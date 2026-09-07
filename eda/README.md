# EDA Infrastructure

This directory holds the reproducible open-source EDA environment for the
`computational-rnd-engine` hardware validation flow.

## Status

**BLOCKED** — the host machine has no WSL2, no Docker, and no EDA tools
installed. The files here define the environment; they cannot execute until
WSL2 + Docker (or Podman) and the SKY130A PDK are provisioned.

## Files

| File | Purpose |
|---|---|
| `Dockerfile` | Reproducible Ubuntu 22.04 + open-source EDA tool build |
| `docker-compose.yml` | Service definition: read-only PDK mount, no network, resource limits |
| `Makefile` | Convenience targets: `build`, `doctor`, `flow`, `lint`, `signoff`, `shell` |
| `versions.lock` | Pinned tool versions (authoritative for reproducibility) |
| `scripts/check-tools.sh` | Verify all EDA tools are present and executable |
| `scripts/check-pdk.sh` | Verify the SKY130A PDK tree structure |
| `scripts/smoke-test.sh` | Minimal known-good smoke tests for the toolchain |

## Target

**SKY130A** (`sky130A` open PDK) — the first and only configured target.
GF180MCU is configured in `configs/gf180.yaml` but not yet integrated.

## Tools (pinned versions)

| Tool | Version | Role |
|---|---|---|
| Verilator | 5.018 | RTL lint, simulation |
| Icarus Verilog | 12.0 | RTL simulation |
| Yosys | 0.38 | Synthesis |
| ABC | HEAD | Technology mapping |
| SymbiYosys | HEAD | Formal verification |
| OpenROAD | 2.0_8432 | Physical implementation |
| OpenSTA | HEAD | Static timing analysis |
| Magic | 8.3.479 | DRC, layout |
| Netgen | 1.5.265 | LVS |
| KLayout | HEAD | Layout viewer, DRC |

## Prerequisites

1. **WSL2** enabled on Windows (`wsl --install`)
2. **Docker** or **Podman** installed and running
3. **SKY130A PDK** cloned locally (set `PDK_ROOT` to its path)

## Quick start (when prerequisites are met)

```bash
# Build the EDA container
cd eda && make build

# Run the EDA doctor (verifies tools + PDK)
make doctor

# Run a full hardware flow on the best surrogate candidate
make flow POPULATION=8 GENERATIONS=2 SEED=42

# Run just the lint stage
make lint

# Open an interactive shell
make shell
```

## Security

- No `shell=True` — all tool invocations use argument arrays
- Path traversal rejected — absolute args must live under workdir or PDK root
- Read-only PDK mount
- No network access (`network_mode: none`)
- Resource limits (8 CPU, 16 GB RAM)
- All capabilities dropped, no privilege escalation
- Bounded log capture (last 2000 chars of stdout/stderr)
- Host secrets never propagated (only `PATH` + allowlisted `*_BIN`/`PDK_ROOT`/`EDA_ROOT`)

## Honesty boundary

This environment runs **open-source experimental EDA tools only**. A clean
SKY130A flow is **not** equivalent to foundry-qualified production tapeout.
Every metric is explicitly tagged with its evidence level
(SURROGATE / RTL / SIMULATION / FORMAL / SYNTHESIS / PHYSICAL / SIGNOFF).
The system never collapses these categories.