from __future__ import annotations

# Field catalog: path -> (unit, human-readable description).
#
# The path convention is "<design.<model>.<field>" e.g.
# ``representation.isa_width`` corresponds to ``Design.representation.isa_width``.
# Legal ranges are NOT duplicated here — they are introspected live from the
# pydantic field constraints so this catalog and the Design schema cannot drift.
FIELD_CATALOG: dict[str, tuple[str | None, str]] = {
    "representation.isa_width": ("bit", "Instruction-set address/data width."),
    "representation.vector_width": ("bit", "Widest SIMD/vector datapath."),
    "representation.pipeline_depth": ("stage", "Baseline pipeline depth."),
    "representation.issue_width": ("inst", "Instructions issued per cycle."),
    "representation.execution_units": ("unit", "General-purpose execution units."),
    "representation.register_count": ("reg", "Architectural register file entries."),
    "structure.l1_kb": ("kB", "L1 cache capacity."),
    "structure.l2_kb": ("kB", "L2 cache capacity."),
    "structure.l3_kb": ("kB", "L3/shared cache capacity."),
    "structure.cache_line_bytes": ("B", "Cache line size."),
    "structure.memory_channels": ("chan", "DRAM memory channels."),
    "structure.interconnect_width": ("bit", "On-chip datapath interconnect width."),
    "interactions.prefetch_strength": (None, "Prefetch aggressiveness (0..1)."),
    "interactions.branch_predictor": (None, "Branch-predictor capability (0..1)."),
    "interactions.data_reuse": (None, "Data-reuse / locality exploitation (0..1)."),
    "interactions.parallelism": (None, "Exposed parallelism (0..1)."),
    "interactions.fusion": (None, "Kernel fusion intensity (0..1)."),
    "transformations.loop_tiling": ("elem", "Loop tiling factor."),
    "transformations.unroll_factor": ("x", "Loop unroll factor."),
    "transformations.kernel_fusion": (None, "Kernel fusion intensity (0..1)."),
    "transformations.vectorization": (None, "Vectorization intensity (0..1)."),
    "synthesized.parallel_lanes": ("lane", "Parallel processing lanes."),
    "synthesized.tensor_units": ("unit", "Tensor/accelerator units."),
    "synthesized.specialized_units": ("unit", "Specialized compute units."),
    "synthesized.clock_ghz": ("GHz", "Target clock frequency."),
    "hardware.technology_nm": ("nm", "Technology node (feature size)."),
    "hardware.voltage": ("V", "Operating voltage."),
    "hardware.frequency_scaling": (None, "Relative frequency-scaling factor."),
    "hardware.parallel_blocks": ("block", "Parallel replicated blocks."),
    "hardware.target": (None, "Target hardware strategy (mirrors domain)."),
}