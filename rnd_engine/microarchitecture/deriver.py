from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ..reproducibility import canonical_json_bytes
from ..specification import ArchitectureSpecification, specification_hash
from .model import (
    CacheUnit,
    ClockResetDomain,
    ClockResetSpec,
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

MICROARCHITECTURE_SCHEMA_VERSION: int = 1
GENERATOR_VERSION: str = "1.0.0"


class MicroarchitectureError(RuntimeError):
    """Raised when a specification cannot be derived into a microarchitecture."""


def _spec_values(spec: ArchitectureSpecification) -> dict[str, Any]:
    """Map spec parameter path -> value (unique by path across sections)."""
    by_path: dict[str, Any] = {}
    for section in spec.sections:
        for p in section.parameters:
            by_path.setdefault(p.path, p.value)
    return by_path


def _local(
    v: dict[str, Any], *paths: str, default: Any | None = None
) -> Any:
    for path in paths:
        if path in v:
            return v[path]
    if default is not None:
        return default
    raise MicroarchitectureError(f"Specification missing required path: {paths}")


def _derive_pipeline(v: dict[str, Any]) -> PipelineSpec:
    isa = _local(v, "representation.isa_width")
    issue = _local(v, "representation.issue_width")
    depth = _local(v, "representation.pipeline_depth")
    vec = _local(v, "representation.vector_width")
    interconnect = _local(v, "structure.interconnect_width")

    stages = [
        PipelineStage(
            name="fetch",
            role="instruction fetch",
            cycles=1,
            width_bits=isa,
            derived_from=["representation.isa_width"],
            rule="fetch width == ISA width",
        ),
        PipelineStage(
            name="decode",
            role="instruction decode/rename",
            cycles=1,
            width_bits=isa * issue,
            derived_from=["representation.isa_width", "representation.issue_width"],
            rule="decode width == issue_width * ISA width",
        ),
        PipelineStage(
            name="issue",
            role="issue to execution ports",
            cycles=1,
            width_bits=isa * issue,
            derived_from=["representation.issue_width"],
            rule="issue ports == issue_width",
        ),
        PipelineStage(
            name="execute",
            role="integer/FP execution",
            cycles=1,
            width_bits=isa * issue,
            derived_from=["representation.issue_width", "representation.execution_units"],
            rule="execute width == issue_width datapaths (execution_units >= issue_width enforced)",
        ),
    ]
    if vec > isa:
        stages.append(
            PipelineStage(
                name="vector",
                role="vector datapath",
                cycles=1,
                width_bits=vec,
                derived_from=["representation.vector_width"],
                rule="vector stage present only when vector_width > isa_width",
            )
        )
    stages.extend(
        [
            PipelineStage(
                name="memory",
                role="memory access",
                cycles=1,
                width_bits=interconnect,
                derived_from=["structure.interconnect_width"],
                rule="memory stage width == interconnect width",
            ),
            PipelineStage(
                name="retire",
                role="in-order retirement",
                cycles=1,
                width_bits=isa * issue,
                derived_from=["representation.issue_width"],
                rule="retire width == issue_width * ISA width (in-order)",
            ),
        ]
    )

    # The architecture `pipeline_depth` is a target; the derived floor expressed
    # in stage count is the classic in-order multi-stage pipeline.
    floor_depth = len(stages)
    effective = max(floor_depth, depth)
    return PipelineSpec(
        depth_stages=effective,
        slots_per_stage=issue,
        stages=stages,
    )


def _derive_datapaths(v: dict[str, Any]) -> DatapathsSpec:
    isa = _local(v, "representation.isa_width")
    issue = _local(v, "representation.issue_width")
    execution = _local(v, "representation.execution_units")
    regs = _local(v, "representation.register_count")
    vec = _local(v, "representation.vector_width")
    lanes = _local(v, "synthesized.parallel_lanes")
    tensor = _local(v, "synthesized.tensor_units")
    special = _local(v, "synthesized.specialized_units")

    datapaths = [
        Datapath(
            name="alu",
            kind="alu",
            count=execution,
            width_bits=isa,
            derived_from=["representation.execution_units", "representation.isa_width"],
            rule="one ALU per execution_unit",
        ),
        Datapath(
            name="register_file",
            kind="register_file",
            count=1,
            width_bits=isa,
            depth=regs,
            derived_from=["representation.register_count", "representation.isa_width"],
            rule="architectural register file with register_count entries",
        ),
    ]
    if vec > isa:
        datapaths.append(
            Datapath(
                name="vector_unit",
                kind="vector",
                count=1,
                width_bits=vec,
                depth=lanes,
                derived_from=["representation.vector_width", "synthesized.parallel_lanes"],
                rule="single vector unit of vector_width bits, parallel_lanes lanes",
            )
        )
    if tensor > 0:
        datapaths.append(
            Datapath(
                name="tensor_units",
                kind="tensor",
                count=tensor,
                width_bits=isa,
                derived_from=["synthesized.tensor_units"],
                rule="tensor_units tensor/systolic units",
            )
        )
    if special > 0:
        datapaths.append(
            Datapath(
                name="specialized_units",
                kind="specialized",
                count=special,
                width_bits=isa * 2,
                derived_from=["synthesized.specialized_units"],
                rule="specialized_units specialized accelerators (2*ISA datapath)",
            )
        )
    # lanes is recorded on the vector path; if no vector path we still surface it.
    return DatapathsSpec(
        issue_width=issue,
        register_file_entries=regs,
        register_file_read_ports=max(1, issue * 2),
        register_file_write_ports=max(1, issue),
        datapaths=datapaths,
    )


def _assoc_ways(capacity_kb: int, line_bytes: int, default: int) -> int:
    """Pick associativity from capacity (small caches fewer ways)."""
    if capacity_kb <= 0:
        return default
    if capacity_kb < 32:
        return 2
    if capacity_kb < 128:
        return 4
    return default


def _sets(capacity_kb: int, line_bytes: int, ways: int) -> int | None:
    if capacity_kb <= 0 or ways <= 0:
        return None
    lines = capacity_kb * 1024 // line_bytes
    return max(1, lines // ways)


def _derive_memories(v: dict[str, Any]) -> MemoriesSpec:
    l1 = _local(v, "structure.l1_kb")
    l2 = _local(v, "structure.l2_kb")
    l3 = _local(v, "structure.l3_kb")
    line = _local(v, "structure.cache_line_bytes")
    channels = _local(v, "structure.memory_channels")
    interconnect = _local(v, "structure.interconnect_width")

    caches = [
        CacheUnit(
            name="l1",
            level="L1",
            capacity_kb=l1,
            line_bytes=line,
            ways=_assoc_ways(l1, line, 4),
            derived_from=["structure.l1_kb", "structure.cache_line_bytes"],
            rule="L1 capacity and line from spec; associativity scaled by capacity",
        ),
        CacheUnit(
            name="l2",
            level="L2",
            capacity_kb=l2,
            line_bytes=line,
            ways=_assoc_ways(l2, line, 8),
            derived_from=["structure.l2_kb", "structure.cache_line_bytes"],
            rule="L2 capacity and line from spec",
        ),
    ]
    if l3 > 0:
        caches.append(
            CacheUnit(
                name="l3",
                level="L3",
                capacity_kb=l3,
                line_bytes=line,
                ways=_assoc_ways(l3, line, 16),
                derived_from=["structure.l3_kb", "structure.cache_line_bytes"],
                rule="L3 instantiated only when spec L3 capacity > 0",
            )
        )
    for cache in caches:
        cache.sets = _sets(cache.capacity_kb, line, cache.ways)

    controller = MemoryResource(
        name="memory_controller",
        kind="dram",
        channels=channels,
        width_bits=interconnect,
        instantiated=True,
        derived_from=["structure.memory_channels", "structure.interconnect_width"],
        rule="DRAM controller with memory_channels channels",
    )
    return MemoriesSpec(caches=caches, controllers=[controller])


def _derive_control(v: dict[str, Any]) -> ControlSpec:
    issue = _local(v, "representation.issue_width")
    branch = _local(v, "interactions.branch_predictor")
    prefetch = _local(v, "interactions.prefetch_strength")
    fusion = _local(v, "interactions.fusion")
    data_reuse = _local(v, "interactions.data_reuse")
    vec = _local(v, "representation.vector_width")

    mechanisms = [
        ControlMechanism(
            name="in_order_issue",
            kind="issue",
            width_bits=issue,
            derived_from=["representation.issue_width"],
            rule="in-order issue of issue_width instructions/cycle",
        ),
        ControlMechanism(
            name="branch_predictor",
            kind="branch_predict",
            strength=branch,
            derived_from=["interactions.branch_predictor"],
            rule="branch-predictor capability scaled by spec strength",
        ),
        ControlMechanism(
            name="prefetch",
            kind="prefetch",
            strength=prefetch,
            derived_from=["interactions.prefetch_strength"],
            rule="prefetch aggressiveness from spec strength",
        ),
        ControlMechanism(
            name="in_order_retire",
            kind="retire",
            width_bits=issue,
            derived_from=["representation.issue_width"],
            rule="in-order retire of issue_width instructions/cycle",
        ),
        ControlMechanism(
            name="data_reuse",
            kind="dataflow",
            strength=data_reuse,
            derived_from=["interactions.data_reuse"],
            rule="data-reuse/locality control strength from spec",
        ),
        ControlMechanism(
            name="kernel_fusion",
            kind="dataflow",
            strength=fusion,
            derived_from=["interactions.fusion"],
            rule="kernel-fusion control strength from spec",
        ),
    ]
    if vec > _local(v, "representation.isa_width"):
        mechanisms.append(
            ControlMechanism(
                name="vector_issue",
                kind="vector",
                width_bits=vec,
                derived_from=["representation.vector_width"],
                rule="vector instruction issue when vector datapath exists",
            )
        )
    return ControlSpec(mechanisms=mechanisms)


def _derive_clock_reset(v: dict[str, Any]) -> ClockResetSpec:
    clock = _local(v, "synthesized.clock_ghz")
    voltage = _local(v, "hardware.voltage")
    tech = _local(v, "hardware.technology_nm")
    freq_scale = _local(v, "hardware.frequency_scaling")

    return ClockResetSpec(
        domains=[
            ClockResetDomain(
                name="core",
                frequency_ghz=round(clock * freq_scale, 3),
                voltage_v=voltage,
                technology_nm=tech,
                derived_from=[
                    "synthesized.clock_ghz",
                    "hardware.frequency_scaling",
                    "hardware.voltage",
                    "hardware.technology_nm",
                ],
                rule="core domain frequency = clock_ghz * frequency_scaling; voltage/technology from spec",
            ),
            ClockResetDomain(
                name="memory",
                frequency_ghz=round(clock * freq_scale * 0.5, 3),
                voltage_v=voltage,
                technology_nm=tech,
                derived_from=["synthesized.clock_ghz", "hardware.frequency_scaling"],
                rule="memory domain runs at half the core frequency (uncore divider=2)",
            ),
        ]
    )


def _derive_interfaces(v: dict[str, Any]) -> InterfacesSpec:
    isa = _local(v, "representation.isa_width")
    interconnect = _local(v, "structure.interconnect_width")
    channels = _local(v, "structure.memory_channels")
    vec = _local(v, "representation.vector_width")
    tensor = _local(v, "synthesized.tensor_units")
    special = _local(v, "synthesized.specialized_units")

    ports = [
        InterfacePort(
            name="instruction_fetch",
            direction="master",
            width_bits=isa,
            count=1,
            derived_from=["representation.isa_width"],
            rule="instruction fetch port sized to ISA width",
        ),
        InterfacePort(
            name="data_memory",
            direction="master",
            width_bits=interconnect,
            count=1,
            derived_from=["structure.interconnect_width"],
            rule="data memory port sized to interconnect width",
        ),
        InterfacePort(
            name="system_interconnect",
            direction="master",
            width_bits=interconnect,
            count=1,
            derived_from=["structure.interconnect_width"],
            rule="system interconnect port",
        ),
        InterfacePort(
            name="dram",
            direction="master",
            width_bits=interconnect,
            count=channels,
            derived_from=["structure.memory_channels"],
            rule="one DRAM port per memory channel",
        ),
    ]
    if vec > isa:
        ports.append(
            InterfacePort(
                name="vector",
                direction="internal",
                width_bits=vec,
                count=1,
                derived_from=["representation.vector_width"],
                rule="vector datapath interface present only when vector_width > isa_width",
            )
        )
    if tensor > 0 or special > 0:
        ports.append(
            InterfacePort(
                name="accelerator",
                direction="internal",
                width_bits=max(interconnect, vec),
                count=1,
                derived_from=["synthesized.tensor_units", "synthesized.specialized_units"],
                rule="accelerator interface present when tensor or specialized units exist",
            )
        )
    return InterfacesSpec(ports=ports)


def derive_microarchitecture(
    spec: ArchitectureSpecification,
) -> MicroArchitectureSpec:
    """Deterministically derive a MicroArchitectureSpec from a specification.

    Pure function of the specification parameters — no RNG, no environment
    dependency — so the same specification always yields the same
    microarchitecture and the same ``microarchitecture_hash``.
    """
    if not spec.design_id:
        raise MicroarchitectureError("Specification has no design_id.")

    v = _spec_values(spec)
    return MicroArchitectureSpec(
        design_id=spec.design_id,
        architecture_schema_version=spec.architecture_schema_version,
        specification_hash=specification_hash(spec),
        microarchitecture_schema_version=MICROARCHITECTURE_SCHEMA_VERSION,
        generator_version=GENERATOR_VERSION,
        domain=spec.domain,
        provenance=spec.provenance,
        pipeline=_derive_pipeline(v),
        datapaths=_derive_datapaths(v),
        memories=_derive_memories(v),
        interfaces=_derive_interfaces(v),
        control=_derive_control(v),
        clock_reset=_derive_clock_reset(v),
    )


def microarchitecture_hash(micro: MicroArchitectureSpec) -> str:
    """Deterministic content hash (SHA-256, 128-bit) of a microarchitecture."""
    payload = micro.model_dump(mode="json")
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()[:32]


def _json_dumps(value: dict[str, Any]) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_microarchitecture_files(
    micro: MicroArchitectureSpec, output_dir: str | Path
) -> dict[str, str]:
    """Write one JSON file per subsystem plus an index; returns name -> sha256."""
    out = Path(output_dir)
    spec_dir = out / "microarchitecture"
    spec_dir.mkdir(parents=True, exist_ok=True)
    files: dict[str, str] = {}

    sections = {
        "pipeline": micro.pipeline.model_dump(mode="json"),
        "datapaths": micro.datapaths.model_dump(mode="json"),
        "memories": micro.memories.model_dump(mode="json"),
        "interfaces": micro.interfaces.model_dump(mode="json"),
        "control": micro.control.model_dump(mode="json"),
        "clock_reset": micro.clock_reset.model_dump(mode="json"),
    }
    for name, data in sections.items():
        path = spec_dir / f"{name}.json"
        path.write_text(_json_dumps(data), encoding="utf-8")
        files[name] = _file_sha256(path)

    index = {
        "design_id": micro.design_id,
        "architecture_schema_version": micro.architecture_schema_version,
        "specification_hash": micro.specification_hash,
        "microarchitecture_schema_version": micro.microarchitecture_schema_version,
        "generator_version": micro.generator_version,
        "microarchitecture_hash": microarchitecture_hash(micro),
        "files": {
            name: {"file": f"{name}.json", "sha256": digest}
            for name, digest in files.items()
        },
    }
    index_path = spec_dir / "index.json"
    index_path.write_text(_json_dumps(index), encoding="utf-8")
    files["index"] = _file_sha256(index_path)
    return files


def write_microarchitecture_markdown(
    micro: MicroArchitectureSpec, path: str | Path
) -> None:
    """Write a human-readable microarchitecture specification document."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Microarchitecture Specification",
        "",
        f"- **design_id**: `{micro.design_id}`",
        f"- **domain**: {micro.domain}",
        f"- **architecture_schema_version**: {micro.architecture_schema_version}",
        f"- **specification_hash**: `{micro.specification_hash}`",
        f"- **microarchitecture_schema_version**: {micro.microarchitecture_schema_version}",
        f"- **generator_version**: {micro.generator_version}",
        f"- **microarchitecture_hash**: `{microarchitecture_hash(micro)}`",
        "",
        "## Pipeline",
        "",
        "| stage | role | cycles | width (bit) | derived from | rule |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for stage in micro.pipeline.stages:
        lines.append(
            f"| {stage.name} | {stage.role} | {stage.cycles} | {stage.width_bits} | "
            f"{', '.join(stage.derived_from)} | {stage.rule} |"
        )
    lines.append("")
    lines += [
        (
            f"**depth_stages**: {micro.pipeline.depth_stages}  ·  "
            f"**slots_per_stage**: {micro.pipeline.slots_per_stage}"
        ),
        "",
        "## Datapaths",
        "",
        "| name | kind | count | width (bit) | depth | derived from | rule |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for d in micro.datapaths.datapaths:
        lines.append(
            f"| {d.name} | {d.kind} | {d.count} | {d.width_bits} | {d.depth if d.depth is not None else '-'} | "
            f"{', '.join(d.derived_from)} | {d.rule} |"
        )
    lines.append("")
    lines += [
        "## Memories",
        "",
        "| name | level | capacity (kB) | line (B) | ways | sets | instantiated | rule |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for c in micro.memories.caches:
        lines.append(
            f"| {c.name} | {c.level} | {c.capacity_kb} | {c.line_bytes} | "
            f"{c.ways if c.ways is not None else '-'} | {c.sets if c.sets is not None else '-'} | "
            f"{c.instantiated} | {c.rule} |"
        )
    for r in micro.memories.controllers:
        lines.append(
            f"| {r.name} | {r.kind} | - | - | - | - | {r.instantiated} | {r.rule} |"
        )
    lines.append("")
    lines += [
        "## Interfaces",
        "",
        "| name | direction | width (bit) | count | rule |",
        "| --- | --- | --- | --- | --- |",
    ]
    for p in micro.interfaces.ports:
        lines.append(
            f"| {p.name} | {p.direction} | {p.width_bits} | {p.count} | {p.rule} |"
        )
    lines.append("")
    lines += [
        "## Control",
        "",
        "| name | kind | strength | width (bit) | rule |",
        "| --- | --- | --- | --- | --- |",
    ]
    for m in micro.control.mechanisms:
        strength = f"{m.strength:.3f}" if m.strength is not None else "-"
        width = f"{m.width_bits}" if m.width_bits is not None else "-"
        lines.append(f"| {m.name} | {m.kind} | {strength} | {width} | {m.rule} |")
    lines.append("")
    lines += [
        "## Clock / Reset",
        "",
        "| domain | frequency (GHz) | voltage (V) | technology (nm) | rule |",
        "| --- | --- | --- | --- | --- |",
    ]
    for dom in micro.clock_reset.domains:
        lines.append(
            f"| {dom.name} | {dom.frequency_ghz} | {dom.voltage_v} | {dom.technology_nm} | {dom.rule} |"
        )
    lines.append("")
    lines += [
        "## Provenance",
        "",
        "```json",
        json.dumps(micro.provenance or {}, indent=2, sort_keys=True),
        "```",
        "",
    ]
    target.write_text("\n".join(lines), encoding="utf-8")