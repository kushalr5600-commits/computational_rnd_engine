# Project Status

> Informative snapshot. Updated through the Phase L milestone (EDA bootstrap, SKY130A integration, real hardware validation).
> Every status is one of: **PASS · FAIL · NOT_RUN · BLOCKED**. No result is claimed unless real tooling produced it.

## 1. What already works

| Capability | Component | Status |
| --- | --- | --- |
| Deterministic architecture search | `SearchEngine` (`rnd_engine/search.py`) | PASS |
| Deterministic content/lineage-addressed design IDs | `design_id()` (`rnd_engine/models.py`) | PASS |
| Architecture representation (ISA, pipeline, resources, cache, memory, interconnect, transformations, clock, voltage, technology) | `Design` models (`rnd_engine/models.py`) | PASS |
| Architecture schema versioning | `ARCHITECTURE_SCHEMA_VERSION` + `Design.architecture_schema_version` | PASS |
| Provenance on every design (seed, search config, objective config, configuration fingerprint) | `Design.provenance`, `SearchEngine._provenance` | PASS |
| Surrogate evaluation (deterministic, hash-seeded) | `Evaluator` (`rnd_engine/evaluator.py`) | PASS |
| Omega objective + feasibility constraints | `OmegaObjective`, `OmegaConfig` (`rnd_engine/objective.py`) | PASS |
| Candidate archive (JSONL, Omega-sorted, bounded) | `Archive` (`rnd_engine/archive.py`) | PASS |
| Closed-loop evolutionary search | `InventionEngine` (`rnd_engine/engine.py`) | PASS |
| CLI | `rnd-engine` (`rnd_engine/cli.py`) | PASS |
| Reproducibility test suite (same seed, different seed, evolution, cross-process) | `tests/test_reproducibility.py` | PASS |
| Canonical architecture specification (JSON per section + index + human-readable Markdown) | `rnd_engine/specification/` | PASS |
| Microarchitecture derivation (pipeline, datapaths, memories, interfaces, control, clock/reset; traceable `derived_from` + `rule`; content-addressed hash) | `rnd_engine/microarchitecture/` | PASS |
| Reproducibility utilities (stable SHA-256 digests, config fingerprints) | `rnd_engine/reproducibility.py` | PASS |
| Template-driven SystemVerilog RTL generation (parameterized modules, structural top, manifest-bound provenance) | `rnd_engine/rtl/generator.py` | PASS |
| RTL structural checks (module balance, driver/load sanity, latches, no unresolved template vars) | `rnd_engine/rtl/checker.py` | PASS |
| RTL elaboration checks (unknown modules/ports, unconnected required ports, duplicate connections, unknown parameter overrides, top presence) | `rnd_engine/rtl/checker.py` (`elaboration_check`) | PASS |
| RTL lint gate honesty (verilator/iverilog invoked, `BLOCKED` when binary absent) | `rnd_engine/rtl/checker.py` | PASS |
| Gate reports `reports/lint/<design_id>/` + gate config `verification/lint/gates.json` | `rnd_engine/rtl/generator.py` | PASS |
| Pure-Python reference model matching generated RTL semantics (incl. NOP writeback quirk) | `rnd_engine/verification/reference.py` | PASS |
| Directed tests with hand-computed expectations + reference-model gate `REF-001..003` | `rnd_engine/verification/generator.py` | PASS |
| Testbench + SVA formal property artifacts (labeled never-executed) | `rnd_engine/verification/generator.py` | PASS |
| Simulation / formal gates (verilator/iverilog, SymbiYosys absent) | `rnd_engine/verification/generator.py` | BLOCKED |
| Traceability chain (architecture -> spec -> microarch -> RTL -> verification -> synthesis, SHA-256-linked, validated) | `rnd_engine/traceability/` | PASS |
| Deterministic synthesis config + Yosys flow generation | `rnd_engine/synthesis/generator.py` | PASS |
| Yosys runner + stat parsing (executes when binary present; FAILED keeps stderr) | `rnd_engine/synthesis/generator.py` | PASS |
| Yosys execution gate (binary not installed) | `rnd_engine/synthesis/` | BLOCKED |
| Open-PDK registry (SKY130 `sky130A`, GF180MCU `gf180mcuC`: libs, metal stack, PVT corners) | `rnd_engine/technology/registry.py` | PASS |
| Honest PDK installation probe (`PDK_ROOT`/`PDK` filesystem check) | `rnd_engine/technology/registry.py` | PASS |
| Deterministic design->PDK binding + OpenROAD flow artifacts | `rnd_engine/technology/generator.py` | PASS |
| Physical implementation gate (OpenROAD+OpenSTA verified; sky130A PDK INSTALLED at /usr/local/share/pdk/sky130A and smoke-verified: counter8 full PnR 0 DRC/0 antenna, hold +0.371/setup +7.723/TNS 0 → engine stages ready to run on candidates) | `rnd_engine/technology/` | TOOLCHAIN READY (engine candidate stages NOT_RUN) |
| Physical plan + per-stage scripts (floorplan/place/CTS/route/STA/power/DRC/LVS) | `rnd_engine/physical/` | Generated; stages BLOCKED / NOT_RUN |
| Signoff gate aggregation (12 gates, statuses verbatim from stage manifests) | `rnd_engine/signoff/generator.py` (`collect_gates`) | PASS |
| `tapeout_ready` iff every gate PASSED (impossible in toolless flow: 3 PASS / 9 BLOCKED) | `rnd_engine/signoff/generator.py` (`signoff`) | PASS (honesty invariant) |
| `MeasuredMetrics` (tool-only population) separated from `SurrogateMetrics` (predictions) | `rnd_engine/signoff/model.py` | PASS |
| Real measured area/power/timing/DRC/LVS | Phase H toolchain | BLOCKED |
| Release-level assessment (LEVEL_0..LEVEL_7 evidence gates; cumulative ladder; refuses TAPEOUT without real evidence) | `rnd_engine/release/` (`assess_release`) | PASS |
| IP provenance manifest (content-addressed, per-stage hashes; no proprietary PDK content) | `rnd_engine/release/generator.py` | PASS |
| Tapeout package (emitted at TAPEOUT only when every gate genuinely PASSED — impossible in toolless flow) | `rnd_engine/release/bundle.py` | PASS (refuses by construction) |
| **Flow configuration externalized** (clock, voltage, PDK, libraries, tool paths in YAML) | `configs/default.yaml`, `configs/sky130.yaml`, `configs/gf180.yaml`, `configs/flows/*.yaml` | PASS |
| **Configuration hashing** (stable digest of resolved config; env allowlist) | `rnd_engine/config.py` (`configuration_hash`, `toolchain_hash`, `pdk_hash`) | PASS |
| **EDA subprocess runner** (no `shell=True`, path-traversal guards, bounded output, controlled env) | `rnd_engine/edatools.py` (`run_external_tool`, `_assert_contained`, `_controlled_env`) | PASS |
| **Canonical error model** (24 failure codes, secret-filtering, lossless receipt conversion) | `rnd_engine/errors.py` (`ExternalToolError`) | PASS |
| **Immutable evidence receipts** (candidate + toolchain + PDK + config identities, monotonic evidence ladder) | `rnd_engine/receipt.py` (`FlowReceipt`, `StageReceipt`, `evidence_from_stages`) | PASS |
| **EDA doctor** (honest tool + PDK probe, smoke tests, MISSING/INSTALLED/SMOKE_TEST_FAILED/READY) | `rnd_engine/edadoctor.py` (`run_eda_doctor`, `format_doctor_report`) | PASS |
| **Hardware flow orchestration** (lint -> simulation -> formal -> synthesis -> physical -> sta -> power -> drc -> lvs -> signoff -> release -> receipt) | `rnd_engine/flow.py` (`run_flow`) | PASS |
| **EDA container infrastructure** (Dockerfile, docker-compose, Makefile, versions.lock, check/pdk/smoke scripts) | `eda/` | PASS (Docker/WSL2 operational; image `rnd-engine-eda:with-openroad` contains verified OpenROAD + installed sky130A PDK) |
| **CI** (always-run software gates; EDA gates report BLOCKED_EXTERNAL_DEPENDENCY when unavailable) | `.github/workflows/ci.yml` | PASS |

Baseline gates (validated on Python 3.12.10, pydantic 2.13.5):

```text
ruff check .                        -> PASS (0 errors)
python -m pytest -q                 -> PASS (298 tests)
python -m compileall -q rnd_engine  -> PASS
rnd-engine --help                   -> PASS (legacy + 9 subcommands)
rnd-engine eda-doctor               -> PASS (reports BLOCKED/MISSING honestly)
rnd-engine fab-status               -> PASS (honest lifecycle position per candidate)
rnd-engine lineage                  -> PASS (promotion funnel per experiment)
rnd-engine --population 4 --generations 1 --seed 42 -> deterministic
```

### Fab-ready architecture milestone (audited)

The recursive fab-ready architecture is implemented and adversarially
verified (see docs/ARCHITECTURE.md, "Fab-ready recursive architecture"):

| Layer | Module | Verified by |
|---|---|---|
| Canonical data model (8-level Fidelity, 21-state FabState, EvidenceReceipt, Knowledge, Primitive, SearchPolicy, LineageRecord) | `fab_ready.py` | 19 tests |
| Equation 24 objective (multiplicative V, literal D(S), literal L(Π,K), hard feasibility) | `equation24.py` | 10 tests |
| Append-only knowledge substrate K | `knowledge.py` | substrate tests |
| Recursive substrate evolution S/Π/P | `substrate.py` | 18 tests |
| Fab lifecycle state machine (BLOCKED preserves position, FAIL terminal, FAB_READY only with 13 genuine PASS gates) | `fab_state.py` | 37 tests |
| EDA adapter architecture (ToolRegistry, EvidenceCollector, StageAdapter preflight) | `adapters.py` | runtime probes |
| CLI: `flow`, `fab-status`, `lineage` | `cli.py` | 10 tests |

An independent verification/audit pass confirmed: the 9-vs-10-vs-13
gate/stage enumeration is reconciled and property-locked; FAB_READY is
impossible without genuine evidence for every required gate; BLOCKED never
becomes PASS without real tool execution; one evolved candidate was traced
end-to-end with real EDA execution stopping exactly at binary resolution
(`TOOL_NOT_FOUND`).

## 2. What is missing

The hardware realization chain after architecture/specification does **not** exist yet.

| Missing capability | Phase | Status |
| --- | --- | --- |
| Microarchitecture derivation (pipeline/control/interface breakdown) | 3 | PASS |
| Synthesizable SystemVerilog RTL generation | 4 | PASS |
| RTL lint / syntax / elaboration gates | 5 | PARTIAL (structural + elaboration PASS; verilator/iverilog BLOCKED — not installed) |
| Functional verification (reference model RUNS; simulation BLOCKED — no simulator) | 6 | PARTIAL (reference-model gate PASS; tb_top.sv artifact-only, simulation BLOCKED) |
| Formal verification | 7 | BLOCKED (no formal engine; properties.sva artifact-only) |
| Architecture-to-RTL traceability manifest | 8 | PASS (`RtlManifest` + per-build `TraceabilityManifest` chain in `rnd_engine/traceability/`) |
| Synthesis abstractions + flows | 9 | PARTIAL (config/flow generated + runner ready; execution **BLOCKED** — no yosys binary) |
| Technology / PDK abstraction layer | 10 | PASS (registry + binding + honest probe) |
| Open-PDK implementation path | 11 | BLOCKED (no PDK) |
| Floorplan / placement / CTS / routing | 12-15 | BLOCKED |
| Static timing analysis | 16 | BLOCKED |
| Power analysis | 17 | BLOCKED |
| IR-drop / EM | 18 | BLOCKED |
| DRC / LVS | 19-20 | BLOCKED |
| Signoff orchestration | 21 | Aggregated (3 PASS / 9 BLOCKED; tapeout_ready=False) |
| Architecture <-> physical feedback (measured metrics) | 22 | NOT_RUN |
| Multi-fidelity closed-loop search | 23-24 | PARTIAL (fidelity ladder + promotion funnel implemented; SURROGATE-only evidence in toolless flow) |
| Experiment management | 25 | PARTIAL (deterministic runs + per-artifact SHA-256 manifests; RTL/synth/physical integration pending) |
| Data/provenance system (per-artifact manifests) | 26 | PARTIAL (design-level + experiment-artifact manifests) |
| Release/tapout packaging with gate enforcement | 27-29 | PASS (level assessment + refusal core + tapeout bundle writer; refuses by construction) |
| Security/IP manifest | 30 | PASS (content-addressed IP provenance + hardened subprocess runner) |
| CI/CD for the flow | 31 | PASS (software gates always-run; EDA gates report BLOCKED_EXTERNAL_DEPENDENCY) |
| Extended CLI (`specify`, `rtl`, `synthesize`, `signoff`, ...) | 32 | PARTIAL (eda-doctor, doctor, flow, status, release, signoff, experiment added; specify/rtl/verify/synthesize/physical/drc/lvs pending) |
| Flow configuration files | 33 | PASS (default/sky130/gf180 + 9 flow YAMLs) |
| External tool error-capture harness | 34 | PASS (24-code model + lossless receipt conversion) |

## 3. What can be reused

- `models.py` — all `Design` sub-models; extended (not replaced) with schema version + provenance.
- `search.py` / `evaluator.py` / `objective.py` / `engine.py` / `archive.py` — the deterministic seed-42 loop is
  the SEARCH layer of the closed-loop target; it must not be rewritten.
- `design_id()` — the content-addressed identity primitive; later manifests reuse the same digest approach.
- `reproducibility.py` — stable hashing/fingerprinting primitives reused by specification/manifests later.
- `specification/` — the canonical, field-annotated, hashable architecture description. Downstream microarchitecture
  and RTL generators consume this exact structure (not the raw `Design`), keeping the chain traceable.
- Existing determinism tests — regression anchor for every subsequent phase.
- `edatools.py` — hardened subprocess runner with path-traversal guards, bounded output, controlled env.
- `receipt.py` — immutable evidence receipts with monotonic evidence ladder.
- `config.py` — externalized configuration with stable hashing.

## 4. What must be (re)designed

- **Microarchitecture model** — new `rnd_engine/microarchitecture/` package with pipeline-stage, datapath,
  interface, memory, and control sub-models derived from a `Design`.
- **RTL generator** — new `rnd_engine/rtl/` package emitting synthesizable SystemVerilog only for components the
  design calls for; no placeholder/"pseudocode RTL".
- **Tool abstraction** — every external executable (simulator, linter, synth, P&R, DRC/LVS, STA, power) goes behind
  a `Tool`/`CommandResult` interface that records command/env/stdout/stderr/exit/duration/status and an explicit
  `NOT_RUN/BLOCKED/FAILED/PASSED` outcome.
- **Runbook/config** — `configs/` files for architecture/verification/synthesis/physical/signoff/release; flow
  parameters (clock, voltage, libraries, PDK paths) must never be hardcoded in Python.
- **Experiment + release framework** — `artifacts/experiments/<id>/`, per-artifact manifests, `ReleaseLevel`
  gates, and a tapeout package generator that refuses to fabricate `TAPEOUT_READY`.

## 5. External tools — available

Detected on this machine (`.venv` Python 3.12.10):

| Tool | Detected | Role |
| --- | --- | --- |
| verilator | ❌ No | RTL lint, simulation |
| iverilog | ❌ No | RTL simulation |
| yosys | ❌ No | Synthesis |
| abc | ❌ No | Technology mapping |
| sby (SymbiYosys) | ❌ No | Formal verification |
| openroad | ❌ No | Physical implementation |
| opensta | ❌ No | Static timing analysis |
| magic | ❌ No | DRC, layout |
| netgen | ❌ No | LVS |
| klayout | ❌ No | Layout viewer, DRC |
| ghdl | ❌ No | VHDL simulation |

**All hardware-dependent gates are BLOCKED.** The EDA environment is defined in `eda/` but cannot execute until WSL2 + Docker + SKY130A PDK are provisioned.

## 6. EDA infrastructure status

| Component | Location | Status |
| --- | --- | --- |
| Dockerfile | `eda/Dockerfile` | ✅ Built (not executable — no Docker) |
| docker-compose.yml | `eda/docker-compose.yml` | ✅ Defined (read-only PDK, no network, resource limits) |
| Makefile | `eda/Makefile` | ✅ Convenience targets |
| versions.lock | `eda/versions.lock` | ✅ Pinned tool versions |
| check-tools.sh | `eda/scripts/check-tools.sh` | ✅ Verifies tool presence |
| check-pdk.sh | `eda/scripts/check-pdk.sh` | ✅ Verifies PDK tree |
| smoke-test.sh | `eda/scripts/smoke-test.sh` | ✅ Minimal known-good tests |
| CI | `.github/workflows/ci.yml` | ✅ Software gates + EDA doctor |

## 7. Honesty boundary

- **No silicon fabricated, no foundry approval, no DRC/LVS/timing/power/IR/EM claim anywhere.**
- Evaluator output is deterministic-surrogate evidence only, never physical proof.
- `tapeout_ready` and every release level ≥ the tool-gated rungs are **False by construction** until real EDA tools + a PDK are installed and actually executed.
- A SKY130 experimental/open flow is **not** equivalent to commercial foundry qualification.
| --- | --- |
| Python 3.12, pydantic >= 2.7, numpy >= 2, pytest, ruff | yes |
| iverilog, verilator, yosys, OpenROAD, magic, netgen, klayout, spice, ghdl | no |

No hardware EDA toolchain is currently installed. All RTL/verification/synthesis/physical/signoff phases are
therefore **BLOCKED** until relevant tools are provided (or an open toolchain such as Verilator/Icarus for
simulation and Yosys+OpenROAD+SKY130 for the open flow is installed).

## 6. External tools — missing (required for the hardware chain)

| Stage | Tool examples | Notes |
| --- | --- | --- |
| RTL lint | Verilator --lint-only, Spyglass | lint gates before simulation |
| RTL simulation | Verilator, Icarus Verilog, VCS | functional verification, TB, coverage |
| Formal | SymbiYosys, JasperGold | property checking (Phase 7) |
| Synthesis | Yosys+ABC, Genus, DC | netlist + timing estimate |
| Physical | OpenROAD, Innovus | floorplan, placement, CTS, route |
| DRC/LVS | KLayout, magic+netgen, Calibre | checker-produced results only |
| STA | OpenSTA, Tempus | WNS/TNS across corners |
| Power | PTPX, OpenROAD power | dynamic/leakage breakdown; estimates labeled as estimates |

## 7. PDK information — missing

No PDK is present. The development target (open PDK, e.g., SKY130 via the OpenROAD flow) and the production target
(foundry PDK + process node + standard-cell/memory libraries + metal stack + corners + package) are **conceptual
only**. The architecture model already keeps `architecture target` (domain) separate from physical implementation
technology; nothing in Phase 1/2 assumes a PDK exists.

Until a production PDK is supplied the flow stops at the highest legitimate stage and reports:

```text
STATUS = BLOCKED
Production tapeout blocked: production PDK not supplied.
```

## 8. Recommended implementation sequence

Gated phases (each ends with validation + docs + stable milestone, per the development order policy):

```text
PHASE A  Repository audit                                       -> DONE (this document)
PHASE B  Architecture specification infra (Phase 1 + 2)         -> IN PROGRESS (this milestone)
PHASE C  Microarchitecture derivation (Phase 3)
PHASE D  RTL generation (Phase 4) + RTL lint/infrastructure gates (Phase 5)
PHASE E  Functional verification env (Phase 6) + formal configs (Phase 7)
PHASE F  Traceability manifests (Phase 8) + synthesis abstraction (Phase 9)
PHASE G  Technology/PDK abstraction (Phase 10) + open-PDK path (Phase 11)
PHASE H  Physical design flow (Phases 12-18) + DRC/LVS (19-20)
PHASE I  Signoff orchestration (21) + architecture<->physical feedback (22)
PHASE J  Multi-fidelity search (23-24), experiments (25), provenance (26)
PHASE K  Release/tapout framework (27-29), security (30), CI (31), CLI (32)
```

## 9. Honesty boundary

- No silicon has been fabricated. No foundry approval exists. No DRC/LVS/timing/power/IR/EM claim is made anywhere.
- The evaluator is a deterministic **surrogate**; its `evidence.type == "deterministic_surrogate"`. Surrogate output
  is never presented as physical or silicon evidence.
- All un-run hardware stages report `NOT_RUN` or `BLOCKED` — never `PASS`.