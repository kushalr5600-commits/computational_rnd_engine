# Architecture

The system is intentionally standalone.

## Core loop

Design representation -> deterministic search -> evaluation -> Ω objective -> elite selection -> next generation.

## Ω dimensions

A amplification, V correctness, G generalization, U utility, N novelty, R reusability, H hardware efficiency, I useful structure, D search efficiency, L future discovery rate.

Costs include search, error, memory, complexity, energy, and fragility.

## LLM independence

No LLM is required by the default path. LLM adapters should only propose hypotheses; generated proposals enter the same evaluator and Ω gate as deterministic candidates.

## CPU/GPU roadmap

1. algorithm/kernel search
2. architecture parameter search
3. cycle-accurate simulation
4. RTL generation
5. RTL simulation/formal checks
6. synthesis/PPA
7. FPGA validation
8. calibrated energy and hardware feedback

## Honesty invariant

**Surrogate evidence is never authoritative physical evidence.** The built-in evaluator is a deterministic surrogate (`evidence.type == "deterministic_surrogate"`). It is *not* and is never presented as cycle-accurate simulation, formal verification, RTL linting, synthesis, physical, or silicon evidence. Every un-run hardware stage reports `NOT_RUN`/`BLOCKED`, never `PASS`.

Evidence levels are monotonic: SURROGATE → RTL → SIMULATION → FORMAL → SYNTHESIS → PHYSICAL → SIGNOFF → SILICON. A candidate cannot claim a higher rung without every lower rung genuinely PASSED with real tool evidence.

A SKY130 experimental/open flow bundle is **not** equivalent to foundry-qualified production tapeout.

```text
SearchEngine  ->  deterministic architecture search
Evaluator     ->  deterministic surrogate evaluation
OmegaObjective->  Omega score + feasibility constraints
Archive       ->  bounded, Omega-sorted candidate store

SearchEngine
    -> Design (schema v1, content-addressed id, provenance)
        -> rnd_engine.specification.build_specification
            -> ArchitectureSpecification (sections, annotated params)
                -> specification_hash  (content addressed, sides the manifest chain)
```

The **canonical specification** is the contract between the invention engine and every downstream hardware
stage (microarchitecture, RTL, verification, synthesis, physical, signoff). Downstream consumers read the
specification — never raw `Design` internals — so the architecture-to-silicon chain stays traceable.

## Specification layer

`rnd_engine/specification/` converts a `Design` into an `ArchitectureSpecification`:

- deterministic (same `Design` -> byte-identical specification + identical `specification_hash`)
- every parameter records name, path, type, unit, legal range, description, source, provenance
- sections: architecture (identity/provenance), compute, memory, interfaces, clock_reset, control, parameters
- emits one JSON file per section + `specification/index.json` + a human-readable Markdown document

Provenance (`Design.provenance`) captures seed, search engine, RNG, objective config, and a
`configuration_fingerprint` so a design's identity is bound to the generator configuration that produced it.

## Microarchitecture layer

`rnd_engine/microarchitecture/` converts an `ArchitectureSpecification` into a `MicroArchitectureSpec`:

- deterministic: same specification -> byte-identical microarchitecture + identical `microarchitecture_hash`
- every element records `derived_from` (spec parameter paths) and a `rule` describing the derivation
- sub-models: pipeline, datapaths, memories, interfaces, control, clock/reset
- conditional elements (vector stage/unit/port/issue, tensor units, specialized units, L3 cache) are only
  instantiated when the architecture calls for them
- emits one JSON file per subsystem + `microarchitecture/index.json` + a human-readable Markdown document
- embeds `specification_hash`, so the chain Design -> Spec -> Microarchitecture cannot silently diverge

## RTL layer

`rnd_engine/rtl/` converts a `MicroArchitectureSpec` into synthesizable SystemVerilog:

- `generate_rtl` — emits only the modules the design requires (no placeholder/pseudocode RTL)
- `RtlManifest` — binds design_id, specification_hash, architecture_schema_version, RTL_SCHEMA_VERSION, generator_version, provenance, and a content-addressed build hash
- Structural checks (`structural_check`, RCHK-001..008): pure-Python — module balance, latches, initial blocks, delays, always_ff usage, wait/fork
- Elaboration checks (`elaboration_check`, ELB-001..006): pure-Python — unknown modules/ports, unconnected required ports, duplicate connections, unknown parameter overrides, top presence
- Tool lint gate: invokes Verilator/Icarus when present; `BLOCKED` when absent — never PASS

## Verification layer

`rnd_engine/verification/`:

- `reference.py` — pure-Python reference model mirroring generated RTL semantics (incl. NOP-writes-ALU-default quirk); compared against hand-computed literal expectations, never generates them
- `generator.py` — emits testbench artifact (`tb_top.sv`) + SVA formal properties (`properties.sva`); both labeled never-executed until a real simulator runs them
- Reference-model gates REF-001..003 actually RUN (pure Python) and report PASSED/FAILED
- Simulation/formal gates: BLOCKED when no simulator/formal engine installed

## Traceability layer

`rnd_engine/traceability/` — per-build content-addressed provenance chain:

```
architecture -> specification -> microarchitecture -> RTL -> verification -> synthesis
```

Each link is the SHA-256 of its stage manifest. Consistency validation checks design_id agreement + RTL hash match.

## Synthesis layer

`rnd_engine/synthesis/`:

- `SynthesisConfig` — deterministic (top, clock period from derived clock domain, source list)
- Generates Yosys flow scripts under `configs/synthesis/<id>/` and `flows/synthesis/<id>/`
- Yosys runner (subprocess, stat parsing for wires/cells/cell histogram); tool failure = FAILED with stderr captured
- Execution gate: BLOCKED when yosys not installed; config/flow generation always succeeds

## Technology / PDK layer

`rnd_engine/technology/`:

- Declarative open-PDK registry: SKY130 `sky130A`, GF180MCU `gf180mcuC` (node, standard-cell libraries, metal stack, PVT corners, voltage ranges)
- `pdk_installed()` — honest `PDK_ROOT`/`PDK` filesystem probe; a declared profile alone is never enough
- `bind_technology()` — deterministic per-design binding (node/voltage -> matching open profile -> config + OpenROAD flow artifacts)
- Foundry-node designs (no open profile) and matched-but-uninstalled PDKs both report BLOCKED with recorded reasons

## Physical layer

`rnd_engine/physical/`:

- `PhysicalConfig` — deterministic (floorplan utilization/aspect/site, CTS period/skew, routing layers from PDK metal stack)
- Per-stage OpenROAD/checker scripts generated for floorplan, placement, CTS, routing, STA (WNS/TNS), power, DRC (Magic), LVS (Netgen) — all labeled "generated, not executed"
- Honest stage gates: BLOCKED (PDK uninstalled / no open profile), NOT_RUN (PDK detected, runner arrives with a real toolchain) — never PASS; `metrics` stay empty until a checker produces them

## Signoff layer

`rnd_engine/signoff/`:

- `SignoffResult` aggregates every stage manifest (RTL structural/elaboration/lint, verification reference/simulation/formal, synthesis, pdk_binding, physical_implementation, drc, lvs — 12 gates)
- Gate statuses copied **verbatim** from stage manifests — signoff never re-judges or softens a result
- `tapeout_ready` is True **iff every gate is PASSED** — impossible by construction in the toolless flow (3 real gates PASS, 9 toolchain gates BLOCKED)
- `MeasuredMetrics` (tool-only population) separated from `SurrogateMetrics` (predictions)

## Release layer

`rnd_engine/release/`:

- `ReleaseLevel` LEVEL_0..LEVEL_7 — cumulative evidence ladder; `assess_release` refuses TAPEOUT without real evidence
- IP provenance manifest — content-addressed, per-stage hashes; no proprietary PDK content
- `bundle.py` — tapeout bundle writer with strict refusal logic; emits auditable refusal notice when release is not genuinely ready
- SKY130 experimental/open flow bundle is never equivalent to foundry-qualified production tapeout

## Configuration layer

`rnd_engine/config/` — fixes the empty-`configs/` policy debt:

- `configs/default.yaml` — machine-independent defaults
- `configs/sky130.yaml`, `configs/gf180.yaml` — PDK profile overlays
- `configs/flows/{lint,simulation,formal,synthesis,physical,sta,power,drc,lvs}.yaml` — per-stage tool/options
- Machine-specific paths enter ONLY via documented env vars (`PDK_ROOT`, `EDA_ROOT`, `<TOOL>_BIN`)
- `configuration_hash` — stable digest of resolved config; any env change that alters it changes the hash
- `toolchain_hash` — stable digest of resolved tool versions
- `pdk_hash` — content hash of installed PDK tree (sorted relative-path walk)

## EDA infrastructure layer

`eda/` — reproducible open-source EDA environment:

- `Dockerfile` — Ubuntu 22.04 + Verilator, Icarus, Yosys, ABC, SymbiYosys, OpenROAD, OpenSTA, Magic, Netgen, KLayout
- `docker-compose.yml` — read-only PDK mount, no network, resource limits, all capabilities dropped
- `versions.lock` — pinned tool versions (authoritative for reproducibility)
- `scripts/check-tools.sh`, `check-pdk.sh`, `smoke-test.sh` — verification scripts
- `Makefile` — convenience targets (`build`, `doctor`, `flow`, `lint`, `signoff`, `shell`)

## EDA subprocess runner

`rnd_engine/edatools.py` — hardened external-tool execution:

- No `shell=True` — all invocations use argument arrays
- Path traversal rejected — absolute args must live under workdir or PDK root
- Controlled environment — PATH + allowlisted vars only; host secrets never propagated
- Bounded log capture — last 2000 chars of stdout/stderr
- Resource limits — configurable timeout, max output bytes
- `ToolRun` record — tool, command, status, exit_code, stdout/stderr tail, version, duration, error_code, workdir, env_keys

## Error model

`rnd_engine/errors.py` — canonical 24-code failure model:

- `TOOL_NOT_FOUND`, `TOOL_EXECUTION_FAILED`, `TIMEOUT`, `SYNTAX_ERROR`, `ELABORATION_ERROR`
- `SIMULATION_FAILURE`, `FORMAL_FAILURE`, `SYNTHESIS_FAILURE`, `PNR_FAILURE`, `STA_FAILURE`, `POWER_FAILURE`, `DRC_FAILURE`, `LVS_FAILURE`
- `PDK_MISSING`, `PDK_INVALID`, `CONFIG_INVALID`, `ARTIFACT_INVALID`
- `ExternalToolError` preserves exit code, stdout/stderr, command metadata, tool version, duration, stage, candidate, artifact hash
- Secret-filtering — `SECRET`/`TOKEN` env vars never stored

## Receipt layer

`rnd_engine/receipt.py` — immutable evidence receipts:

- `FlowReceipt` — binds candidate_id, experiment_id, generation_id, parent_candidate_id, parent_artifact_hash + architecture/microarchitecture/RTL/testbench/property/netlist/def/gds hashes + configuration/toolchain/PDK hashes
- `StageReceipt` — one pipeline stage (PASS/FAIL/BLOCKED/NOT_RUN/PENDING)
- `ToolRunReceipt` — one external-tool invocation, captured without loss
- `evidence_from_stages` — derives honest evidence level from actual stage statuses (monotonic ladder)
- `signoff_ready_from_stages` — True only when every hardware gate is genuinely PASS
- `write_receipt` / `load_receipt` — immutable persistence under `receipts/<candidate_id>/`

## EDA doctor

`rnd_engine/edadoctor.py` — honest tool + PDK probe:

- Tests every relevant executable with actual smoke tests (not just `which`)
- Verifies PDK tree structure (LEF, Liberty, GDS, SPICE, technology files, DRC/LVS config)
- Distinguishes MISSING / INSTALLED / SMOKE_TEST_FAILED / READY
- `rnd-engine eda-doctor` CLI subcommand

## Flow orchestration

`rnd_engine/flow.py` — end-to-end hardware validation flow:

```
Architecture -> Microarchitecture -> RTL -> lint -> simulation -> formal ->
synthesis -> physical -> sta -> power -> drc -> lvs -> signoff -> release -> receipt
```

Each stage produces a `StageReceipt`; the final `FlowReceipt` is persisted immutably. The flow is SURROGATE-only until real EDA tools are installed.

## CLI

`rnd_engine/cli.py`:

- Legacy flags: `--population`, `--generations`, `--seed`, `--domain`
- Subcommands: `eda-doctor`, `doctor` (alias), `flow`, `status`, `release`, `signoff`, `experiment`
- `rnd-engine flow --stages lint,simulation` — run specific stages
- `rnd-engine eda-doctor --profile sky130` — run EDA diagnostics

## Security

- No `shell=True` — argument arrays only
- Path traversal rejected — `_assert_contained`
- Isolated temporary working directory
- Read-only PDK mount
- No network by default
- Resource/time limits
- Container isolation (all capabilities dropped, no-new-privileges)
- No host secrets — env allowlist + SECRET/TOKEN filtering
- Bounded logs
- Deterministic artifact collection

## CI

`.github/workflows/ci.yml`:

- Always-run software gates: pytest, ruff, compileall
- EDA doctor gate: reports `BLOCKED_EXTERNAL_DEPENDENCY` when EDA unavailable, never PASS
- Honesty rule: CI never reports PASS for a stage that did not actually execute

## Multi-fidelity search (Phase J, partial)

`rnd_engine/fidelity/` — designed promotion funnel:

```
~1000 SURROGATE -> ~100 RTL/simulation/formal -> ~20 SYNTHESIS -> ~5 PHYSICAL -> 1-2 SIGNOFF
```

Currently SURROGATE-only evidence in toolless flow. Promotion is monotonic and configurable.

## Fab-ready recursive architecture (Phases 1-6, audited)

Implemented on top of the core loop without replacing it. All statuses below
are pytest-verified (298 tests); the hardware half remains BLOCKED.

### Canonical data model (`rnd_engine/fab_ready.py`)

- `Fidelity` — 8-level evidence ladder: SURROGATE < RTL < SIMULATION < FORMAL
  < SYNTHESIS < PHYSICAL < SIGNOFF < SILICON. Promotion is monotonic.
- `FabState` — 21-state lifecycle: DISCOVERED -> ... -> FAB_READY, plus
  terminal FAILED / INVALID.
- `EvidenceReceipt` — one immutable record per stage per candidate: tool,
  version, command, input/output hashes, metrics, toolchain/configuration
  hashes, duration, failure reason. `content_hash()` is deterministic.
- `KnowledgeItem` (12 types), `Primitive`, `SearchPolicy`,
  `SearchSpaceState`, `LineageRecord`, `CandidateSnapshot`,
  `FabReadyRelease`.
- `check_fab_ready(receipts)` — the single authoritative fabrication gate:
  13 required gates, every one must be genuinely PASS.

### Equation 24 objective (`rnd_engine/equation24.py`)

Exact canonical structure, verified by property tests:

```
omega = (A * V * G * U * N * R * H) * (1 + kappa*I) * (1 + eta*D) * (1 + xi*L)
        / (1 + C_search + lambda*E + mu*M + nu*D_c + rho*Energy + sigma*Fragility)
```

- V is multiplicative and evidence-fidelity-weighted (surrogate 0.30 ...
  signoff 1.00) — surrogate evidence can rank but never promote.
- D(S) is literal: `best_verified_improvement / search_cost`.
- L(Pi,K) is literal: `estimated_future_rate / search_budget`.
- Feasibility is a hard gate: any violated constraint family zeroes omega
  exactly, independent of V.

### Recursive substrate (`rnd_engine/knowledge.py`, `substrate.py`)

Append-only `KnowledgeStore` (K) feeds three deterministic evolutions:

```
K_t -> evolve_search_space(S_t, K_t)  -> S_(t+1)   bans/recommends/primitives/bounds
K_t -> evolve_policy(Pi_t, K_t)       -> Pi_(t+1)  exploration/weights/budgets
K_t -> promote_primitives(K_t)        -> P_(t+1)   >=3 verified uses, content-addressed
```

Verified failures ban regions; verified solutions recommend regions;
verified transformations and successful lineages reshape policy weights.

### Fab lifecycle state machine (`rnd_engine/fab_state.py`)

`FabMachine` drives one candidate honestly through `FabState`:

- PASS on a stage completes exactly the lifecycle states it justifies
  (`STAGE_TO_STATE`: lint -> RTL_LINTED + RTL_ELABORATED; physical ->
  AREA_ANALYZED + PLACED + ROUTED; each other stage -> its single state).
- FAIL is terminal. BLOCKED is an environment problem: position preserved,
  blockage recorded, never progress faked. NOT_RUN is recorded separately.
- `declare_fab_ready()` is the only path to FAB_READY and refuses unless
  `check_fab_ready` passes. Transitions are audited with justification +
  evidence hash; `machine_digest()` is deterministic.

Gate enumeration (reconciled and property-locked):

- **9** flow stages executed by `run_flow`
- **10** entries in `FLOW_STAGE_TO_GATES` = 9 stages + signoff
- **13** fabrication gates = lint expands to rtl_lint + rtl_elaboration,
  physical expands to placement + routing + area, plus signoff

### EDA adapter architecture (`rnd_engine/adapters.py`)

- `ToolRegistry` — cached per-tool discovery (binary, version,
  MISSING/INSTALLED) bound to toolchain_hash + configuration_hash. No smoke
  tests (that remains `edadoctor`'s job).
- `EvidenceCollector` — converts a `ToolRun` into a canonical
  `EvidenceReceipt` via the fixed, non-overridable `RUN_TO_GATE` mapping:
  PASSED->PASS, FAILED->FAIL, TIMEOUT->FAIL, TOOL_NOT_FOUND->BLOCKED.
- `StageAdapter` — preflight refuses to launch any process when a required
  tool is MISSING (returns an honest BLOCKED receipt naming the tools);
  `_execute` is implemented per stage only when a real binary can run.

### CLI

`rnd-engine flow|fab-status|lineage` alongside the legacy flags and
`eda-doctor|doctor|status|release|signoff|experiment`. `fab_status.json` is
persisted beside every receipt; `fab-status` reports the honest lifecycle
position per candidate; `lineage` reports the promotion funnel per
experiment.
