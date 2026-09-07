from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ..models import (
    Design,
    HardwareStrategy,
    Interactions,
    Representation,
    Structure,
    SynthesizedComputation,
    Transformation,
)
from ..reproducibility import canonical_json_bytes
from .catalog import FIELD_CATALOG
from .model import ArchitectureSpecification, ParameterSpec, SpecificationSection

SPECIFICATION_SCHEMA_VERSION: int = 1
GENERATOR_VERSION: str = "1.0.0"

#: section name -> output file name
SECTION_FILENAMES: dict[str, str] = {
    "architecture": "architecture.json",
    "compute": "compute.json",
    "memory": "memory.json",
    "interfaces": "interfaces.json",
    "clock_reset": "clock_reset.json",
    "control": "control.json",
    "parameters": "parameters.json",
}


class SpecificationError(RuntimeError):
    """Raised when a Design cannot be converted into a specification."""


def _bounds(field_info: Any) -> tuple[int | float | None, int | float | None]:
    """Extract inclusive legal [min, max] from pydantic field metadata."""
    low: int | float | None = None
    high: int | float | None = None
    for meta in getattr(field_info, "metadata", ()) or ():
        g = getattr(meta, "ge", None)
        if g is not None and low is None:
            low = g
        h = getattr(meta, "le", None)
        if h is not None and high is None:
            high = h
    return low, high


def _json_safe(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if hasattr(value, "value"):  # Enum
        return _json_safe(value.value)
    return str(value)


def _field_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "string"
    if isinstance(value, (list, tuple)):
        return "list"
    if isinstance(value, dict):
        return "json"
    return type(value).__name__


def _field_spec(cls: type[Any], obj: Any, name: str, prefix: str) -> ParameterSpec:
    """Build a ParameterSpec for a single model field with live constraints."""
    path = f"{prefix}.{name}"
    info = cls.model_fields[name]
    value = _json_safe(getattr(obj, name))
    unit, description = FIELD_CATALOG.get(
        path, (None, f"No catalog description for {path}.")
    )
    low, high = _bounds(info)
    return ParameterSpec(
        name=name,
        path=path,
        value=value,
        field_type=_field_type(value),
        unit=unit,
        legal_min=low,
        legal_max=high,
        description=description,
        source=f"design.{path}",
    )


def _identity_parameters(design: Design) -> list[ParameterSpec]:
    provenance = design.provenance or {}
    search_config = provenance.get("search_config") or {}
    objective_config = provenance.get("objective_config")
    items: list[tuple[str, Any, str, str, str]] = [
        ("design_id", design.id, "string", "Content-addressed design identifier.", "design.id"),
        ("domain", design.domain.value, "string", "Processor domain target.", "design.domain"),
        ("architecture_schema_version", design.architecture_schema_version, "integer",
         "Version of the Design schema used by the generator.", "design.architecture_schema_version"),
        ("generation", design.generation, "integer",
         "Generation in which the design was produced (0 = root).", "design.generation"),
        ("parent_ids", list(design.parent_ids), "list",
         "Immediate parent design IDs (empty for roots).", "design.parent_ids"),
        ("seed", search_config.get("seed"), "integer",
         "Search RNG seed that generated the design.", "provenance.search_config.seed"),
        ("search_engine", search_config.get("engine"), "string",
         "Search engine implementation.", "provenance.search_config.engine"),
        ("rng", search_config.get("rng"), "string",
         "Random number generator implementation.", "provenance.search_config.rng"),
        ("configuration_fingerprint", provenance.get("configuration_fingerprint"), "string",
         "Stable fingerprint of the search + objective configuration.", "provenance.configuration_fingerprint"),
        ("objective_config", objective_config, "json",
         "Objective (Omega) configuration snapshot.", "provenance.objective_config"),
        ("hardware.target", design.hardware.target, "string",
         "Target hardware strategy (mirrors domain).", "design.hardware.target"),
    ]
    output: list[ParameterSpec] = []
    for name, value, field_type, description, source in items:
        path = f"hardware.{name}" if name == "hardware.target" else f"architecture.{name}"
        output.append(
            ParameterSpec(
                name=name,
                path=path,
                value=_json_safe(value),
                field_type=field_type,
                unit=None,
                legal_min=None,
                legal_max=None,
                description=description,
                source=source,
            )
        )
    return output


def build_specification(design: Design) -> ArchitectureSpecification:
    """Deterministically convert a Design into its canonical specification."""
    if not design.id:
        raise SpecificationError(
            "Design has no id; generate/label the design before specifying it."
        )

    rep = design.representation
    stru = design.structure
    inter = design.interactions
    syn = design.synthesized
    hw = design.hardware
    t = design.transformations[0] if design.transformations else None

    identity = _identity_parameters(design)

    compute = [
        _field_spec(Representation, rep, "isa_width", "representation"),
        _field_spec(Representation, rep, "vector_width", "representation"),
        _field_spec(Representation, rep, "pipeline_depth", "representation"),
        _field_spec(Representation, rep, "issue_width", "representation"),
        _field_spec(Representation, rep, "execution_units", "representation"),
        _field_spec(Representation, rep, "register_count", "representation"),
        _field_spec(SynthesizedComputation, syn, "parallel_lanes", "synthesized"),
        _field_spec(SynthesizedComputation, syn, "tensor_units", "synthesized"),
        _field_spec(SynthesizedComputation, syn, "specialized_units", "synthesized"),
    ]

    memory = [
        _field_spec(Structure, stru, "l1_kb", "structure"),
        _field_spec(Structure, stru, "l2_kb", "structure"),
        _field_spec(Structure, stru, "l3_kb", "structure"),
        _field_spec(Structure, stru, "cache_line_bytes", "structure"),
        _field_spec(Structure, stru, "memory_channels", "structure"),
    ]

    interfaces = [
        _field_spec(Structure, stru, "interconnect_width", "structure"),
        _field_spec(HardwareStrategy, hw, "parallel_blocks", "hardware"),
    ]

    clock_reset = [
        _field_spec(SynthesizedComputation, syn, "clock_ghz", "synthesized"),
        _field_spec(HardwareStrategy, hw, "voltage", "hardware"),
        _field_spec(HardwareStrategy, hw, "frequency_scaling", "hardware"),
        _field_spec(HardwareStrategy, hw, "technology_nm", "hardware"),
    ]

    control = [
        _field_spec(Interactions, inter, "prefetch_strength", "interactions"),
        _field_spec(Interactions, inter, "branch_predictor", "interactions"),
        _field_spec(Interactions, inter, "data_reuse", "interactions"),
        _field_spec(Interactions, inter, "parallelism", "interactions"),
        _field_spec(Interactions, inter, "fusion", "interactions"),
    ]
    if t is not None:
        control.extend(
            [
                _field_spec(Transformation, t, "loop_tiling", "transformations"),
                _field_spec(Transformation, t, "unroll_factor", "transformations"),
                _field_spec(Transformation, t, "kernel_fusion", "transformations"),
                _field_spec(Transformation, t, "vectorization", "transformations"),
            ]
        )

    all_parameters = compute + memory + interfaces + clock_reset + control + identity

    sections = [
        SpecificationSection(
            name="architecture",
            title="Architecture Identity & Provenance",
            source="design + provenance",
            parameters=identity,
        ),
        SpecificationSection(
            name="compute",
            title="Compute Resources",
            source="design.representation + design.synthesized",
            parameters=compute,
        ),
        SpecificationSection(
            name="memory",
            title="Memory System",
            source="design.structure",
            parameters=memory,
        ),
        SpecificationSection(
            name="interfaces",
            title="Interfaces & Interconnect",
            source="design.structure + design.hardware",
            parameters=interfaces,
        ),
        SpecificationSection(
            name="clock_reset",
            title="Clock, Reset & Technology Strategy",
            source="design.synthesized + design.hardware",
            parameters=clock_reset,
        ),
        SpecificationSection(
            name="control",
            title="Control & Dataflow Characteristics",
            source="design.interactions + design.transformations",
            parameters=control,
        ),
        SpecificationSection(
            name="parameters",
            title="Complete Parameter Listing",
            source="all design fields",
            parameters=all_parameters,
        ),
    ]

    return ArchitectureSpecification(
        design_id=design.id,
        architecture_schema_version=design.architecture_schema_version,
        domain=str(design.domain.value),
        generation=design.generation,
        parent_ids=list(design.parent_ids),
        provenance=design.provenance or {},
        specification_schema_version=SPECIFICATION_SCHEMA_VERSION,
        generator_version=GENERATOR_VERSION,
        sections=sections,
    )
def specification_hash(spec: ArchitectureSpecification) -> str:
    """Deterministic content hash (SHA-256, 128-bit) of a specification."""
    payload = spec.model_dump(mode="json")
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()[:32]


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_specification_files(
    spec: ArchitectureSpecification, output_dir: str | Path
) -> dict[str, str]:
    """Write one JSON file per section plus an index; returns name -> sha256."""
    out = Path(output_dir)
    spec_dir = out / "specification"
    spec_dir.mkdir(parents=True, exist_ok=True)
    files: dict[str, str] = {}

    for section in spec.sections:
        fname = SECTION_FILENAMES.get(section.name, f"{section.name}.json")
        data = {
            "section": section.name,
            "title": section.title,
            "source": section.source,
            "design_id": spec.design_id,
            "parameters": [p.model_dump(mode="json") for p in section.parameters],
        }
        path = spec_dir / fname
        path.write_text(
            json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        files[section.name] = _file_sha256(path)

    index = {
        "design_id": spec.design_id,
        "architecture_schema_version": spec.architecture_schema_version,
        "specification_schema_version": spec.specification_schema_version,
        "generator_version": spec.generator_version,
        "specification_hash": specification_hash(spec),
        "files": {
            name: {"file": SECTION_FILENAMES[name], "sha256": digest}
            for name, digest in files.items()
        },
    }
    index_path = spec_dir / "index.json"
    index_path.write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    files["index"] = _file_sha256(index_path)
    return files


def write_markdown(spec: ArchitectureSpecification, path: str | Path) -> None:
    """Write a human-readable architecture specification document."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Architecture Specification",
        "",
        f"- **design_id**: `{spec.design_id}`",
        f"- **domain**: {spec.domain}",
        f"- **generation**: {spec.generation}",
        f"- **architecture_schema_version**: {spec.architecture_schema_version}",
        f"- **specification_schema_version**: {spec.specification_schema_version}",
        f"- **generator_version**: {spec.generator_version}",
        f"- **specification_hash**: `{specification_hash(spec)}`",
        "",
        "## Lineage",
        "",
        "| parent_ids |",
        "| --- |",
    ]
    if spec.parent_ids:
        for pid in spec.parent_ids:
            lines.append(f"| `{pid}` |")
    else:
        lines.append("| *(root candidate)* |")
    lines.append("")
    lines += [
        "## Provenance",
        "",
        "```json",
        json.dumps(spec.provenance or {}, indent=2, sort_keys=True),
        "```",
        "",
    ]
    for section in spec.sections:
        lines += [
            f"## {section.title} (`{section.name}`)",
            "",
            "| field | value | unit | legal range | type | description | source |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
        for p in section.parameters:
            low = p.legal_min if p.legal_min is not None else "-"
            high = p.legal_max if p.legal_max is not None else "-"
            lines.append(
                f"| `{p.path}` | `{p.value}` | {p.unit or '-'} | "
                f"[{low}, {high}] | {p.field_type} | {p.description} | `{p.source}` |"
            )
        lines.append("")
    target.write_text("\n".join(lines), encoding="utf-8")