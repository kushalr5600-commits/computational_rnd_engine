"""Signoff orchestration models (Phase I)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

SIGNOFF_SCHEMA_VERSION: int = 1

# Gate statuses mirror the honesty vocabulary used across the project.
GATE_PASSED = "PASSED"
GATE_BLOCKED = "BLOCKED"
GATE_FAILED = "FAILED"
GATE_NOT_RUN = "NOT_RUN"


class SurrogateMetrics(BaseModel):
    """Pre-silicon *predicted* metrics from the search/surrogate models.

    These are estimates the search optimized against — never measurements.
    Kept separate from ``MeasuredMetrics`` so no prediction can be mistaken
    for a tool-produced number.
    """

    predicted_area_au: float | None = None      # architecture-relative units
    predicted_power_au: float | None = None
    predicted_cycles_per_op: float | None = None
    confidence: float | None = None


class MeasuredMetrics(BaseModel):
    """Metrics produced ONLY by real tools on a real toolchain.

    Every field starts as None; a value may be filled exclusively from a
    tool report that the flow actually executed. There is no code path that
    fills these without a tool run.
    """

    area_um2: float | None = None
    worst_slack_ns: float | None = None
    tns_ns: float | None = None
    power_w: float | None = None
    drc_violations: int | None = None
    lvs_clean: bool | None = None
    source: str | None = None  # e.g. "openroad+magic+netgen"


class GateResult(BaseModel):
    """One signoff gate with its honest outcome."""

    gate: str
    stage: str  # rtl / verification / synthesis / technology / physical
    status: str  # PASSED / BLOCKED / FAILED / NOT_RUN
    reason: str = ""


class SignoffResult(BaseModel):
    """Aggregated signoff across every stage manifest of one build.

    ``tapeout_ready`` is True only when EVERY gate is PASSED — a single
    BLOCKED or NOT_RUN gate (i.e. any missing tool or PDK) keeps the design
    firmly not ready. This is the Phase I honesty invariant.
    """

    design_id: str
    architecture_schema_version: int
    specification_hash: str
    rtl_architecture_hash: str
    signoff_schema_version: int = SIGNOFF_SCHEMA_VERSION
    gates: list[GateResult] = Field(default_factory=list)
    tapeout_ready: bool = False
    blocked_gates: list[str] = Field(default_factory=list)
    surrogate_metrics: SurrogateMetrics | None = None
    measured_metrics: MeasuredMetrics = Field(default_factory=MeasuredMetrics)
    provenance: dict[str, Any] = Field(default_factory=dict)

    def gate(self, name: str) -> GateResult | None:
        return next((g for g in self.gates if g.gate == name), None)
