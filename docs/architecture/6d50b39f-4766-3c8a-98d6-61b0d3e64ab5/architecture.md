# Architecture Specification

- **design_id**: `6d50b39f-4766-3c8a-98d6-61b0d3e64ab5`
- **domain**: heterogeneous
- **generation**: 0
- **architecture_schema_version**: 1
- **specification_schema_version**: 1
- **generator_version**: 1.0.0
- **specification_hash**: `0edf41603bf572bf288b161975cb95b8`

## Lineage

| parent_ids |
| --- |
| *(root candidate)* |

## Provenance

```json
{
  "configuration_fingerprint": "146a69d586c304df",
  "objective_config": null,
  "search_config": {
    "engine": "SearchEngine",
    "rng": "Random",
    "seed": 42
  },
  "seed": 42
}
```

## Architecture Identity & Provenance (`architecture`)

| field | value | unit | legal range | type | description | source |
| --- | --- | --- | --- | --- | --- | --- |
| `architecture.design_id` | `6d50b39f-4766-3c8a-98d6-61b0d3e64ab5` | - | [-, -] | string | Content-addressed design identifier. | `design.id` |
| `architecture.domain` | `heterogeneous` | - | [-, -] | string | Processor domain target. | `design.domain` |
| `architecture.architecture_schema_version` | `1` | - | [-, -] | integer | Version of the Design schema used by the generator. | `design.architecture_schema_version` |
| `architecture.generation` | `0` | - | [-, -] | integer | Generation in which the design was produced (0 = root). | `design.generation` |
| `architecture.parent_ids` | `[]` | - | [-, -] | list | Immediate parent design IDs (empty for roots). | `design.parent_ids` |
| `architecture.seed` | `42` | - | [-, -] | integer | Search RNG seed that generated the design. | `provenance.search_config.seed` |
| `architecture.search_engine` | `SearchEngine` | - | [-, -] | string | Search engine implementation. | `provenance.search_config.engine` |
| `architecture.rng` | `Random` | - | [-, -] | string | Random number generator implementation. | `provenance.search_config.rng` |
| `architecture.configuration_fingerprint` | `146a69d586c304df` | - | [-, -] | string | Stable fingerprint of the search + objective configuration. | `provenance.configuration_fingerprint` |
| `architecture.objective_config` | `None` | - | [-, -] | json | Objective (Omega) configuration snapshot. | `provenance.objective_config` |
| `hardware.hardware.target` | `heterogeneous` | - | [-, -] | string | Target hardware strategy (mirrors domain). | `design.hardware.target` |

## Compute Resources (`compute`)

| field | value | unit | legal range | type | description | source |
| --- | --- | --- | --- | --- | --- | --- |
| `representation.isa_width` | `128` | bit | [16, 256] | integer | Instruction-set address/data width. | `design.representation.isa_width` |
| `representation.vector_width` | `128` | bit | [32, 4096] | integer | Widest SIMD/vector datapath. | `design.representation.vector_width` |
| `representation.pipeline_depth` | `6` | stage | [2, 64] | integer | Baseline pipeline depth. | `design.representation.pipeline_depth` |
| `representation.issue_width` | `12` | inst | [1, 32] | integer | Instructions issued per cycle. | `design.representation.issue_width` |
| `representation.execution_units` | `10` | unit | [1, 128] | integer | General-purpose execution units. | `design.representation.execution_units` |
| `representation.register_count` | `64` | reg | [8, 2048] | integer | Architectural register file entries. | `design.representation.register_count` |
| `synthesized.parallel_lanes` | `32` | lane | [1, 4096] | integer | Parallel processing lanes. | `design.synthesized.parallel_lanes` |
| `synthesized.tensor_units` | `0` | unit | [0, 1024] | integer | Tensor/accelerator units. | `design.synthesized.tensor_units` |
| `synthesized.specialized_units` | `10` | unit | [0, 512] | integer | Specialized compute units. | `design.synthesized.specialized_units` |

## Memory System (`memory`)

| field | value | unit | legal range | type | description | source |
| --- | --- | --- | --- | --- | --- | --- |
| `structure.l1_kb` | `64` | kB | [4, 4096] | integer | L1 cache capacity. | `design.structure.l1_kb` |
| `structure.l2_kb` | `512` | kB | [64, 65536] | integer | L2 cache capacity. | `design.structure.l2_kb` |
| `structure.l3_kb` | `65536` | kB | [0, 524288] | integer | L3/shared cache capacity. | `design.structure.l3_kb` |
| `structure.cache_line_bytes` | `32` | B | [16, 256] | integer | Cache line size. | `design.structure.cache_line_bytes` |
| `structure.memory_channels` | `3` | chan | [1, 64] | integer | DRAM memory channels. | `design.structure.memory_channels` |

## Interfaces & Interconnect (`interfaces`)

| field | value | unit | legal range | type | description | source |
| --- | --- | --- | --- | --- | --- | --- |
| `structure.interconnect_width` | `1024` | bit | [32, 4096] | integer | On-chip datapath interconnect width. | `design.structure.interconnect_width` |
| `hardware.parallel_blocks` | `64` | block | [1, 1024] | integer | Parallel replicated blocks. | `design.hardware.parallel_blocks` |

## Clock, Reset & Technology Strategy (`clock_reset`)

| field | value | unit | legal range | type | description | source |
| --- | --- | --- | --- | --- | --- | --- |
| `synthesized.clock_ghz` | `3.44` | GHz | [0.1, 10.0] | float | Target clock frequency. | `design.synthesized.clock_ghz` |
| `hardware.voltage` | `0.79` | V | [0.3, 1.8] | float | Operating voltage. | `design.hardware.voltage` |
| `hardware.frequency_scaling` | `0.87` | - | [0.2, 4.0] | float | Relative frequency-scaling factor. | `design.hardware.frequency_scaling` |
| `hardware.technology_nm` | `14` | nm | [3, 180] | integer | Technology node (feature size). | `design.hardware.technology_nm` |

## Control & Dataflow Characteristics (`control`)

| field | value | unit | legal range | type | description | source |
| --- | --- | --- | --- | --- | --- | --- |
| `interactions.prefetch_strength` | `0.4219218196852704` | - | [0, 1] | float | Prefetch aggressiveness (0..1). | `design.interactions.prefetch_strength` |
| `interactions.branch_predictor` | `0.029797219438070344` | - | [0, 1] | float | Branch-predictor capability (0..1). | `design.interactions.branch_predictor` |
| `interactions.data_reuse` | `0.21863797480360336` | - | [0, 1] | float | Data-reuse / locality exploitation (0..1). | `design.interactions.data_reuse` |
| `interactions.parallelism` | `0.5053552881033624` | - | [0, 1] | float | Exposed parallelism (0..1). | `design.interactions.parallelism` |
| `interactions.fusion` | `0.026535969683863625` | - | [0, 1] | float | Kernel fusion intensity (0..1). | `design.interactions.fusion` |
| `transformations.loop_tiling` | `16` | elem | [1, 1024] | integer | Loop tiling factor. | `design.transformations.loop_tiling` |
| `transformations.unroll_factor` | `16` | x | [1, 64] | integer | Loop unroll factor. | `design.transformations.unroll_factor` |
| `transformations.kernel_fusion` | `0.41951982096165874` | - | [0, 1] | float | Kernel fusion intensity (0..1). | `design.transformations.kernel_fusion` |
| `transformations.vectorization` | `0.4492090462838536` | - | [0, 1] | float | Vectorization intensity (0..1). | `design.transformations.vectorization` |

## Complete Parameter Listing (`parameters`)

| field | value | unit | legal range | type | description | source |
| --- | --- | --- | --- | --- | --- | --- |
| `representation.isa_width` | `128` | bit | [16, 256] | integer | Instruction-set address/data width. | `design.representation.isa_width` |
| `representation.vector_width` | `128` | bit | [32, 4096] | integer | Widest SIMD/vector datapath. | `design.representation.vector_width` |
| `representation.pipeline_depth` | `6` | stage | [2, 64] | integer | Baseline pipeline depth. | `design.representation.pipeline_depth` |
| `representation.issue_width` | `12` | inst | [1, 32] | integer | Instructions issued per cycle. | `design.representation.issue_width` |
| `representation.execution_units` | `10` | unit | [1, 128] | integer | General-purpose execution units. | `design.representation.execution_units` |
| `representation.register_count` | `64` | reg | [8, 2048] | integer | Architectural register file entries. | `design.representation.register_count` |
| `synthesized.parallel_lanes` | `32` | lane | [1, 4096] | integer | Parallel processing lanes. | `design.synthesized.parallel_lanes` |
| `synthesized.tensor_units` | `0` | unit | [0, 1024] | integer | Tensor/accelerator units. | `design.synthesized.tensor_units` |
| `synthesized.specialized_units` | `10` | unit | [0, 512] | integer | Specialized compute units. | `design.synthesized.specialized_units` |
| `structure.l1_kb` | `64` | kB | [4, 4096] | integer | L1 cache capacity. | `design.structure.l1_kb` |
| `structure.l2_kb` | `512` | kB | [64, 65536] | integer | L2 cache capacity. | `design.structure.l2_kb` |
| `structure.l3_kb` | `65536` | kB | [0, 524288] | integer | L3/shared cache capacity. | `design.structure.l3_kb` |
| `structure.cache_line_bytes` | `32` | B | [16, 256] | integer | Cache line size. | `design.structure.cache_line_bytes` |
| `structure.memory_channels` | `3` | chan | [1, 64] | integer | DRAM memory channels. | `design.structure.memory_channels` |
| `structure.interconnect_width` | `1024` | bit | [32, 4096] | integer | On-chip datapath interconnect width. | `design.structure.interconnect_width` |
| `hardware.parallel_blocks` | `64` | block | [1, 1024] | integer | Parallel replicated blocks. | `design.hardware.parallel_blocks` |
| `synthesized.clock_ghz` | `3.44` | GHz | [0.1, 10.0] | float | Target clock frequency. | `design.synthesized.clock_ghz` |
| `hardware.voltage` | `0.79` | V | [0.3, 1.8] | float | Operating voltage. | `design.hardware.voltage` |
| `hardware.frequency_scaling` | `0.87` | - | [0.2, 4.0] | float | Relative frequency-scaling factor. | `design.hardware.frequency_scaling` |
| `hardware.technology_nm` | `14` | nm | [3, 180] | integer | Technology node (feature size). | `design.hardware.technology_nm` |
| `interactions.prefetch_strength` | `0.4219218196852704` | - | [0, 1] | float | Prefetch aggressiveness (0..1). | `design.interactions.prefetch_strength` |
| `interactions.branch_predictor` | `0.029797219438070344` | - | [0, 1] | float | Branch-predictor capability (0..1). | `design.interactions.branch_predictor` |
| `interactions.data_reuse` | `0.21863797480360336` | - | [0, 1] | float | Data-reuse / locality exploitation (0..1). | `design.interactions.data_reuse` |
| `interactions.parallelism` | `0.5053552881033624` | - | [0, 1] | float | Exposed parallelism (0..1). | `design.interactions.parallelism` |
| `interactions.fusion` | `0.026535969683863625` | - | [0, 1] | float | Kernel fusion intensity (0..1). | `design.interactions.fusion` |
| `transformations.loop_tiling` | `16` | elem | [1, 1024] | integer | Loop tiling factor. | `design.transformations.loop_tiling` |
| `transformations.unroll_factor` | `16` | x | [1, 64] | integer | Loop unroll factor. | `design.transformations.unroll_factor` |
| `transformations.kernel_fusion` | `0.41951982096165874` | - | [0, 1] | float | Kernel fusion intensity (0..1). | `design.transformations.kernel_fusion` |
| `transformations.vectorization` | `0.4492090462838536` | - | [0, 1] | float | Vectorization intensity (0..1). | `design.transformations.vectorization` |
| `architecture.design_id` | `6d50b39f-4766-3c8a-98d6-61b0d3e64ab5` | - | [-, -] | string | Content-addressed design identifier. | `design.id` |
| `architecture.domain` | `heterogeneous` | - | [-, -] | string | Processor domain target. | `design.domain` |
| `architecture.architecture_schema_version` | `1` | - | [-, -] | integer | Version of the Design schema used by the generator. | `design.architecture_schema_version` |
| `architecture.generation` | `0` | - | [-, -] | integer | Generation in which the design was produced (0 = root). | `design.generation` |
| `architecture.parent_ids` | `[]` | - | [-, -] | list | Immediate parent design IDs (empty for roots). | `design.parent_ids` |
| `architecture.seed` | `42` | - | [-, -] | integer | Search RNG seed that generated the design. | `provenance.search_config.seed` |
| `architecture.search_engine` | `SearchEngine` | - | [-, -] | string | Search engine implementation. | `provenance.search_config.engine` |
| `architecture.rng` | `Random` | - | [-, -] | string | Random number generator implementation. | `provenance.search_config.rng` |
| `architecture.configuration_fingerprint` | `146a69d586c304df` | - | [-, -] | string | Stable fingerprint of the search + objective configuration. | `provenance.configuration_fingerprint` |
| `architecture.objective_config` | `None` | - | [-, -] | json | Objective (Omega) configuration snapshot. | `provenance.objective_config` |
| `hardware.hardware.target` | `heterogeneous` | - | [-, -] | string | Target hardware strategy (mirrors domain). | `design.hardware.target` |
