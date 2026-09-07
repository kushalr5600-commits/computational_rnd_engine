from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class PipelineStage(BaseModel):
    """One pipeline stage, with reasoning traceable to the architecture spec."""

    name: str
    role: str
    cycles: int = 1
    width_bits: int
    derived_from: list[str] = Field(default_factory=list)
    rule: str


class Datapath(BaseModel):
    """One datapath resource (ALU, vector, specialized, register file, port)."""

    name: str
    kind: str
    count: int = 1
    width_bits: int
    depth: int | None = None
    derived_from: list[str] = Field(default_factory=list)
    rule: str


class CacheUnit(BaseModel):
    """A cache hierarchy level derived from the architecture spec."""

    name: str
    level: str
    capacity_kb: int
    line_bytes: int
    ways: int | None = None
    sets: int | None = None
    instantiated: bool = True
    derived_from: list[str] = Field(default_factory=list)
    rule: str


class MemoryResource(BaseModel):
    """A memory-system resource (cache level or memory controller/DRAM)."""

    name: str
    kind: str
    channels: int = 1
    width_bits: int
    instantiated: bool = True
    derived_from: list[str] = Field(default_factory=list)
    rule: str


class InterfacePort(BaseModel):
    """A microarchitecture interface port (fetch, data, interconnect, DDR, accel)."""

    name: str
    direction: str
    width_bits: int
    count: int = 1
    derived_from: list[str] = Field(default_factory=list)
    rule: str


class ControlMechanism(BaseModel):
    """A control mechanism (issue, branch predict, prefetch, hazard, retire, vector)."""

    name: str
    kind: str
    strength: float | None = None
    width_bits: int | None = None
    derived_from: list[str] = Field(default_factory=list)
    rule: str


class ClockResetDomain(BaseModel):
    """A clock/reset domain with frequency, voltage and technology target."""

    name: str
    frequency_ghz: float
    voltage_v: float
    technology_nm: int
    derived_from: list[str] = Field(default_factory=list)
    rule: str


class PipelineSpec(BaseModel):
    """Ordered pipeline: fetch -> decode -> issue -> execute -> memory -> retire."""

    depth_stages: int
    slots_per_stage: int
    stages: list[PipelineStage] = Field(default_factory=list)


class DatapathsSpec(BaseModel):
    """Compute datapaths + register file."""

    issue_width: int
    register_file_entries: int
    register_file_read_ports: int
    register_file_write_ports: int
    datapaths: list[Datapath] = Field(default_factory=list)


class MemoriesSpec(BaseModel):
    """Cache hierarchy + memory controller."""

    caches: list[CacheUnit] = Field(default_factory=list)
    controllers: list[MemoryResource] = Field(default_factory=list)


class InterfacesSpec(BaseModel):
    """Ports visible at the microarchitecture boundary."""

    ports: list[InterfacePort] = Field(default_factory=list)


class ControlSpec(BaseModel):
    """Issue, hazards, branch predict, prefetch, and data-movement control."""

    mechanisms: list[ControlMechanism] = Field(default_factory=list)


class ClockResetSpec(BaseModel):
    """Clock/reset domains."""

    domains: list[ClockResetDomain] = Field(default_factory=list)


class MicroArchitectureSpec(BaseModel):
    """Deterministic microarchitecture derived from an ArchitectureSpecification.

    Every element records ``derived_from`` (the architecture-spec parameter
    paths) and a ``rule`` describing the derivation, so every hardware decision
    is traceable back to the architecture candidate.
    """

    design_id: str
    architecture_schema_version: int
    specification_hash: str
    microarchitecture_schema_version: int = 1
    generator_version: str = "1.0.0"
    domain: str
    provenance: dict[str, Any] = Field(default_factory=dict)
    pipeline: PipelineSpec
    datapaths: DatapathsSpec
    memories: MemoriesSpec
    interfaces: InterfacesSpec
    control: ControlSpec
    clock_reset: ClockResetSpec