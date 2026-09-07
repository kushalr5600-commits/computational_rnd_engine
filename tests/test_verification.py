"""Phase E verification-package tests (toolless scope)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rnd_engine.microarchitecture import derive_microarchitecture
from rnd_engine.models import Domain
from rnd_engine.rtl import generate_rtl
from rnd_engine.search import SearchEngine
from rnd_engine.specification import build_specification
from rnd_engine.verification import (
    OP_ADD,
    OP_HALT,
    OP_NOP,
    REFERENCE_OPS,
    ReferenceModel,
    VerificationError,
    encode_insn,
    generate_verification,
    run_reference_gate,
)
from rnd_engine.verification.generator import (
    GENERATOR_VERSION,
    VERIFICATION_SCHEMA_VERSION,
    _directed_tests,
    _rtl_params,
)


def _micro(seed: int = 42, domain: Domain = Domain.HETEROGENEOUS):
    design = SearchEngine(seed).seed(1, domain)[0]
    return derive_microarchitecture(build_specification(design))


@pytest.fixture(scope="module")
def micro():
    return _micro()


@pytest.fixture(scope="module")
def verified(micro, tmp_path_factory):
    out = tmp_path_factory.mktemp("verif")
    rtl = generate_rtl(micro, out)
    return generate_verification(micro, rtl, out), out


def test_reference_model_matches_rtl_semantics():
    model = ReferenceModel(16, 3)
    # ADD r3 = r1 + r2; HALT; trailing never executes; NOP writes a+b
    prog = [
        encode_insn(OP_ADD, 1, 2, 3, 3),
        encode_insn(OP_NOP, 1, 2, 4, 3),
        encode_insn(OP_HALT, 0, 0, 0, 3),
        encode_insn(OP_ADD, 3, 3, 3, 3),  # after halt: must not run
    ]
    res = model.run(prog, {0x4: 0x11}, {1: 9, 2: 5})
    assert res.regs["x3"] == 14
    assert res.regs["x4"] == 14          # NOP writes ALU default a+b
    assert res.retired == 3              # HALT itself retires
    assert res.halted
    assert res.memory["4"] == 0x11


def test_reference_model_wraps_at_isa_width():
    model = ReferenceModel(8, 2)
    res = model.run([encode_insn(OP_ADD, 1, 2, 3, 2),
                     encode_insn(OP_HALT, 0, 0, 0, 2)],
                    init_regs={1: 0xFF, 2: 0x2})
    assert res.regs["x3"] == 0x01


def test_reference_model_rejects_out_of_scope_op():
    model = ReferenceModel(16, 3)
    with pytest.raises(ValueError, match="out of scope"):
        model.run([encode_insn(0x8, 0, 0, 1, 3)])  # OP_VEC has no ref semantics


def test_reference_ops_cover_defined_isa():
    assert REFERENCE_OPS == {0x0, 0x1, 0x2, 0x3, 0x4, 0x5, 0x6, 0x7, 0xF}


def test_reference_gate_passes_on_all_directed_tests(micro):
    tests = _directed_tests(_rtl_params(micro))
    assert len(tests) >= 5
    report, results = run_reference_gate(tests)
    assert report.status == "PASSED", [i.message for i in report.issues]
    assert report.summary["passed"] == report.summary["tests"] == len(tests)
    assert all(r["status"] == "PASSED" for r in results)


def test_reference_gate_detects_a_broken_expectation(micro):
    tests = _directed_tests(_rtl_params(micro))
    tests[0].expected_regs["x3"] = 0xDEAD  # corrupt one hand-written expectation
    report, results = run_reference_gate(tests)
    assert report.status == "FAILED"
    assert any(i.rule == "REF-002" for i in report.issues)
    assert results[0]["status"] == "FAILED"


def test_generate_verification_artifacts(verified, micro):
    _, out = verified
    base = Path(out)
    assert (base / "verification" / micro.design_id / "tb_top.sv").exists()
    assert (base / "verification" / micro.design_id / "tests.json").exists()
    assert (base / "verification" / "formal" / micro.design_id
            / "properties.sva").exists()
    reports = base / "reports" / "verification" / micro.design_id
    gates = json.loads((reports / "gates.json").read_text(encoding="utf-8"))
    assert gates["gates"]["reference_model"]["status"] == "PASSED"
    assert gates["gates"]["simulation"]["status"] == "BLOCKED"
    assert gates["gates"]["formal"]["status"] == "BLOCKED"


def test_blocked_gates_never_claim_pass(verified):
    report, _ = verified
    assert report.provenance["simulation"] == "BLOCKED"
    assert report.provenance["formal"] == "BLOCKED"
    tb = report.provenance["tb_top_sha256"]
    assert len(tb) == 64


def test_verification_manifest_binds_to_rtl_build(verified, micro):
    manifest, _ = verified
    assert manifest.design_id == micro.design_id
    assert manifest.verification_schema_version == VERIFICATION_SCHEMA_VERSION
    assert manifest.generator_version == GENERATOR_VERSION
    assert manifest.rtl_architecture_hash
    assert {t.name for t in manifest.tests} >= {
        "alu_ops", "mem_roundtrip", "halt_stops", "nop_writes", "wrap"}
    assert manifest.provenance["seed"] == micro.provenance["seed"]


def test_verification_generation_is_deterministic(micro, tmp_path):
    rtl = generate_rtl(micro, tmp_path / "a")
    a = generate_verification(micro, rtl, tmp_path / "a")
    b = generate_verification(micro, rtl, tmp_path / "b")
    assert a.model_dump_json() == b.model_dump_json()


def test_generate_verification_rejects_foreign_manifest(micro, tmp_path):
    rtl = generate_rtl(micro, tmp_path)
    other = _micro(seed=43)
    with pytest.raises(VerificationError, match="design"):
        generate_verification(other, rtl, tmp_path)


def test_generate_verification_rejects_unlabeled_design(tmp_path):
    bad = _micro(seed=7, domain=Domain.CPU)
    bad.design_id = ""
    with pytest.raises(VerificationError):
        generate_verification(bad, generate_rtl(_micro(seed=7, domain=Domain.CPU),
                                                tmp_path), tmp_path)
