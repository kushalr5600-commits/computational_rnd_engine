"""Synthesis data models (Phase F, toolless scope)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class SynthesisConfig(BaseModel):
    """Deterministic synthesis configuration for one design.

    Flow parameters (clock, libraries, tool options) live here — never
    hardcoded in the Python flow code.
    """

    design_id: str
    top_module: str = "top"
    clock_period_ns: float
    target_library: str | None = None
    source_files: list[str] = Field(default_factory=list)
    flattening: bool = True
    provenance: dict[str, Any] = Field(default_factory=dict)


class SynthesisCellStats(BaseModel):
    """Cell histogram from the Yosys ``stat`` pass."""

    number_of_wires: int | None = None
    number_of_cells: int | None = None
    cell_types: dict[str, int] = Field(default_factory=dict)


class SynthesisManifest(BaseModel):
    """Manifest binding a synthesis run (or BLOCKED status) to its inputs."""

    design_id: str
    rtl_architecture_hash: str
    synthesis_config_hash: str
    synthesis_schema_version: int = 1
    tool: str = "yosys"
    tool_path: str | None = None
    tool_version: str | None = None
    status: str = "NOT_RUN"  # PASSED / FAILED / BLOCKED / NOT_RUN
    stats: SynthesisCellStats | None = None
    netlist_path: str | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)
