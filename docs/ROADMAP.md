# Roadmap

Gated phases. Each phase ends with: inspect -> implement -> validate -> document -> stable milestone.
Status vocabulary: **PASS · FAIL · NOT_RUN · BLOCKED**. No stage is declared done without real tool evidence.

## Phase A — Audit and governance (DONE)

- [x] Repository audit (models, search, evaluator, objective, archive, engine, CLI, tests, packaging, artifacts)
- [x] Baseline gates validated (ruff, pytest, compileall, deterministic CLI)
- [x] `docs/PROJECT_STATUS.md`, `docs/ARCHITECTURE.md` updated

## Phase B — Architecture + canonical specification (IN PROGRESS -> dense complete)

Target: deterministic, versioned, provenance-carrying design identity + hashable canonical specification.

- [x] `ARCHITECTURE_SCHEMA_VERSION` + `Design.architecture_schema_version`
- [x] `Design.provenance` (seed, search config, objective config, configuration fingerprint)
- [x] Deterministic design IDs bound to schema version + provenance
- [x] `rnd_engine/reproducibility.py` (canonical JSON digest, config fingerprints)
- [x] `rnd_engine/specification/` (models, catalog, generator; JSON per section + index + Markdown)
- [x] specification determinism + schema + cross-process hash tests (20 tests total, all pass)
- [x] Docs: ARCHITECTURE, PROJECT_STATUS, ROADMAP, REPRODUCIBILITY, VALIDATION_MATRIX
- [ ] CLI `rnd-engine specify` (deferred to Phase K CLI expansion)
- [ ] Generate one architecture spec per accepted candidate automatically in the run loop (Phase F traceability milestone)

## Phase C — Microarchitecture derivation (COMPLETE)

- [x] `rnd_engine/microarchitecture/` models: pipeline (fetch/decode/issue/execute[/vector]/memory/retire), datapaths (ALU/register file/vector/tensor/specialized), memories (L1/L2/L3 caches + controller), interfaces, control, clock/reset
- [x] Every element carries `derived_from` (spec paths) + `rule`; conditional elements only instantiated when the architecture calls for them
- [x] Deterministic `derive_microarchitecture` + content-addressed `microarchitecture_hash`
- [x] Writers: per-subsystem JSON + index + Markdown under `docs/architecture/<design_id>/`
- [x] Tests: determinism, traceability, cache math, L3-gating, clock math, writers, cross-process hash (31 tests total, all pass)
- [x] Docs updated (PROJECT_STATUS, VALIDATION_MATRIX, ARCHITECTURE)

## Phase D — RTL generation + RTL gates (COMPLETE within toolless scope)

- [x] Synthesizable SystemVerilog generator (only components the design requires)
- [x] RTL manifest (design id, spec hash, generator version, provenance, content-addressed build hash)
- [x] Structural gate `RCHK-001..008` (pure Python: latches, initial blocks, delays, module balance, always_ff usage, wait/fork)
- [x] Elaboration gate `ELB-001..006` (pure Python: unknown modules, unknown ports, unconnected required ports, duplicate connections, unknown parameter overrides, top presence)
- [x] Reports under `reports/lint/<design_id>/` + gate configuration `verification/lint/gates.json`
- [ ] Verilator/Icarus lint/syntax gates — **BLOCKED** (no EDA toolchain installed; gates report BLOCKED, never PASS)

## Phase E — Functional + formal verification (COMPLETE within toolless scope)

- [x] Pure-Python reference model (`rnd_engine/verification/reference.py`) mirroring the generated RTL semantics exactly (incl. the NOP-writes-ALU-default quirk of `issue.sv`); VEC/MAC ops documented out of reference scope
- [x] Directed test suite with **hand-computed** expectations (alu_ops, mem_roundtrip, halt_stops, nop_writes, wrap) — model is compared against literal numbers, never generates them
- [x] Reference-model gate `REF-001..003` actually RUNS (pure Python) and reports PASSED/FAILED
- [x] Testbench artifact `verification/<id>/tb_top.sv` + SVA formal properties `verification/formal/<id>/properties.sva` (artifact-only, labeled as never executed)
- [x] Verification manifest bound to the RTL `architecture_hash` + gate reports under `reports/verification/<id>/` incl. `gates.json`
- [ ] Simulation gate (Verilator/Icarus) — **BLOCKED** (no simulator installed; never PASS)
- [ ] Formal gate (SymbiYosys/JasperGold) — **BLOCKED** (no formal engine; never PASS)

## Phase F — Traceability + synthesis abstraction (COMPLETE within toolless scope)

- [x] `rnd_engine/traceability/` — per-build content-addressed provenance chain: architecture -> specification -> microarchitecture -> RTL -> verification -> synthesis, each link SHA-256 of its stage manifest, with consistency validation (design_id agreement + RTL hash match)
- [x] `rnd_engine/synthesis/` — deterministic `SynthesisConfig` (top, clock period from the derived clock domain, source list) + generated Yosys flow (`configs/synthesis/<id>/config.json`, `flows/synthesis/<id>/flow.ys`)
- [x] Yosys runner (subprocess, stat parsing for wires/cells/cell histogram); tool failure = FAILED with stderr captured; no fabricated area/timing numbers
- [ ] Yosys execution gate — **BLOCKED** (yosys not installed; config/flow generated but never executed)

## Phase G — Technology/PDK abstraction + open-PDK path (COMPLETE within toolless scope)

- [x] `rnd_engine/technology/` — declarative open-PDK registry (SKY130 `sky130A`, GF180MCU `gf180mcuC`: node, standard-cell libraries, metal stack, PVT corners, voltage ranges); profiles are metadata, never proof of installation
- [x] `pdk_installed()` — honest `PDK_ROOT`/`PDK` filesystem probe; a declared profile alone is never enough
- [x] `bind_technology()` — deterministic per-design binding (node/voltage -> matching open profile -> config + OpenROAD flow artifacts under `configs/technology/<id>/`, `flows/physical/<id>/`); manifest chained to the RTL and synthesis hashes
- [x] Honest gate outcomes: foundry-node designs (no open profile) and matched-but-uninstalled PDKs both report **BLOCKED** with recorded reasons; even with a PDK installed the gate is `NOT_RUN` until the Phase H runner exists
- [ ] Physical implementation (OpenROAD execution, DRC/LVS, STA) — **BLOCKED** (no PDK/toolchain installed; Phase H scope)

## Phase H — Physical design + DRC/LVS (COMPLETE within toolless scope)

- [x] `rnd_engine/physical/` — deterministic `PhysicalConfig` (floorplan utilization/aspect/site, CTS period/skew, routing layers from the PDK metal stack) bound to RTL + synthesis + technology manifests
- [x] Per-stage OpenROAD/checker scripts generated for floorplan, placement, CTS, routing, STA (WNS/TNS), power, DRC (magic), LVS (netgen) — all labeled "generated, not executed"
- [x] Honest stage gates: BLOCKED (PDK uninstalled / no open profile), NOT_RUN (PDK detected, runner arrives with a real toolchain) — never PASS; `metrics` stay empty until a checker produces them
- [ ] OpenROAD execution, DRC/LVS, STA/power results — **BLOCKED** (no toolchain installed)

## Phase I — Signoff orchestration + architecture<->physical feedback (COMPLETE within toolless scope)

- [x] `rnd_engine/signoff/` — `SignoffResult` aggregating every stage manifest (rtl structural/elaboration/lint, verification reference/simulation/formal, synthesis, pdk_binding, physical_implementation, drc, lvs — 12 gates)
- [x] Gate statuses copied **verbatim** from stage manifests — signoff never re-judges or softens a result
- [x] `tapeout_ready` is True **iff every gate is PASSED** — impossible by construction in the toolless flow (3 real gates PASS, 9 toolchain gates BLOCKED)
- [x] `MeasuredMetrics` (all-None until a real tool fills them; no code path populates them without a tool run) strictly separated from `SurrogateMetrics` (predictions from the search models)
- [x] Persisted to `reports/signoff/<design_id>/signoff.json`; foreign-design manifests rejected
- [ ] Real measured area/power/timing/DRC/LVS — **BLOCKED** (requires the Phase H toolchain)

## Phase J — Multi-fidelity search, experiments, provenance

- Fidelity levels SURROGATE/RTL/SYNTHESIS/PHYSICAL/SIGNOFF + `evidence_level`
- Configurable promotion: 1000 -> 100 -> 20 -> 5 -> 1-2
- Experiment framework (`artifacts/experiments/<id>/`) + per-artifact SHA-256 manifests

## Phase K — Release/tapout framework, security, CI, CLI

- [x] `rnd_engine/release/` — `ReleaseLevel` LEVEL_0..LEVEL_7 (EXPLORE..TAPEOUT), `_LEVEL_GATES`, `ReleaseManifest`, `assess_release`; every gate derived **verbatim** from the stage manifests; `tapeout_ready` True only when the TAPEOUT level's gate is genuinely PASSED (False by construction in the toolless flow)
- [x] Cumulative ladder: reaching a level requires every lower level's gates to pass; missing upstream stages are honestly `NOT_RUN`
- [x] Content-addressed IP provenance manifest (design + stage hashes); refuses to fabricate `TAPEOUT_READY`
- [x] Cross-manifest `design_id` consistency check (`ReleaseError` on mismatch)
- [x] Tests: 15 release tests (ladder, toolchain-blocked refusal, design_id consistency, manifest structure, determinism) — suite now 133, all pass
- [ ] Tapeout package writer (possible only with a real toolchain) + security/IP hardening
- [ ] CI: Python lint/tests/compile + RTL lint/sim + schema/manifest/flow validation (optional synth/PD jobs)
- [ ] Extended CLI: search, evaluate, specify, rtl, verify, synthesize, physical, signoff, release, experiment, status

## Phase L — EDA bootstrap, SKY130A integration & real hardware validation

- [x] `configs/` externalized (default/sky130/gf180 + 9 flow YAMLs: lint, simulation, formal, synthesis, physical, sta, power, drc, lvs)
- [x] `rnd_engine/config.py` — deterministic config loading, deep merge, env resolution, `configuration_hash`, `toolchain_hash`, `pdk_hash`
- [x] `rnd_engine/errors.py` — canonical 24-code external-tool error model (`ExternalToolError`)
- [x] `rnd_engine/edatools.py` — hardened subprocess runner (no `shell=True`, path-traversal guards, isolated workdir, bounded logs, env allowlist)
- [x] `rnd_engine/edadoctor.py` — honest tool + PDK probe (MISSING/INSTALLED/SMOKE_TEST_FAILED/READY)
- [x] `rnd_engine/receipt.py` — immutable `FlowReceipt` + `StageReceipt` + `ToolRunReceipt`, evidence ladder, `signoff_ready_from_stages`
- [x] `rnd_engine/flow.py` — end-to-end hardware validation flow (Architecture → ... → receipt)
- [x] `rnd_engine/release/bundle.py` — tapeout bundle writer with strict refusal logic
- [x] Extended CLI: `eda-doctor`, `doctor`, `flow`, `status`, `release`, `signoff`, `experiment`
- [x] `eda/` — Dockerfile, docker-compose.yml, Makefile, versions.lock, scripts (check-tools, check-pdk, smoke-test)
- [x] `.github/workflows/ci.yml` — always-run software gates + EDA doctor gate (reports BLOCKED_EXTERNAL_DEPENDENCY when unavailable)
- [x] Tests: 175 total (added test_config, test_edatools, test_receipt, test_cli)
- [ ] WSL2 + Docker + SKY130A PDK provisioning — **BLOCKED** (host has none)
- [ ] Real RTL lint (Verilator/Icarus) — **BLOCKED**
- [ ] Real simulation — **BLOCKED**
- [ ] Real formal (SymbiYosys) — **BLOCKED**
- [ ] Real synthesis (Yosys) — **BLOCKED**
- [ ] Real physical (OpenROAD) — **BLOCKED**
- [ ] Real STA/power/DRC/LVS — **BLOCKED**
- [ ] Measured metrics → Ω integration
- [ ] Multi-fidelity promotion activation (currently SURROGATE-only)

---

## Phase M — fab-ready recursive architecture (implemented + audited)

- [x] `rnd_engine/fab_ready.py` — canonical data model: 8-level `Fidelity`, 21-state `FabState`, `EvidenceReceipt`, `KnowledgeItem`, `Primitive`, `SearchPolicy`, `SearchSpaceState`, `LineageRecord`, `check_fab_ready()` (13 gates)
- [x] `rnd_engine/equation24.py` — exact Equation 24: multiplicative evidence-weighted V, literal D(S) and L(Pi,K), hard feasibility gating
- [x] `rnd_engine/knowledge.py` — append-only recursive knowledge substrate (K)
- [x] `rnd_engine/substrate.py` — recursive evolution: K->S (bans/recommends/bounds), K->Pi (exploration/weights), K->P (primitive promotion at >=3 verified uses)
- [x] `rnd_engine/fab_state.py` — honest lifecycle state machine (BLOCKED preserves position, FAIL terminal, FAB_READY only via genuine all-gate PASS); `bridge_flow_statuses()` + `compute_fab_state()`; gate enumeration reconciled (9 flow stages / 10 bridged gates / 13 fabrication gates, property-locked)
- [x] `rnd_engine/adapters.py` — EDA adapter architecture: `ToolRegistry` (discovery), `EvidenceCollector` (fixed honest RUN_TO_GATE mapping), `StageAdapter` (preflight refuses to launch without real binaries)
- [x] `fab_status.json` persisted beside every receipt; CLI `fab-status` and `lineage` subcommands
- [x] Independent verification/audit pass: Equation 24 verified against canonical spec; adversarial probes (garbage status rejected, TIMEOUT->FAIL, TOOL_NOT_FOUND->BLOCKED, surrogate-only refused, all-9-hardware-PASS still refused without signoff); one evolved candidate traced end-to-end with real EDA execution stopping exactly at binary resolution
- [x] Tests: 298 total (+fab-ready, equation24, substrate, fab-state, CLI tests)

---

## Current status

Phase L's EDA infrastructure layer is now implemented within the toolless scope:
configs are externalized, the hardened subprocess runner and EDA doctor are
implemented, immutable evidence receipts and the end-to-end flow orchestration
are in place, the tapeout bundle writer refuses by construction, CI runs
always-run software gates and reports BLOCKED_EXTERNAL_DEPENDENCY for EDA gates,
and 298 tests guard the entire stack (all passing, ruff clean), including the fab-ready recursive architecture (Equation 24, knowledge substrate, lifecycle state machine, EDA adapters) verified by an independent audit pass.

The hardware realization chain (RTL lint → simulation → formal → synthesis →
physical → STA → power → DRC → LVS → GDS) is **BLOCKED** on missing WSL2,
Docker, and SKY130A PDK. No PASS is claimed for any hardware stage.

See `docs/PROJECT_STATUS.md` for the detailed matrix.