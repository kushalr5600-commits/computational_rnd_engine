"""Canonical architecture specification layer.

Deterministically converts a ``Design`` into a machine-readable, provenance-
carrying architecture specification (``ArchitectureSpecification``) whose
contents are hashed for traceability (``specification_hash``). Every parameter
records name, type, unit, legal range, description, source and provenance.
"""

from ..models import ARCHITECTURE_SCHEMA_VERSION
from .catalog import FIELD_CATALOG
from .generator import (
    SPECIFICATION_SCHEMA_VERSION,
    SpecificationError,
    build_specification,
    specification_hash,
    write_markdown,
    write_specification_files,
)
from .model import (
    ArchitectureSpecification,
    ParameterSpec,
    SpecificationSection,
)

__all__ = [
    "ARCHITECTURE_SCHEMA_VERSION",
    "FIELD_CATALOG",
    "SPECIFICATION_SCHEMA_VERSION",
    "ArchitectureSpecification",
    "ParameterSpec",
    "SpecificationError",
    "SpecificationSection",
    "build_specification",
    "specification_hash",
    "write_markdown",
    "write_specification_files",
]