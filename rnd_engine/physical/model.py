"""Physical design + DRC/LVS abstraction models (Phase H, toolless scope)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

# Physical implementation stages the flow models. Every stage is a real
# OpenROAD/checker step; without a toolchain each reports BLOCKED.
PHYSICAL_STAGES: tuple[str, ...] = (
    "floorplan",
    "placement",
    "cts",
    "routing",
    "sta",
    "power",
    "drc",
    "lvs",
)


class FloorplanParams(BaseModel):
    """Deterministic floorplan parameters derived from the design."""

    utilization_pct: float
    aspect_ratio: float
    core_margin_um: float
    place_site_name: str


class CtsParams(BaseModel):
    """Clock-tree synthesis parameters derived from the clock domain."""

    clock_port: str
    period_ns: float
    max_skew_ns: float
    max_buf_margin_ns: float = 0.05


class PhysicalConfig(BaseModel):
    """Per-design physical implementation configuration.

    Pure function of (microarchitecture, technology config). Never contains
    results — only the inputs a real OpenROAD run would consume.
    """

    design_id: str
    pdk_name: str
    standard_cell_library: str
    clock_period_ns: float
    floorplan: FloorplanParams
    cts: CtsParams
    routing_layers: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)


class StageStatus(BaseModel):
    """One physical stage's honest outcome."""

    stage: str
    status: str  # BLOCKED / NOT_RUN / FAILED / PASSED
    reason: str = ""
    metrics: dict[str, float] = Field(default_factory=dict)  # empty unless a real tool ran


class PhysicalManifest(BaseModel):
    """Manifest binding physical-design plans (or BLOCKED statuses) to inputs."""

    design_id: str
    rtl_architecture_hash: str
    synthesis_config_hash: str
    technology_schema_version: int = 1
    physical_schema_version: int = 1
    status: str = "NOT_RUN"  # aggregate: BLOCKED until a real toolchain runs
    tool: str = "openroad"
    tool_path: str | None = None
    config: PhysicalConfig | None = None
    stages: list[StageStatus] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)

    def stages_dict(self) -> dict[str, dict[str, str]]:
        """Status + reason per physical stage, for signoff/release consumption."""
        return {s.stage: {"status": s.status, "reason": s.reason} for s in self.stages}

    def stage(self, name: str) -> StageStatus | None:
        return next((s for s in self.stages if s.stage == name), None)
