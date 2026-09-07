"""Signoff orchestration (Phase I)."""

from .generator import (
    SIGNOFF_SCHEMA_VERSION,
    SIGNOFF_TOOLCHAIN_GATES,
    SignoffError,
    collect_gates,
    signoff,
)
from .model import (
    GATE_BLOCKED,
    GATE_FAILED,
    GATE_NOT_RUN,
    GATE_PASSED,
    GateResult,
    MeasuredMetrics,
    SignoffResult,
    SurrogateMetrics,
)

__all__ = [
    "GATE_BLOCKED",
    "GATE_FAILED",
    "GATE_NOT_RUN",
    "GATE_PASSED",
    "SIGNOFF_SCHEMA_VERSION",
    "SIGNOFF_TOOLCHAIN_GATES",
    "GateResult",
    "MeasuredMetrics",
    "SignoffError",
    "SignoffResult",
    "SurrogateMetrics",
    "collect_gates",
    "signoff",
]
