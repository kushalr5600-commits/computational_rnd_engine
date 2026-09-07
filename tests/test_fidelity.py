"""Phase J tests: fidelity ladder + promotion policy (honest evidence)."""

from __future__ import annotations

from rnd_engine.fidelity import (
    DEFAULT_PROMOTION_COUNTS,
    FIDELITY_LEVELS,
    EvidenceAssessment,
    PromotionFunnel,
    PromotionPolicy,
    apply_promotion,
    assess_evidence,
)
from rnd_engine.signoff.model import (
    GATE_BLOCKED,
    GATE_PASSED,
    GateResult,
    SignoffResult,
)


def _signoff(gates: dict[str, str], design_id: str = "d1",
             tapeout_ready: bool = False) -> SignoffResult:
    return SignoffResult(
        design_id=design_id,
        architecture_schema_version=1,
        specification_hash="s" * 32,
        rtl_architecture_hash="r" * 32,
        gates=[GateResult(gate=g, stage="x", status=s)
               for g, s in gates.items()],
        tapeout_ready=tapeout_ready,
    )


def test_ladder_and_default_counts():
    assert FIDELITY_LEVELS == (
        "SURROGATE", "RTL", "SYNTHESIS", "PHYSICAL", "SIGNOFF")
    assert DEFAULT_PROMOTION_COUNTS == {
        "SURROGATE": 1000, "RTL": 100, "SYNTHESIS": 20, "PHYSICAL": 5,
        "SIGNOFF": 2}
    assert PromotionPolicy().counts == DEFAULT_PROMOTION_COUNTS


def test_no_gates_is_surrogate():
    a = assess_evidence(_signoff({}))
    assert a.evidence_level == "SURROGATE"
    assert a.blocking_reason == "no RTL gates passed"


def test_blocked_toolchain_caps_at_rtl():
    """The toolless flow's honest answer: RTL evidence, never above."""
    gates = {
        "rtl_structural": GATE_PASSED,
        "rtl_elaboration": GATE_PASSED,
        "verification_reference_model": GATE_PASSED,
        "synthesis": GATE_BLOCKED,
        "physical_implementation": GATE_BLOCKED,
        "drc": GATE_BLOCKED,
        "lvs": GATE_BLOCKED,
    }
    a = assess_evidence(_signoff(gates))
    assert a.evidence_level == "RTL"
    assert "synthesis" in a.blocking_reason
    assert set(a.supporting_gates) == {
        "rtl_structural", "rtl_elaboration", "verification_reference_model"}


def test_ladder_climbs_only_with_real_passes():
    def result(level_gates: dict[str, str], ready: bool = False):
        return _signoff(level_gates, tapeout_ready=ready)

    synth = {"rtl_structural": GATE_PASSED, "rtl_elaboration": GATE_PASSED,
             "synthesis": GATE_PASSED}
    assert assess_evidence(result(synth)).evidence_level == "SYNTHESIS"

    phys = {**synth, "physical_implementation": GATE_PASSED,
            "drc": GATE_PASSED, "lvs": GATE_PASSED}
    assert assess_evidence(result(phys)).evidence_level == "PHYSICAL"

    assert assess_evidence(result(phys, ready=True)).evidence_level == "SIGNOFF"


def test_missing_single_gate_does_not_skip_a_rung():
    gates = {"rtl_structural": GATE_PASSED, "rtl_elaboration": GATE_PASSED,
             "synthesis": GATE_PASSED, "physical_implementation": GATE_PASSED,
             "drc": GATE_PASSED, "lvs": GATE_PASSED}
    # tapeout_ready False -> PHYSICAL, not SIGNOFF.
    a = assess_evidence(_signoff(gates))
    assert a.evidence_level == "PHYSICAL"

# --- promotion funnel -------------------------------------------------------

def _rtl_assessment(design_id: str) -> EvidenceAssessment:
    return EvidenceAssessment(design_id=design_id, evidence_level="RTL")


def test_promotion_respects_per_rung_counts():
    scored = [(float(i), _rtl_assessment(f"d{i}")) for i in range(10)]
    policy = PromotionPolicy(counts={"SURROGATE": 1000, "RTL": 3,
                                     "SYNTHESIS": 20, "PHYSICAL": 5,
                                     "SIGNOFF": 2})
    funnel = apply_promotion(scored, policy)
    assert funnel.summary()["RTL"] == 3
    # The overflow falls back to SURROGATE, ordered by omega.
    assert funnel.summary()["SURROGATE"] == 7
    top = funnel.levels["RTL"]
    assert [r.omega for r in top] == sorted(
        [r.omega for r in top], reverse=True)
    assert {r.design_id for r in top} == {"d9", "d8", "d7"}


def test_promotion_ranks_and_records_evidence():
    scored = [(5.0, EvidenceAssessment(design_id="hi", evidence_level="RTL")),
              (1.0, EvidenceAssessment(design_id="lo", evidence_level="SURROGATE"))]
    funnel = apply_promotion(scored)
    assert funnel.levels["RTL"][0].design_id == "hi"
    assert funnel.levels["RTL"][0].rank == 1
    assert funnel.levels["RTL"][0].promoted_to == "RTL"
    assert funnel.levels["SURROGATE"][0].design_id == "lo"


def test_none_assessment_is_honest_surrogate():
    funnel = apply_promotion([(1.0, None), (2.0, None)])
    assert funnel.summary() == {"SURROGATE": 2}
    assert all(r.evidence_level == "SURROGATE" for r in funnel.levels["SURROGATE"])


def test_fallback_never_climbs_above_evidence():
    """A SYNTHESIS-evidence candidate with a full SYNTHESIS rung falls back
    to RTL, not to PHYSICAL — the ladder cannot be skipped upward."""
    scored = [(float(i), EvidenceAssessment(design_id=f"d{i}",
                                            evidence_level="SYNTHESIS"))
              for i in range(4)]
    policy = PromotionPolicy(counts={"SURROGATE": 1000, "RTL": 1,
                                     "SYNTHESIS": 2, "PHYSICAL": 5,
                                     "SIGNOFF": 2})
    funnel = apply_promotion(scored, policy)
    assert funnel.summary()["SYNTHESIS"] == 2
    assert funnel.summary()["RTL"] == 1
    assert funnel.summary()["SURROGATE"] == 1


def test_promotion_funnel_is_deterministic():
    scored = [(float(i % 7), _rtl_assessment(f"d{i}")) for i in range(15)]
    a = apply_promotion(scored).model_dump_json()
    b = apply_promotion(scored).model_dump_json()
    assert a == b
    assert PromotionFunnel(policy=PromotionPolicy()).summary() == {}