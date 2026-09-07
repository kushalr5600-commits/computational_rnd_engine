"""Verification data models (Phase E, toolless scope)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RefRunResult(BaseModel):
    """Outcome of one run of the pure-Python reference model."""

    regs: dict[str, int] = Field(default_factory=dict)
    memory: dict[str, int] = Field(default_factory=dict)
    retired: int = 0
    halted: bool = False


class RtlTestCase(BaseModel):
    """One directed verification case.

    ``expected`` carries hand-computed final state (written literally when the
    test is constructed — never derived by running the reference model), so a
    model-vs-expected comparison is a real check, not a tautology.
    """

    name: str
    description: str = ""
    log_regs: int
    isa_width: int
    program: list[str] = Field(default_factory=list)  # hex instruction words
    init_memory: dict[str, int] = Field(default_factory=dict)  # word addr hex -> value
    init_regs: dict[str, int] = Field(default_factory=dict)  # x-index -> value
    expected_regs: dict[str, int] = Field(default_factory=dict)
    expected_memory: dict[str, int] = Field(default_factory=dict)
    expected_retired: int = 0
    expected_halted: bool = True


class VerificationManifest(BaseModel):
    """Manifest binding verification artifacts to the RTL build they target."""

    design_id: str
    rtl_architecture_hash: str
    verification_schema_version: int = 1
    generator_version: str = "1.0.0"
    tests: list[RtlTestCase] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
