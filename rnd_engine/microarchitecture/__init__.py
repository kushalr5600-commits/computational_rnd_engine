"""Microarchitecture derivation layer.

Deterministically converts an ``ArchitectureSpecification`` into a concrete
``MicroArchitectureSpec`` (pipeline, datapaths, memories, interfaces, control,
clock/reset). Every element carries ``derived_from`` spec paths and a ``rule``
so each hardware decision traces back to the architecture candidate.
"""

from ..models import ARCHITECTURE_SCHEMA_VERSION
from .deriver import (
    MICROARCHITECTURE_SCHEMA_VERSION,
    MicroarchitectureError,
    derive_microarchitecture,
    microarchitecture_hash,
    write_microarchitecture_files,
    write_microarchitecture_markdown,
)
from .model import (
    CacheUnit,
    ClockResetDomain,
    ControlMechanism,
    ControlSpec,
    Datapath,
    DatapathsSpec,
    InterfacePort,
    InterfacesSpec,
    MemoriesSpec,
    MemoryResource,
    MicroArchitectureSpec,
    PipelineSpec,
    PipelineStage,
)

__all__ = [
    "ARCHITECTURE_SCHEMA_VERSION",
    "MICROARCHITECTURE_SCHEMA_VERSION",
    "CacheUnit",
    "ClockResetDomain",
    "ControlMechanism",
    "ControlSpec",
    "Datapath",
    "DatapathsSpec",
    "InterfacePort",
    "InterfacesSpec",
    "MemoriesSpec",
    "MemoryResource",
    "MicroArchitectureSpec",
    "MicroarchitectureError",
    "PipelineSpec",
    "PipelineStage",
    "derive_microarchitecture",
    "microarchitecture_hash",
    "write_microarchitecture_files",
    "write_microarchitecture_markdown",
]