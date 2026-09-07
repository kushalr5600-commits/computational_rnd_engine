# Microarchitecture Specification

- **design_id**: `6d50b39f-4766-3c8a-98d6-61b0d3e64ab5`
- **domain**: heterogeneous
- **architecture_schema_version**: 1
- **specification_hash**: `0edf41603bf572bf288b161975cb95b8`
- **microarchitecture_schema_version**: 1
- **generator_version**: 1.0.0
- **microarchitecture_hash**: `74ecabe918dbdf818e0be857ade24f0f`

## Pipeline

| stage | role | cycles | width (bit) | derived from | rule |
| --- | --- | --- | --- | --- | --- |
| fetch | instruction fetch | 1 | 128 | representation.isa_width | fetch width == ISA width |
| decode | instruction decode/rename | 1 | 1536 | representation.isa_width, representation.issue_width | decode width == issue_width * ISA width |
| issue | issue to execution ports | 1 | 1536 | representation.issue_width | issue ports == issue_width |
| execute | integer/FP execution | 1 | 1536 | representation.issue_width, representation.execution_units | execute width == issue_width datapaths (execution_units >= issue_width enforced) |
| memory | memory access | 1 | 1024 | structure.interconnect_width | memory stage width == interconnect width |
| retire | in-order retirement | 1 | 1536 | representation.issue_width | retire width == issue_width * ISA width (in-order) |

**depth_stages**: 6  ·  **slots_per_stage**: 12

## Datapaths

| name | kind | count | width (bit) | depth | derived from | rule |
| --- | --- | --- | --- | --- | --- | --- |
| alu | alu | 10 | 128 | - | representation.execution_units, representation.isa_width | one ALU per execution_unit |
| register_file | register_file | 1 | 128 | 64 | representation.register_count, representation.isa_width | architectural register file with register_count entries |
| specialized_units | specialized | 10 | 256 | - | synthesized.specialized_units | specialized_units specialized accelerators (2*ISA datapath) |

## Memories

| name | level | capacity (kB) | line (B) | ways | sets | instantiated | rule |
| --- | --- | --- | --- | --- | --- | --- | --- |
| l1 | L1 | 64 | 32 | 4 | 512 | True | L1 capacity and line from spec; associativity scaled by capacity |
| l2 | L2 | 512 | 32 | 8 | 2048 | True | L2 capacity and line from spec |
| l3 | L3 | 65536 | 32 | 16 | 131072 | True | L3 instantiated only when spec L3 capacity > 0 |
| memory_controller | dram | - | - | - | - | True | DRAM controller with memory_channels channels |

## Interfaces

| name | direction | width (bit) | count | rule |
| --- | --- | --- | --- | --- |
| instruction_fetch | master | 128 | 1 | instruction fetch port sized to ISA width |
| data_memory | master | 1024 | 1 | data memory port sized to interconnect width |
| system_interconnect | master | 1024 | 1 | system interconnect port |
| dram | master | 1024 | 3 | one DRAM port per memory channel |
| accelerator | internal | 1024 | 1 | accelerator interface present when tensor or specialized units exist |

## Control

| name | kind | strength | width (bit) | rule |
| --- | --- | --- | --- | --- |
| in_order_issue | issue | - | 12 | in-order issue of issue_width instructions/cycle |
| branch_predictor | branch_predict | 0.030 | - | branch-predictor capability scaled by spec strength |
| prefetch | prefetch | 0.422 | - | prefetch aggressiveness from spec strength |
| in_order_retire | retire | - | 12 | in-order retire of issue_width instructions/cycle |
| data_reuse | dataflow | 0.219 | - | data-reuse/locality control strength from spec |
| kernel_fusion | dataflow | 0.027 | - | kernel-fusion control strength from spec |

## Clock / Reset

| domain | frequency (GHz) | voltage (V) | technology (nm) | rule |
| --- | --- | --- | --- | --- |
| core | 2.993 | 0.79 | 14 | core domain frequency = clock_ghz * frequency_scaling; voltage/technology from spec |
| memory | 1.496 | 0.79 | 14 | memory domain runs at half the core frequency (uncore divider=2) |

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
