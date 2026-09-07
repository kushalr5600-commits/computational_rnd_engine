"""Phase K tests: release/tapout framework (honest evidence, toolless scope)."""

from __future__ import annotations

import pytest

from rnd_engine.microarchitecture.model import (
    ClockResetSpec,
    ControlSpec,
    DatapathsSpec,
    InterfacesSpec,
    MemoriesSpec,
    MicroArchitectureSpec,
    PipelineSpec,
)
from rnd_engine.release import (
    GATE_BLOCKED,
    GATE_PASS,
    RELEASE_SCHEMA_VERSION,
    ReleaseError,
    ReleaseLevel,
    assess_gate,
    assess_release,
)
from rnd_engine.rtl.model import RtlManifest
from rnd_engine.signoff.model import GATE_PASSED, GateResult, SignoffResult
from rnd_engine.specification.model import ArchitectureSpecification
from rnd_engine.synthesis.model import SynthesisManifest


def _micro(design_id: str = "d1") -> MicroArchitectureSpec:
    return MicroArchitectureSpec(
        design_id=design_id,
        architecture_schema_version=1,
        specification_hash="s" * 32,
        domain="heterogeneous",
        pipeline=PipelineSpec(depth_stages=5, slots_per_stage=2),
        datapaths=DatapathsSpec(
            issue_width=2, register_file_entries=32,
            register_file_read_ports=4, register_file_write_ports=2),
        memories=MemoriesSpec(), interfaces=InterfacesSpec(), control=ControlSpec(),
        clock_reset=ClockResetSpec(),
    )


def _spec(design_id: str = "d1") -> ArchitectureSpecification:
    return ArchitectureSpecification(
        design_id=design_id, architecture_schema_version=1, domain="heterogeneous")


def _rtl(design_id: str = "d1") -> RtlManifest:
    return RtlManifest(
        design_id=design_id, architecture_schema_version=1,
        specification_hash="s" * 32, microarchitecture_hash="m" * 32,
        architecture_hash="r" * 32,
        provenance={"structural_check": "PASSED", "elaboration_check": "PASSED"})


def _synth_blocked(design_id: str = "d1") -> SynthesisManifest:
    """A synthesis manifest pointing at an unavailable toolchain."""
    return SynthesisManifest(
        design_id=design_id, rtl_architecture_hash="r" * 32,
        synthesis_config_hash="", status="BLOCKED")


def _signoff(
    design_id: str = "d1",
    gates: dict[str, str] | None = None,
    tapeout_ready: bool = False,
) -> SignoffResult:
    gates = gates or {}
    return SignoffResult(
        design_id=design_id, architecture_schema_version=1,
        specification_hash="s" * 32, rtl_architecture_hash="r" * 32,
        gates=[GateResult(gate=g, stage="x", status=s) for g, s in gates.items()],
        tapeout_ready=tapeout_ready)


# --- assess_gate ------------------------------------------------------------

def test_assess_gate_normalises_status():
    g = assess_gate("structural", "PASSED")
    assert g.status == GATE_PASS
    assert g.name == "structural"


def test_assess_gate_blocks_when_blocked():
    g = assess_gate("synthesis", "BLOCKED", reason="no toolchain")
    assert g.status == GATE_BLOCKED
    assert g.reason == "no toolchain"


# --- level ladder -----------------------------------------------------------

def test_explore_level_with_no_manifests():
    """No manifests -> EXPLORE (surrogate-only)."""
    m = assess_release(_micro())
    assert m.reached_level == ReleaseLevel.EXPLORE
    assert m.tapeout_ready is False


def test_specified_level_with_specification():
    m = assess_release(_micro(), specification=_spec())
    assert m.reached_level == ReleaseLevel.SPECIFIED


def test_rtlized_level_with_rtl_manifest():
    """Reaching RTLIZED needs the cumulative ladder: spec + RTL gates PASS."""
    m = assess_release(_micro(), specification=_spec(), rtl_manifest=_rtl())
    assert m.reached_level == ReleaseLevel.RTLIZED


def test_toolchain_gates_block_advancement():
    """Even with all manifests, toolchain gates keep level below TAPEOUT."""
    m = assess_release(
        _micro(), specification=_spec(), rtl_manifest=_rtl(),
        signoff_result=_signoff())
    assert m.reached_level < ReleaseLevel.TAPEOUT
    assert m.tapeout_ready is False


def test_tapeout_ready_is_false_in_toolless_flow():
    """The security invariant: tapeout_ready is always False without tools."""
    m = assess_release(
        _micro(), specification=_spec(), rtl_manifest=_rtl(),
        signoff_result=_signoff(tapeout_ready=False))
    assert m.tapeout_ready is False


def test_tapeout_ready_true_requires_all_gates_passed():
    """Even with tapeout_ready=True from signoff, level gates must all PASS."""
    m = assess_release(
        _micro(), rtl_manifest=_rtl(),
        signoff_result=_signoff(
            tapeout_ready=True,
            gates={"synthesis": GATE_PASSED, "physical_implementation": GATE_PASSED,
                   "drc": GATE_PASSED, "lvs": GATE_PASSED}))
    assert m.tapeout_ready is False


# --- design_id consistency --------------------------------------------------

def test_mismatched_design_id_raises():
    with pytest.raises(ReleaseError):
        assess_release(_micro("d1"), rtl_manifest=_rtl("d2"))


def test_mismatched_specification_raises():
    with pytest.raises(ReleaseError):
        assess_release(_micro("d1"), specification=_spec("d2"))


# --- manifest structure -----------------------------------------------------

def test_manifest_carries_schema_version():
    assert assess_release(_micro()).release_schema_version == RELEASE_SCHEMA_VERSION


def test_manifest_lists_blocked_gates():
    m = assess_release(_micro(), synthesis_manifest=_synth_blocked())
    assert [g.name for g in m.gates if g.status == GATE_BLOCKED] == [
        "synthesis_config"]


def test_manifest_ip_provenance_includes_design_id():
    assert assess_release(_micro("d1")).ip_provenance["design_id"] == "d1"


def test_manifest_provenance_records_blocked_count():
    m = assess_release(_micro(), synthesis_manifest=_synth_blocked())
    assert m.provenance["gates_blocked"] == 1
    assert m.provenance["gates_total"] == len(m.gates)


# --- determinism ------------------------------------------------------------

def test_assess_release_is_deterministic():
    a = assess_release(_micro(), specification=_spec(), rtl_manifest=_rtl())
    b = assess_release(_micro(), specification=_spec(), rtl_manifest=_rtl())
    assert a.model_dump_json() == b.model_dump_json()