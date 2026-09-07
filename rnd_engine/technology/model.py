"""Technology/PDK abstraction models (Phase G, toolless scope)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PdkCorner(BaseModel):
    """One process/voltage/temperature corner declared by a PDK profile."""

    name: str
    process: str  # e.g. "typical", "slow", "fast"
    voltage_v: float
    temperature_c: float


class PdkProfile(BaseModel):
    """Declarative metadata for a technology/PDK target.

    A profile is *declared*, not *installed*: its presence in the registry
    says nothing about whether the PDK files exist on this machine —
    ``pdk_installed`` in the technology gate is the only source of truth.
    """

    name: str  # e.g. "sky130A", "gf180mcuC"
    node_nm: int
    open_source: bool
    standard_cell_libraries: list[str] = Field(default_factory=list)
    metal_stack: list[str] = Field(default_factory=list)
    voltage_range: tuple[float, float] = (1.0, 1.0)
    corners: list[PdkCorner] = Field(default_factory=list)
    notes: str = ""


class TechnologyConfig(BaseModel):
    """Per-design technology binding, derived from the microarchitecture."""

    design_id: str
    pdk_name: str
    node_nm: int
    voltage_v: float
    standard_cell_library: str
    corners: list[PdkCorner] = Field(default_factory=list)
    clock_period_ns: float
    open_source: bool
    provenance: dict[str, Any] = Field(default_factory=dict)


class TechnologyManifest(BaseModel):
    """Manifest binding a technology target (or BLOCKED status) to its inputs."""

    design_id: str
    rtl_architecture_hash: str
    synthesis_config_hash: str
    technology_schema_version: int = 1
    status: str = "NOT_RUN"  # PASSED / BLOCKED / NOT_RUN
    pdk_installed: bool = False
    config: TechnologyConfig | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)
