"""Fidelity ladder + promotion policy (Phase J).

The evidence level of a design is derived ONLY from actual gate outcomes in
its stage manifests. A design cannot claim SYNTHESIS fidelity because it
"would pass" — the Yosys gate must have actually run and PASSED. In the
toolless flow every design therefore caps at RTL evidence, which is the
honest answer, not a limitation of the ladder.
"""

from __future__ import annotations

from ..signoff.model import GATE_NOT_RUN, GATE_PASSED, SignoffResult
from .model import (
    FIDELITY_LEVELS,
    EvidenceAssessment,
    PromotionFunnel,
    PromotionPolicy,
    PromotionRecord,
)

__all__ = [
    "FIDELITY_LEVELS",
    "EvidenceAssessment",
    "PromotionFunnel",
    "PromotionPolicy",
    "PromotionRecord",
    "apply_promotion",
    "assess_evidence",
]


def _gate_passed(result: SignoffResult, gate: str) -> bool:
    g = result.gate(gate)
    return g is not None and g.status == GATE_PASSED


def assess_evidence(signoff_result: SignoffResult) -> EvidenceAssessment:
    """Map signoff gate outcomes onto the honest evidence level."""
    gates = {g.gate: g.status for g in signoff_result.gates}
    level = "SURROGATE"
    reason = "no RTL gates passed"

    if _gate_passed(signoff_result, "rtl_structural") and \
       _gate_passed(signoff_result, "rtl_elaboration"):
        level = "RTL"
        reason = "SYNTHESIS requires a PASSED synthesis gate " \
                 f"(got {gates.get('synthesis', GATE_NOT_RUN)})"
    if level == "RTL" and _gate_passed(signoff_result, "synthesis"):
        level = "SYNTHESIS"
        reason = "PHYSICAL requires PASSED floorplan..lvs gates"
    if level == "SYNTHESIS" and all(
        _gate_passed(signoff_result, s)
        for s in ("physical_implementation", "drc", "lvs")
    ):
        level = "PHYSICAL"
        reason = "SIGNOFF requires tapeout_ready"
    if level == "PHYSICAL" and signoff_result.tapeout_ready:
        level = "SIGNOFF"
        reason = ""

    return EvidenceAssessment(
        design_id=signoff_result.design_id,
        evidence_level=level,
        supporting_gates={g: s for g, s in gates.items() if s == GATE_PASSED},
        blocking_reason=reason if level != "SIGNOFF" else "",
    )


def apply_promotion(
    scored: list[tuple[float, EvidenceAssessment]],
    policy: PromotionPolicy | None = None,
) -> PromotionFunnel:
    """Promote candidates up the ladder, respecting per-rung counts.

    ``scored`` pairs each candidate's omega score with its evidence
    assessment. Candidates are ranked by omega (descending); each rung keeps
    at most ``policy.counts[level]`` candidates whose evidence supports it.
    A candidate occupies the highest rung it qualifies for.
    """
    policy = policy or PromotionPolicy()
    ranked = sorted(scored, key=lambda pair: -pair[0])
    funnel = PromotionFunnel(policy=policy)
    occupied: dict[str, int] = {lvl: 0 for lvl in FIDELITY_LEVELS}

    for omega, assessment in ranked:
        if assessment is None:
            # No stage flows were executed for this candidate: honest
            # evidence level is SURROGATE.
            assessment = EvidenceAssessment(design_id="", evidence_level="SURROGATE")
        # Walk DOWN from the candidate's evidence level to the first rung
        # with room. The ladder can only be descended here — a full higher
        # rung never pushes a candidate above its evidence.
        for lvl in reversed(
            FIDELITY_LEVELS[: FIDELITY_LEVELS.index(assessment.evidence_level) + 1]
        ):
            if occupied[lvl] < policy.counts.get(lvl, 0):
                occupied[lvl] += 1
                funnel.levels.setdefault(lvl, []).append(
                    PromotionRecord(
                        design_id=assessment.design_id,
                        omega=omega,
                        evidence_level=assessment.evidence_level,
                        promoted_to=lvl,
                        rank=occupied[lvl],
                    ))
                break
        # A candidate with no room anywhere in the funnel is dropped: the
        # promotion counts are a hard budget, not a suggestion.
    funnel.counts_summary = funnel.summary()
    return funnel
