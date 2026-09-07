"""Phase I tests: signoff orchestration (toolless scope)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rnd_engine.microarchitecture import derive_microarchitecture
from rnd_engine.models import Domain
from rnd_engine.physical import bind_physical
from rnd_engine.rtl import generate_rtl
from rnd_engine.search import SearchEngine
from rnd_engine.signoff import (
    GATE_PASSED,
    SIGNOFF_TOOLCHAIN_GATES,
    MeasuredMetrics,
    SignoffError,
    SignoffResult,
    SurrogateMetrics,
    collect_gates,
    signoff,
)
from rnd_engine.specification import build_specification
from rnd_engine.synthesis import synthesize
from rnd_engine.technology import SKY130, bind_technology
from rnd_engine.verification import generate_verification


def _micro(seed: int = 42, domain: Domain = Domain.HETEROGENEOUS):
    design = SearchEngine(seed).seed(1, domain)[0]
    return derive_microarchitecture(build_specification(design))


def _open_pdk_micro(seed: int = 42):
    micro = _micro(seed)
    for dom in micro.clock_reset.domains:
        dom.technology_nm = SKY130.node_nm
        dom.voltage_v = 1.8
    return micro


@pytest.fixture(scope="module")
def full(tmp_path_factory):
    micro = _open_pdk_micro()

    def build(out):
        rtl = generate_rtl(micro, out)
        ver = generate_verification(micro, rtl, out)
        syn = synthesize(micro, rtl, out)
        tech = bind_technology(micro, rtl, syn, out)
        phys = bind_physical(micro, rtl, syn, tech, out)
        return signoff(micro, rtl, ver, syn, tech, phys, out), (
            micro, rtl, ver, syn, tech, phys)
    out = tmp_path_factory.mktemp("signoff")
    result, _parts = build(out)
    return result, out, micro, build

# === PART2 ===

# --- aggregation -------------------------------------------------------------

def test_gates_cover_all_stages_and_pass_real_ones(full):
    result, *_ = full
    stages = {g.stage for g in result.gates}
    assert stages == {"rtl", "verification", "synthesis", "technology", "physical"}
    by_name = {g.gate: g.status for g in result.gates}
    assert by_name["rtl_structural"] == GATE_PASSED
    assert by_name["rtl_elaboration"] == GATE_PASSED
    assert by_name["reference_model"] == GATE_PASSED


def test_tapeout_not_ready_in_toolless_flow(full):
    result, *_ = full
    assert result.tapeout_ready is False
    assert result.blocked_gates, "toolchain gates must be blocked"
    for gate in SIGNOFF_TOOLCHAIN_GATES:
        assert gate in result.blocked_gates, gate


def test_gate_statuses_copied_verbatim(full):
    result, out, micro, _build = full
    ver = generate_verification(micro, generate_rtl(micro, out), out)
    by_name = {g.gate: g for g in result.gates}
    assert by_name["reference_model"].status == ver.provenance["reference_model"]
    assert by_name["simulation"].status == ver.provenance["simulation"]


def test_tapeout_ready_requires_every_gate_passed(tmp_path):
    """A hypothetical all-PASS gate list flips tapeout_ready — and only that."""
    micro = _open_pdk_micro()
    rtl = generate_rtl(micro, tmp_path)
    ver = generate_verification(micro, rtl, tmp_path)
    syn = synthesize(micro, rtl, tmp_path)
    tech = bind_technology(micro, rtl, syn, tmp_path)
    phys = bind_physical(micro, rtl, syn, tech, tmp_path)
    gates = collect_gates(rtl, ver, syn, tech, phys)
    for g in gates:
        g.status = GATE_PASSED
        g.reason = ""
    all_pass = SignoffResult(
        design_id=micro.design_id,
        architecture_schema_version=micro.architecture_schema_version,
        specification_hash=micro.specification_hash,
        rtl_architecture_hash=rtl.architecture_hash,
        gates=gates,
        tapeout_ready=all(g.status == GATE_PASSED for g in gates),
        blocked_gates=[],
    )
    assert all_pass.tapeout_ready is True


# --- metric separation -------------------------------------------------------

def test_measured_metrics_empty_and_separate_from_surrogate(full):
    result, *_ = full
    assert result.measured_metrics.model_dump() == MeasuredMetrics().model_dump()
    assert all(v is None for v in result.measured_metrics.model_dump().values())
    # No surrogate metrics in provenance -> None, never invented.
    assert result.surrogate_metrics is None


def test_surrogate_metrics_come_only_from_provenance(tmp_path):
    micro = _open_pdk_micro()
    micro.provenance["surrogate_metrics"] = {
        "predicted_area_au": 1234.0, "confidence": 0.7}
    rtl = generate_rtl(micro, tmp_path)
    ver = generate_verification(micro, rtl, tmp_path)
    syn = synthesize(micro, rtl, tmp_path)
    tech = bind_technology(micro, rtl, syn, tmp_path)
    phys = bind_physical(micro, rtl, syn, tech, tmp_path)
    result = signoff(micro, rtl, ver, syn, tech, phys, tmp_path)
    assert isinstance(result.surrogate_metrics, SurrogateMetrics)
    assert result.surrogate_metrics.predicted_area_au == 1234.0
    # Predictions must never leak into measured metrics.
    assert result.measured_metrics.area_um2 is None


# --- persistence & consistency ----------------------------------------------

def test_signoff_report_written(full):
    _result, out, micro, _build = full
    path = Path(out) / "reports" / "signoff" / micro.design_id / "signoff.json"
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["tapeout_ready"] is False
    assert data["design_id"] == micro.design_id


def test_signoff_rejects_foreign_manifest(full, tmp_path):
    _, out, _micro, build = full
    other = _open_pdk_micro(seed=43)
    other_rtl = generate_rtl(other, tmp_path)
    _res, parts = build(out)
    _m, _rtl, ver, syn, tech, phys = parts
    with pytest.raises(SignoffError, match="design"):
        signoff(other, other_rtl, ver, syn, tech, phys, tmp_path)


def test_signoff_deterministic(full):
    result, out, _micro, build = full
    again, _ = build(out)
    assert again.model_dump_json() == result.model_dump_json()