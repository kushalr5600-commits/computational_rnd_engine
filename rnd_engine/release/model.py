"""Release/tapout framework (Phase K).

Release levels LEVEL_0..LEVEL_7 with evidence gates. A tapeout package is only
emitted at LEVEL_7 and only when every evidence gate PASSED; because the
toolless flow leaves the 9 toolchain gates BLOCKED, ``tapeout_ready`` is always
False here and a tapout package is **never** fabricated. This is the core
security/correctness invariant of the phase: the framework can refuse, but it
must never claim.
"""

from __future__ import annotations

from enum import IntEnum
from typing import Any

from pydantic import BaseModel, Field


class ReleaseLevel(IntEnum):
    """Maturity stages of the architecture->silicon pipeline."""

    EXPLORE = 0      # surrogate metrics only
    SPECIFIED = 1    # canonical specification written
    RTLIZED = 2      # RTL generated + structural/elaboration gates PASS
    VERIFIED = 3     # reference model passes; testbench/SVA generated
    SYNTHESIZED = 4  # synthesis config/flow generated (BLOCKED)
    PHYSICATED = 5   # physical config + stage scripts generated (BLOCKED)
    SIGNED_OFF = 6   # signoff orchestration runs (toolchain BLOCKED)
    TAPEOUT = 7      # tapeout package -- only emitted when tapeout_ready


RELEASE_SCHEMA_VERSION = 1
RELEASE_PACKAGE_NAME = "rnd-engine-release"


# The gates each level requires to be PASSED (or BLOCKED, for toolchain gates).
# Toolchain gates that cannot run in a toolless environment are listed here so
# the level's evidence can be audited; they do NOT permit tapeout.
_LEVEL_GATES: dict[ReleaseLevel, dict[str, str]] = {
    ReleaseLevel.EXPLORE: {"surrogate_score": "PASS"},
    ReleaseLevel.SPECIFIED: {"specification": "PASS",
                              "specification_schema": "PASS"},
    ReleaseLevel.RTLIZED: {"structural": "PASS", "elaboration": "PASS"},
    ReleaseLevel.VERIFIED: {"reference_model": "PASS"},
    ReleaseLevel.SYNTHESIZED: {"synthesis_config": "PASS"},
    ReleaseLevel.PHYSICATED: {"physical_plan": "PASS"},
    ReleaseLevel.SIGNED_OFF: {
        "signoff_orchestration": "PASS",
        "tapeout_ready": "False",  # truthfully False: toolchain BLOCKED
    },
    ReleaseLevel.TAPEOUT: {"tapeout_ready": "True"},
}


class GateStatus(BaseModel):
    name: str
    status: str  # PASS / FAILED / BLOCKED / NOT_RUN
    gate_schema_version: int | None = None
    reason: str = ""


class ReleaseManifest(BaseModel):
    design_id: str
    reached_level: ReleaseLevel
    tapeout_ready: bool = False
    gates: list[GateStatus] = Field(default_factory=list)
    release_schema_version: int = 1
    ip_provenance: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)
