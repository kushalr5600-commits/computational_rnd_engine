# ML-KEM-768 Gate 9D — Progress Checkpoint
**Updated**: Sep 22 2026 — Keygen ek/dk FULL MATCH after Bug #15 Fix + post-fix 100-seed regression PASS

## RTL STATUS: **KEYGEN VERIFIED** — single-seed 3586/3586 PASS; post-Bug#15 multiseed **100/100 PASS**

## Summary
The frozen `ntt_core.sv` implements a standard 256-point DFT (not FIPS 203 partial NTT).
A separate FIPS 203-compatible NTT candidate (`ntt_core_fips203.sv`) has been created,
verified with comprehensive tests (forward, roundtrip, poly_mul integration), and
synthesized with Yosys (~97K cells, ~3.4K FFs). The candidate is now **fully integrated**
into `mlkem_keygen_fips203.sv` and produces byte-exact ek/dk against the trusted
`gate_9b345_mlkem.py` reference after fixing the stale-`done` handshake race (Bug #15).

**Candidate RTL location**: `rtl_candidate/`
**Status**: Primitive-level verification PASSED. Keygen integration PASSED (3586/3586 checks).

## Verification Results (45/45 PASS)

### Tests 1-3: Directed Forward Tests
| Test | Input | Result |
|------|-------|--------|
| 1 | zero | PASS |
| 2 | unit | PASS |
| 3 | random | PASS |

### Tests 4-14: Roundtrip Tests (NTT→INTT vs input)
| Test | Seed | Diffs | Result |
|------|------|-------|--------|
| 4 | random | 0/256 | PASS |
| 5-14 | 1000-1009 | 0/256 each | ALL PASS |

### Tests 15-24: Forward-Only vs FIPS 203 Python Reference
| Test | Input | Result |
|------|-------|--------|
| 15 | all-ones | PASS |
| 16 | alternating ±1 | PASS |
| 17 | range [0..255] | PASS |
| 18 | seed 42 | PASS |
| 19 | seed 999 | PASS |
| 20-24 | seeds 2000-2004 | ALL PASS |

### Tests 25-34: Poly_mul Integration (RTL INTT of basemultiply output vs expected)
| Test | Seed | Result |
|------|------|--------|
| 25-34 | 0-9 | ALL PASS |

## Ordering Audit (Sep 22 2026) — RESOLVED: RTL IS CORRECT

**Original hypothesis (WRONG)**: A_hat is standard-order, s_hat/e_hat are bit-reversed. basemultiply reads both sequentially → mismatch.

**Corrected finding**: The RTL forward NTT produces **standard-order output**, matching the Python FIPS 203 reference exactly. The address formula `compute_addr_a(stage, pair)` produces standard-order butterfly pairs. No S_BREV_OUT or S_BREV needed.

**Hardware evidence**: basemul_ordering_tb.sv tested 4 keygen polynomial pairs — all 256/256 PASS for each pair. NTT roundtrip verified for 5 seeds. Basemul end-to-end verified (NTT domain multiply + INTT == direct convolution).

**Keygen ek/dk (RESOLVED Sep 22 2026)**: The old 1145/1184 mismatch was NOT ordering and NOT the golden files — it was Bug #15 (stale-`done` NTT handshake race). Post-fix: ek 0/1184, dk 0/2400, full PASS. See Bug #15 section below.

## ROOT CAUSE (Bug #15): Stale-`done` NTT Handshake Race in Keygen FSM
`ntt_core_fips203.done` is a sticky level: set at S_DONE, cleared only *inside* `if (start)` in S_IDLE (ntt_core_fips203.sv:195, one cycle late via NBA). `mlkem_keygen_fips203.sv` pulsed `start` in `S_NTT_SETUP` and checked `done` in `S_NTT_RUN` **on the same cycle**. Effects: odd iterations (vec_i=1,3,5) saw the previous run's still-high `done` and exited after 1 cycle; even iterations waited for the previous run while `ntt_base` had already changed → wrong S_LOAD base, wrong S_WRITE region. Only vec_i=0 after reset worked. Result: s[1]/e[0]/e[2] left in time domain; s[2]/e[1] had corrupted coeff[0] (−2/+3) → constant delta on even NTT outputs.

**Fix**: `S_NTT_WAIT = 5'd23` (reusing dead `S_DK_OUT`) between `S_NTT_SETUP` and `S_NTT_RUN`; waits for `!ntt_done` before entering `S_NTT_RUN`, ensuring a clean start→run→done sequence per vector. Debug `$display` statements removed after verification.

**Verification (Sep 22 2026, 23:12)**: fresh dumps `rtl_ek_fips.txt`/`rtl_dk_fips.txt`/`rtl_mem_fips.txt`:
- A: 0/2304 mismatch; s_hat (×3): 0/256 each; e_hat (×3): 0/256 each; t_hat: 0/768; rho correct
- **ek: 0/1184, dk: 0/2400, "PASS: 3586 FAIL: 0 ALL CHECKS PASSED", 70252 cycles**
- Golden files `ek_fips203.hex`/`dk_fips203.hex` (gen_golden_fips203.py via gate_9b345_mlkem.py, G=SHA3-512, d=00..1F, z=0x64×32) are CORRECT — do NOT regenerate.

**Handshake audit**: Only `u_ntt` had the stale-done pattern. `shake_sha3` done is a 1-cycle pulse (safe); basemultiply, ntt_sample, G/PRF/XOF/H all safe. `tw_rdata(32'd0)` on u_ntt is harmless (core uses internal zeta_rom).

## Verification Record
- **RTL revision**: `rtl_candidate/ntt_core_fips203.sv` + `mlkem_keygen_fips203.sv` (Sep 22 2026)
- **Reference revision**: `gate_9b345_mlkem.py` (trusted, 100-seed 800/800 PASS)
- **Test count**: 45 primitive tests PASS + keygen 3586/3586 PASS
- **Keygen integration**: ek 0/1184, dk 0/2400 FULL MATCH (was 1145/1184 pre-Bug#15-fix)
- **Yosys synthesis**: ~97K generic cells, ~3.4K flip-flops

## Post-Bug#15 100-Seed Regression (Sep 22 2026) — **100/100 PASS**

| Item | Result |
|------|--------|
| Seeds | 100/100 PASS, **0 FAIL, 0 TIMEOUT, 0 ERROR** |
| Per-seed ek | **0/1184** mismatch each seed |
| Per-seed dk | **0/2400** mismatch each seed |
| X/Z in outputs | **0** (TB X/Z checks all clear) |
| Cycle range | 69973–70296 (single-seed golden seed 3 = 70252) |
| Wall time | 318.9 s |
| Stopped early | No (full 100 completed; no first-divergence) |
| Seed goldens | RTL compared per-seed against on-disk `seed_XXX_{ek,dk}.hex` (ek=0/1184, dk=0/2400). Goldens generated by `gen_vectors.py` from `gate_9b345_mlkem.py` (ref MD5 `6fc6b7f6c642725027411ccfeba4d70b`, mtime Sep 16, predates goldens Sep 21). Independent pre-run golden re-verification: **NOT RETAINED**. |

**Evidence (new files; Sep 21 pre-fix log NOT overwritten):**
- New log: `tb/multiseed/multiseed_fips203_postbug15.log` — MD5 `09bbea7e6f5abf6a2ea48b1ac22ae60b`
  - Header records RTL MD5s including `mlkem_keygen_fips203.sv` = `6dce413efe48e66dea485e45df791012`, `ntt_core_fips203.sv` = `53c36f6a2d3d1acee0e6fa3d1ebc00d8`
- Single-seed vvp stdout transcript: `tb/multiseed/evidence/single_seed_vvp_transcript_postbug15.log` — MD5 `2384792f74195166cac0bd05508ba0b2`
  - Contains `PASS: 3586 FAIL: 0` / `ALL CHECKS PASSED` / 70252 cycles
- Old pre-fix log **unchanged**: `tb/multiseed/multiseed_results.log` MD5 `d30708c0ab291073a5150206110478a7` (before == after)
- Runner: `tb/multiseed/run_all_fips203_postbug15.py` (writes only the new log; stop-on-first-non-PASS)
- TB: `rtl_candidate/tb/mlkem_keygen_fips203_ms_tb.sv` (parameterized `SEED_IDX`, X/Z + timeout checks)
- Backup of old log also at `/tmp/multiseed_results.log.bak` (same MD5)

## Bugs Fixed (9 total)
1. State register width 3→4 bits
2. `done` persistence (cleared only on `start`)
3. `compute_addr` formula (FIPS 203 partial NTT addressing)
4. Zeta index (per-group, not per-pair)
5. GS butterfly sign (b-a, not a-b)
6. GS butterfly mod reduction width
7. Inverse NTT stage reversal (eff_stage)
8. Testbench timing/memory model
9. **Keygen stale-`done` NTT handshake (Bug #15)** — S_NTT_WAIT state added

## Architecture
- Forward NTT: standard input → 7 CT layers → **standard output** (FIPS 203 Algo 9)
- Inverse NTT: standard input → 7 GS layers → standard output (FIPS 203 Algo 10)
- N_INV = 3303 (128^{-1} mod 3329)
- Zeta ROM: 128 entries, ZETAS[k] = 17^{bitrev7(k)} mod 3329
- CT butterfly address formula produces standard-order pairs (not bit-reversed)

## ROOT CAUSE: RTL implements standard 256-point DFT, NOT FIPS 203 partial NTT

**Bug:** `ntt_core.sv` implements a standard 256-point DFT (omega=17) with 8
butterfly stages and pre-processing bit-reversal. ML-KEM requires the FIPS 203
partial NTT (7 layers, length 128→2) with specific twiddle ordering. The
`basemultiply.sv` ZETAS are correct for FIPS 203 but incompatible with the
RTL's standard DFT convention.

**Impact:** ALL polynomial multiplications produce wrong results (0/1000 PASS).
The RTL keygen output (ek/dk) contains incorrect NTT-domain coefficients.

**Proof:**
- RTL NTT matches standard DFT(omega=17): **0/256 mismatches**
- RTL NTT vs FIPS 203 partial NTT: **256/256 mismatches**
- RTL polynomial multiplication: **0/1000 PASS**
- FIPS 203 polynomial multiplication: **1000/1000 PASS**
- RTL roundtrip: **100/100 PASS** (self-consistent but wrong transform)

### Isolation Results (Seed 0)
| Stage | Result | Detail |
|-------|--------|--------|
| PRF (SHAKE-256) | **6/6 PASS** | 0/128 byte mismatches per output |
| CBD(eta=2) | **256/256 PASS** | All coefficients match Python |
| NTT forward | **256/256 PASS** | All coefficients match direct DFT(ω=17) |
| G hash (SHA3-512) | **PASS** | rho matches |
| XOF byte order | **PASS** | rho||j||i verified by hardware capture |
| keccak_f | **PASS** | Known test vector |

### NTT Convention Matrix
| Comparison | Result |
|-----------|--------|
| RTL NTT vs standard DFT(omega=17) | **MATCH** (0/256) |
| RTL NTT vs FIPS 203 partial NTT | **MISMATCH** (256/256) |
| RTL NTT vs bitrev(DFT) | **MISMATCH** (240/256) |
| RTL roundtrip | **PASS** (0/256) |
| FIPS 203 roundtrip | **PASS** (0/256) |

---

## FIPS 203 NTT Candidate RTL (`rtl_candidate/`)

### Files
| File | Description |
|------|-------------|
| `ntt_core_fips203.sv` | FIPS 203 NTT core (7-layer CT forward, 7-layer GS inverse) |
| `ntt_butterfly_gs.sv` | GS butterfly (inverse NTT) |
| `fips_zetas.hex` | Zeta ROM (128 entries, ZETAS[k]=17^bitrev7(k) mod 3329) |
| `tb/ntt_fips203_tb.sv` | Comprehensive testbench (14 tests) |
| `tb/gen_ntt_test_vectors.py` | Python vector generator |

### Bugs Fixed from Original RTL
1. **State register width** (3→4 bits): S_DONE (=3'd8) aliased to S_IDLE (=3'd0)
2. **`done` persistence**: Cleared in S_IDLE, now persists until next `start`
3. **`compute_addr` formula**: Changed from `1<<stage` (Cooley-Tukey) to `N>>(stage+1)` (FIPS 203 partial NTT)
4. **Zeta index**: Fixed from per-pair to per-group (all butterflies in a group share one zeta)
5. **GS butterfly sign**: Changed from `a-b` to `b-a` (FIPS 203 Algorithm 10)
6. **GS butterfly mod reduction**: Fixed width truncation (use full 13-bit value in subtraction)
7. **Inverse NTT address reversal**: Added `eff_stage` = `inverse ? (6-stage) : stage`
8. **Testbench timing**: Added extra `@(posedge clk)` before done-wait loop; blocking read for memory model

### Verification Results
| Test | Result |
|------|--------|
| FWD(zero) | **PASS** |
| FWD(unit) → [1,1,1,...] | **PASS** |
| INTT(NTT(unit)) roundtrip | **PASS** (0/256) |
| INTT(NTT(random)) roundtrip | **PASS** (0/256) |
| 10 random roundtrips (seeds 1000-1009) | **ALL PASS** (0/256 diffs) |
| Python cross-check (1000 roundtrips) | **1000/1000 PASS** |

### Synthesis (Yosys 0.52)
- ~97K logic cells, ~3,400 flip-flops
- `coeff_buf[256][11:0]` inferred as register array (3,072 FFs for data)
- Two 12-bit mod-Q multiply units (CT + GS butterfly)

### Architecture Notes
- Forward NTT: standard input → CT layers → standard output (no BREV needed)
- Inverse NTT: standard input → GS layers → standard output (no BREV needed)
- CT butterfly address formula produces standard-order pairs at each stage
- Python reference also produces standard-order output (no bit-reversal)
- All 45 tests PASS with standard-order convention

### Next Steps
1. ~~Integrate into keygen~~ DONE — ek/dk full match after Bug #15 fix
2. ~~Verify against golden files~~ DONE — ek_fips203.hex/dk_fips203.hex verified correct (do NOT regenerate)
3. Gate-level timing analysis
4. NTT ordering is CORRECT — do NOT add S_BREV_OUT/S_BREV
5. ~~Re-run multiseed suite post-fix~~ DONE — **100/100 PASS** in `multiseed_fips203_postbug15.log` (Sep 22 2026); old `multiseed_results.log` left as pre-fix historical record

### Polynomial Multiplication Test
| Pipeline | Result |
|----------|--------|
| RTL NTT → BM → RTL INTT | **0/1000 PASS** |
| FIPS 203 NTT → BM → FIPS INTT | **1000/1000 PASS** |
| RTL NTT → pointwise → RTL INTT | **255/256 FAIL** |

### Basis Polynomial Traces (first divergence)
| Input | RTL Result[0] | Expected[0] | Diff |
|-------|--------------|-------------|------|
| 1*1 | 1666 | 1 | +1665 |
| 1*X | 1352 | 0 | +1352 |
| X*X | 1352 | 0 | +1352 |
| X^128*X^128 | 1664 | 3328 | +1664 |
| all_ones*unit | 2 | 1 | +1 |

### RTL Memory Map
| Region | Address Range | Contents |
|--------|---------------|----------|
| A_BASE | 0..2303 | A matrix (NTT domain) |
| S_BASE | 2304..3071 | s vectors (NTT domain) |
| E_BASE | 3072..3839 | e vectors (NTT domain) |
| T_BASE | 3840..4607 | t vectors |
| W_BASE | 4608..4863 | Work buffer |

### RTL File Hashes (Sep 22 2026)
```
2a62145a5064e3744931e74b9f3c85bb  ntt_core.sv       ← DEFECT: standard DFT, not partial NTT
a16f226c73ccbe999b018c3504242fd5  ntt_butterfly.sv  ← OK: CT butterfly correct for both
25cabc306c463f319dd2ea890aede4f2  basemultiply.sv   ← OK: ZETAS correct for FIPS 203
9a9679cdfe65daef7ca8adf55cea6b3d  mlkem_keygen.sv   ← OK: FSM correct
74be2f73c950c11c9060d596d38a8860  cbd_sampler.sv    ← OK
7b2e53f962d433c2a66e4f82af1a0274  key_encode.sv     ← OK
a06b0e365aa344c3df78bc78f72c98c4  ntt_sample.sv     ← OK
a915a074044318a79491623164a440dc  keccak_f.sv       ← OK
9dafa9dcae8c7fc8f714dc429d376a1d  shake_sha3.sv     ← OK
b88d95136b1c4d314df72548bf79b335  mod_q_mul.sv      ← OK
```

### Known Limitations
- ~~**RTL NTT needs replacement** with FIPS 203 partial NTT (7 layers)~~ RESOLVED — candidate `ntt_core_fips203.sv` is FIPS 203-compliant and integrated
- **basemultiply.sv ZETAS already correct** for FIPS 203 convention
- **Golden files VERIFIED** — `ek_fips203.hex`/`dk_fips203.hex` correct (gen_golden_fips203.py); old `fresh_*`/`ek_pke_new`/`dk_new` were wrong (SHAKE-256 G or wrong z seed) but `ek_pke_new`/`dk_new` were later overwritten to be byte-identical to fips203 goldens
- Encapsulation/decapsulation tests still BLOCKED (out of scope for keygen)
- Implicit rejection tests still BLOCKED (out of scope for keygen)
- `multiseed_results.log` (Sep 21, 0/100 PASS, ek≈1140–1151/1184) is **PRE-Bug#15-fix only** — historical/stale; superseded by `multiseed_fips203_postbug15.log` (**100/100 PASS**, Sep 22 2026)

### Files
- `tb/multiseed/multiseed_fips203_postbug15.log` — **NEW** — post-Bug#15 100-seed regression (100 PASS)
- `tb/multiseed/run_all_fips203_postbug15.py` — **NEW** — runner (does not touch old log)
- `rtl_candidate/tb/mlkem_keygen_fips203_ms_tb.sv` — **NEW** — multiseed TB for fips203 keygen
- `tb/multiseed/evidence/single_seed_vvp_transcript_postbug15.log` — **NEW** — archived single-seed vvp stdout
- `tb/multiseed/poly_mul_root_cause.md` — Root-cause analysis
- `tb/multiseed/evidence/` — Immutable copies of RTL source and reference
- `tb/multiseed/isolation_evidence.md` — PRF→CBD→NTT isolation evidence
- `Documents/Default Project/poly_mul_root_cause.py` — Diagnostic script
- `Documents/Default Project/rtl_poly_mul_audit_v2.py` — RTL model audit
