from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ParameterSpec(BaseModel):
    """One architecture parameter with full metadata.

    Every field carries: name, type, unit (where applicable), legal range,
    description, source and provenance — the canonical contract a hardware
    engineer needs to interpret the intended architecture.
    """

    name: str
    path: str
    value: Any
    field_type: str
    unit: str | None = None
    legal_min: int | float | None = None
    legal_max: int | float | None = None
    description: str
    source: str
    provenance: dict[str, Any] = Field(default_factory=dict)


class SpecificationSection(BaseModel):
    """A named group of parameters (e.g. ``compute``, ``memory``)."""

    name: str
    title: str
    source: str
    parameters: list[ParameterSpec] = Field(default_factory=list)


class ArchitectureSpecification(BaseModel):
    """Canonical, deterministic, machine-readable description of a Design."""

    design_id: str
    architecture_schema_version: int
    domain: str
    generation: int = 0
    parent_ids: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
    specification_schema_version: int = 1
    generator_version: str = "1.0.0"
    sections: list[SpecificationSection] = Field(default_factory=list)