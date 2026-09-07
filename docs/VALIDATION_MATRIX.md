# Validation Matrix

Every row is evidence-backed. Status vocabulary: **PASS · FAIL · NOT_RUN · BLOCKED**.

Last updated: Phase M milestone (fab-ready recursive architecture + audit).

## Software gates (always-run)

| Component | Validation | Tool | Status |
| --- | --- | --- | --- |
| Architecture | schema + versioning | pydantic (Python) | PASS |
| Search | reproducibility (same seed, diff seed, evolution, cross-process) | pytest | PASS |
| Design identity | content-addressed, lineage-aware, config-bound | pytest | PASS |
| Canonical specification | deterministic generation + content hash | pytest | PASS |
| Microarchitecture | deterministic derivation + content hash + traceability | pytest | PASS |
| Objective (Omega) | amplification/correctness/faster-is-better | pytest | PASS |
| Archive | bounded JSONL store, backward-compatible load | pytest / CLI | PASS |
| CLI | end-to-end deterministic run + subcommands | rnd-engine | PASS |
| Reproducibility | deterministic digests, config fingerprints | pytest | PASS |
| Release | LEVEL_0..LEVEL_7 ladder, gate enforcement, refusal | pytest | PASS |
| Signoff | 12-gate aggregation, tapeout_ready iff all PASS | pytest | PASS |
| Traceability | SHA-256-linked stage chain, design_id consistency | pytest | PASS |
| Config | load/merge/resolve, configuration_hash, toolchain_hash, pdk_hash | pytest | PASS |
| EDA tools | hardened runner, missing-tool behavior, timeout, path traversal | pytest | PASS |
| EDA doctor | honest tool + PDK probe | rnd-engine eda-doctor | PASS (reports BLOCKED) |
| Receipts | FlowReceipt, StageReceipt, evidence ladder, immutability | pytest | PASS |
| Tapeout bundle | refusal when not ready | internal tooling | PASS (refuses) |
| CI | software gates + EDA doctor gate | GitHub Actions | PASS |
| Fab data model | 8-level Fidelity, 21-state FabState, EvidenceReceipt, Knowledge, Primitive | pytest (test_fab_ready) | PASS |
| Equation 24 | multiplicative V, literal D(S)/L(Pi,K), hard feasibility, exact structure | pytest (test_equation24) | PASS |
| Knowledge substrate K | append-only, content-addressed, verified failures/solutions | pytest (test_substrate) | PASS |
| Substrate evolution S/Pi/P | bans/recommends/bounds, policy weights, primitive promotion | pytest (test_substrate) | PASS |
| Fab state machine | BLOCKED preserves position, FAIL terminal, FAB_READY only via 13 genuine PASS gates | pytest (test_fab_state) | PASS |
| Gate enumeration | 9 flow stages / 10 bridged gates / 13 fabrication gates reconciled | pytest (test_fab_state) | PASS |
| EDA adapters | ToolRegistry discovery, EvidenceCollector fixed RUN_TO_GATE mapping, StageAdapter preflight refusal | pytest + runtime probes | PASS |
| CLI fab-status / lineage | honest lifecycle position, promotion funnel per experiment | pytest + rnd-engine | PASS |

## Hardware gates (require EDA toolchain + PDK)

| Component | Validation | Tool | Status |
| --- | --- | --- | --- |
| RTL lint | syntax + lint-only | Verilator/Icarus | BLOCKED (Verilator 5.018 + Icarus 12.0 installed & verified in image; not yet run on engine candidate) |
| RTL simulation | testbench execution | Verilator/Icarus | BLOCKED (tools installed & verified; not yet run on engine candidate) |
| Formal | properties / invariants | SymbiYosys/Jasper | BLOCKED (sby installed; not yet run on engine candidate) |
| Synthesis | netlist + area proxy | Yosys/ABC | BLOCKED (Yosys 0.38 + ABC installed & verified; not yet run on engine candidate) |
| Physical | floorplan/place/CTS/route | OpenROAD | TOOL VERIFIED — full sky130A PnR smoke PASS (counter8: 0 DRC, 0 antenna); engine candidates pending |
| STA | setup/hold/WNS/TNS | OpenSTA/Tempus | TOOL VERIFIED — post-route STA on sky130A smoke: hold +0.371 / setup +7.723 / TNS 0; engine candidates pending |
| Power | dynamic/leakage estimation | PTPX/OpenROAD | TOOL VERIFIED — report_power on post-OpenRCX sky130A netlist (5.72e-05 W smoke); engine candidates pending |
| DRC | rule checking | Magic/KLayout | TOOL VERIFIED (Magic 8.3.305: banner + sky130A.tech load PASS; KLayout 0.29.11: banner PASS); not yet run on engine candidate |
| LVS | netlist comparison | Netgen/Magic | TOOL VERIFIED (Netgen 1.5.265 banner PASS); not yet run on engine candidate |
| GDS | layout generation | OpenROAD/KLayout | TOOL VERIFIED (OpenROAD writes GDS; KLayout 0.29.11: banner PASS) |

## Honesty rules

1. A hardware stage is **BLOCKED** until the actual external tool executes successfully against the actual candidate artifact.
2. `BLOCKED` never becomes `PASS` to make tests pass.
3. Surrogate evidence (SURROGATE) never promotes a candidate to a hardware evidence level.
4. `tapeout_ready` is True only when every required gate genuinely PASSED — impossible by construction in the toolless flow.