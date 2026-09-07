"""Multi-fidelity evaluation models (Phase J)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# Fidelity ladder, lowest to highest. A design's evidence level is the highest
# rung its ACTUAL gate outcomes support — never aspirational.
FIDELITY_LEVELS: tuple[str, ...] = (
    "SURROGATE",
    "RTL",
    "SYNTHESIS",
    "PHYSICAL",
    "SIGNOFF",
)

# Roadmap promotion funnel: how many candidates may occupy each rung.
DEFAULT_PROMOTION_COUNTS: dict[str, int] = {
    "SURROGATE": 1000,
    "RTL": 100,
    "SYNTHESIS": 20,
    "PHYSICAL": 5,
    "SIGNOFF": 2,
}


class EvidenceAssessment(BaseModel):
    """Honest evidence level for one design, derived from gate outcomes."""

    design_id: str
    evidence_level: str = "SURROGATE"
    supporting_gates: dict[str, str] = Field(default_factory=dict)
    blocking_reason: str = ""


class PromotionPolicy(BaseModel):
    """Configurable per-rung promotion counts (default 1000/100/20/5/2)."""

    counts: dict[str, int] = Field(default_factory=lambda: dict(DEFAULT_PROMOTION_COUNTS))
    provenance: dict[str, Any] = Field(default_factory=dict)


class PromotionRecord(BaseModel):
    """One candidate's position in the promotion funnel."""

    design_id: str
    omega: float
    evidence_level: str
    promoted_to: str  # highest rung the candidate actually occupies
    rank: int
    provenance: dict[str, Any] = Field(default_factory=dict)


class PromotionFunnel(BaseModel):
    """Result of applying a promotion policy to a scored population."""

    levels: dict[str, list[PromotionRecord]] = Field(default_factory=dict)
    policy: PromotionPolicy = Field(default_factory=PromotionPolicy)
    counts_summary: dict[str, int] = Field(default_factory=dict)

    def summary(self) -> dict[str, int]:
        return {lvl: len(recs) for lvl, recs in self.levels.items()}
