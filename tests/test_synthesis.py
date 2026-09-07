"""Phase F tests: synthesis abstraction (toolless scope)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rnd_engine.microarchitecture import derive_microarchitecture
from rnd_engine.models import Domain
from rnd_engine.rtl import generate_rtl
from rnd_engine.search import SearchEngine
from rnd_engine.specification import build_specification
from rnd_engine.synthesis import (
    SynthesisError,
    run_yosys,
    synthesize,
)
from rnd_engine.synthesis.generator import _parse_stat_output


def _micro(seed: int = 42, domain: Domain = Domain.HETEROGENEOUS):
    design = SearchEngine(seed).seed(1, domain)[0]
    return derive_microarchitecture(build_specification(design))


@pytest.fixture(scope="module")
def micro():
    return _micro()


@pytest.fixture(scope="module")
def synth(micro, tmp_path_factory):
    out = tmp_path_factory.mktemp("synth")
    rtl = generate_rtl(micro, out)
    return synthesize(micro, rtl, out), out, rtl


def test_synthesis_config_is_deterministic(micro, tmp_path):
    rtl = generate_rtl(micro, tmp_path / "a")
    a = synthesize(micro, rtl, tmp_path / "a")
    b = synthesize(micro, rtl, tmp_path / "b")
    assert a.model_dump_json() == b.model_dump_json()
    assert a.synthesis_config_hash == b.synthesis_config_hash


def test_synthesis_blocked_without_yosys(synth, micro):
    manifest, out, _ = synth
    assert manifest.status == "BLOCKED"
    assert manifest.tool_path is None
    assert manifest.stats is None          # no fabricated area/cell numbers
    assert manifest.netlist_path is None
    assert (Path(out) / "configs" / "synthesis" / micro.design_id
            / "config.json").exists()
    assert (Path(out) / "flows" / "synthesis" / micro.design_id
            / "flow.ys").exists()
    report = json.loads(
        (Path(out) / "reports" / "synthesis" / micro.design_id / "yosys.json")
        .read_text(encoding="utf-8"))
    assert report["status"] == "BLOCKED"
    assert any(i["rule"] == "TOOL" for i in report["issues"])


def test_synthesis_config_binds_design(micro, synth):
    manifest, out, rtl = synth
    assert manifest.design_id == micro.design_id
    assert manifest.rtl_architecture_hash == rtl.architecture_hash
    cfg = json.loads(
        (Path(out) / "configs" / "synthesis" / micro.design_id / "config.json")
        .read_text(encoding="utf-8"))
    assert cfg["top_module"] == "top"
    assert "top.sv" in cfg["source_files"]
    assert cfg["clock_period_ns"] > 0
    assert manifest.provenance["seed"] == micro.provenance["seed"]


def test_yosys_flow_lists_all_sources(micro, synth):
    _, out, rtl = synth
    flow = (Path(out) / "flows" / "synthesis" / micro.design_id
            / "flow.ys").read_text("utf-8")
    for meta in rtl.files:
        if meta.path.endswith(".sv"):
            assert f"read_verilog -sv {meta.path}" in flow
    assert "synth -top top" in flow
    assert "stat" in flow
    assert f"write_json {micro.design_id}.netlist.json" in flow


def test_run_yosys_reports_failed_on_tool_error(tmp_path, monkeypatch):
    """A failing tool run is FAILED with stderr kept — never silently PASS."""
    rtl_dir = tmp_path / "rtl"
    rtl_dir.mkdir()
    (rtl_dir / "bad.sv").write_text("module broken(; endmodule", encoding="utf-8")
    monkeypatch.setattr(
        "rnd_engine.synthesis.generator.subprocess.run",
        lambda *a, **k: type("P", (), {"returncode": 1, "stdout": "",
                                       "stderr": "boom"})())
    status, stats, err = run_yosys(rtl_dir, "synth", tmp_path / "work")
    assert status == "FAILED"
    assert stats is None
    assert err == "boom"


def test_stat_parser_extracts_cell_counts():
    out = """
=== top ===

   Number of wires:                 42
   Number of cells:                 17
     $_AND_                          5
     $_DFF_P_                        8
     $_NOT_                          4
"""
    stats = _parse_stat_output(out)
    assert stats.number_of_wires == 42
    assert stats.number_of_cells == 17
    assert stats.cell_types == {"$_AND_": 5, "$_DFF_P_": 8, "$_NOT_": 4}


def test_synthesize_rejects_foreign_manifest(micro, tmp_path):
    rtl = generate_rtl(micro, tmp_path)
    other = _micro(seed=43)
    with pytest.raises(SynthesisError, match="design"):
        synthesize(other, rtl, tmp_path)
