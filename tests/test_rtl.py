from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from rnd_engine.microarchitecture import derive_microarchitecture
from rnd_engine.models import Domain
from rnd_engine.rtl import (
    RTL_SCHEMA_VERSION,
    RtlError,
    elaboration_check,
    generate_rtl,
    rtl_directory,
    rtl_file_hash,
    structural_check,
)
from rnd_engine.rtl.checker import detect_tools, run_rtl_lint
from rnd_engine.search import SearchEngine
from rnd_engine.specification import build_specification

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def micro():
    design = SearchEngine(42).seed(1, Domain.HETEROGENEOUS)[0]
    return derive_microarchitecture(build_specification(design))


@pytest.fixture(scope="module")
def generated(tmp_path_factory, micro):
    out = tmp_path_factory.mktemp("rtl_a")
    manifest = generate_rtl(micro, out)
    return manifest, rtl_directory(out, micro.design_id), out


def _micro_for(seed: int, domain: Domain = Domain.HETEROGENEOUS):
    design = SearchEngine(seed).seed(1, domain)[0]
    return derive_microarchitecture(build_specification(design))


def test_generation_is_deterministic(micro, tmp_path):
    out_a = generate_rtl(micro, tmp_path / "a")
    out_b = generate_rtl(micro, tmp_path / "b")
    assert out_a.model_dump_json() == out_b.model_dump_json()
    assert out_a.architecture_hash == out_b.architecture_hash


def test_manifest_links_to_design_spec_and_microarchitecture(generated, micro):
    manifest, _, _ = generated
    assert manifest.design_id == micro.design_id
    assert manifest.specification_hash == micro.specification_hash
    assert manifest.architecture_schema_version == micro.architecture_schema_version
    assert manifest.rtl_schema_version == RTL_SCHEMA_VERSION
    assert manifest.generator_version == "1.0.0"
    assert manifest.provenance["seed"] == micro.provenance["seed"]


def test_file_hashes_match_on_disk(generated):
    manifest, rtl_dir, _ = generated
    for meta in manifest.files:
        path = rtl_dir / meta.path
        assert path.exists()
        assert rtl_file_hash(path) == meta.sha256


def test_structural_gate_passes(generated):
    manifest, rtl_dir, base = generated
    report = structural_check(rtl_dir)
    assert report.status == "PASSED", [i.message for i in report.issues]
    assert (
        base / "reports" / "lint" / manifest.design_id / "lint_structural.json"
    ).exists()


def test_real_lint_blocked_without_tool(generated, monkeypatch):
    _, rtl_dir, _ = generated
    monkeypatch.setattr(
        "rnd_engine.rtl.checker.shutil.which", lambda _: None
    )
    assert all(v is None for v in detect_tools().values())
    report = run_rtl_lint(rtl_dir, tool="verilator")
    assert report.status == "BLOCKED"
    assert any(i.rule == "TOOL" for i in report.issues)


def test_only_required_modules_generated(generated, micro):
    manifest, rtl_dir, _ = generated
    names = {meta.path for meta in manifest.files}
    assert {"arch_pkg.sv", "alu.sv", "fetch.sv", "decode.sv", "issue.sv",
            "register_file.sv", "top.sv", "filelist.f"} <= names
    kinds = {d.kind for d in micro.datapaths.datapaths}
    assert ("vector_unit.sv" in names) == ("vector" in kinds)
    assert ("specialized_unit.sv" in names) == bool(kinds & {"tensor", "specialized"})
    top = (rtl_dir / "top.sv").read_text(encoding="utf-8")
    assert ("vector_unit_u" in top) == ("vector_unit.sv" in names)
    assert ("specialized_unit_u" in top) == ("specialized_unit.sv" in names)


def test_no_unsubstituted_template_variables(generated):
    _, rtl_dir, _ = generated
    for path in rtl_dir.glob("*.sv"):
        assert not re.findall(r"\$[A-Z_]+", path.read_text(encoding="utf-8")), path.name


def test_filelist_lists_modules(generated):
    manifest, rtl_dir, _ = generated
    text = (rtl_dir / "filelist.f").read_text(encoding="utf-8")
    for meta in manifest.files:
        if meta.path.endswith(".sv"):
            assert meta.path in text
    assert manifest.design_id in text


def test_arch_pkg_binds_microarchitecture_values(generated, micro):
    _, rtl_dir, _ = generated
    pkg = (rtl_dir / "arch_pkg.sv").read_text(encoding="utf-8")
    alu = next(d for d in micro.datapaths.datapaths if d.kind == "alu")
    assert f"localparam int ISA_WIDTH          = {alu.width_bits};" in pkg
    assert f"localparam int ISSUE_WIDTH        = {micro.datapaths.issue_width};" in pkg
    assert f"localparam int REG_COUNT          = {micro.datapaths.register_file_entries};" in pkg
    assert micro.design_id in pkg


def test_unlabeled_microarchitecture_rejected():
    bad = _micro_for(7, Domain.CPU)
    bad.design_id = ""
    with pytest.raises(RtlError):
        generate_rtl(bad)


def test_cross_process_rtl_build_hash_stable():
    script = (
        "from rnd_engine.models import Domain\n"
        "from rnd_engine.search import SearchEngine\n"
        "from rnd_engine.specification import build_specification\n"
        "from rnd_engine.microarchitecture import derive_microarchitecture\n"
        "from rnd_engine.rtl import generate_rtl\n"
        "d = SearchEngine(42).seed(1, Domain.GPU)[0]\n"
        "m = derive_microarchitecture(build_specification(d))\n"
        "print(generate_rtl(m).architecture_hash)\n"
    )

    def run() -> str:
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            check=True,
            cwd=REPO_ROOT,
        )
        return result.stdout.strip()
    assert run() == run()


# ---------------------------------------------------------------------------
# Phase 5 elaboration gate (ELB rules)
# ---------------------------------------------------------------------------

_LEAF_SV = """\
module leaf #(
  parameter int W = 8
) (
  input  logic clk,
  input  logic [W-1:0] a,
  output logic [W-1:0] y
);
  assign y = a;
endmodule
"""


def test_elaboration_gate_passes(generated):
    manifest, rtl_dir, base = generated
    report = elaboration_check(rtl_dir)
    assert report.status == "PASSED", [i.message for i in report.issues]
    assert report.summary["instances"] >= 5  # fetch/decode/issue/rf/alu at least
    assert manifest.provenance["elaboration_check"] == "PASSED"
    assert (
        base / "reports" / "lint" / manifest.design_id / "lint_elaboration.json"
    ).exists()
    gates = (base / "verification" / "lint" / "gates.json").read_text(encoding="utf-8")
    for gate in ("structural", "elaboration", "lint_verilator", "lint_iverilog"):
        assert f'"{gate}"' in gates


def test_elaboration_detects_wiring_errors(tmp_path):
    (tmp_path / "leaf.sv").write_text(_LEAF_SV, encoding="utf-8")
    cases = {
        "ELB-001": "module top; missing #(.W(4)) u1 (.clk()); endmodule",
        "ELB-002": (
            "module top; leaf #(.W(4)) u1 (.clk(), .a(), .y(), .zz()); endmodule"
        ),
        "ELB-003": "module top; leaf #(.W(4)) u1 (.clk(), .y()); endmodule",
        "ELB-004": (
            "module top; leaf #(.W(4)) u1 (.clk(), .a(), .y(), .clk()); endmodule"
        ),
        "ELB-005": (
            "module top; leaf #(.Q(4)) u1 (.clk(), .a(), .y()); endmodule"
        ),
    }
    for rule, top_src in cases.items():
        (tmp_path / "top.sv").write_text(top_src, encoding="utf-8")
        report = elaboration_check(tmp_path)
        found = {i.rule for i in report.issues}
        assert report.status == "FAILED", rule
        assert rule in found, (rule, found)


def test_elaboration_requires_top_module(tmp_path):
    (tmp_path / "leaf.sv").write_text(_LEAF_SV, encoding="utf-8")
    (tmp_path / "other.sv").write_text(
        "module other; leaf #(.W(4)) u1 (.clk(), .a(), .y()); endmodule",
        encoding="utf-8",
    )
    report = elaboration_check(tmp_path)
    assert report.status == "FAILED"
    assert any(i.rule == "ELB-006" for i in report.issues)
