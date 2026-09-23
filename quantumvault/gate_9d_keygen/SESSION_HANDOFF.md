# SESSION_HANDOFF.md — Gate 9D ML-KEM-768 Keygen (FIPS 203 NTT candidate)

**Checkpoint type:** Checkpoint-only (no RTL/ROM/TB/golden changes; no new sim/synth)  
**Date:** Sep 22 2026  
**Milestone:** Post-Bug#15 regression **accepted**; evidence re-verified

---

## 1. Current milestone

| Field | Value |
|-------|--------|
| Project | ML-KEM-768 KeyGen RTL — `quantumvault/gate_9d_keygen/` |
| Candidate path | `rtl_candidate/` (`mlkem_keygen_fips203` + `ntt_core_fips203`) |
| Bug #15 | **RESOLVED** — `S_NTT_WAIT` handshake fix in `mlkem_keygen_fips203.sv` |
| Single-seed keygen | **3586/3586 PASS** (ek 0/1184, dk 0/2400, 70252 cycles) |
| Post-fix 100-seed RTL regression | **100/100 PASS**, 0 FAIL, 0 TIMEOUT, 0 ERROR, 0 X/Z |
| Regression acceptance | **Accepted** (this checkpoint verifies evidence only) |

---

## 2. Evidence paths (exact)

| Artifact | Path (Windows) | Path (WSL) | MD5 |
|----------|----------------|------------|-----|
| New 100-seed log | `C:\Users\user\Music\computational_rnd_engine\quantumvault\gate_9d_keygen\tb\multiseed\multiseed_fips203_postbug15.log` | `/mnt/c/Users/user/Music/computational_rnd_engine/quantumvault/gate_9d_keygen/tb/multiseed/multiseed_fips203_postbug15.log` | `09bbea7e6f5abf6a2ea48b1ac22ae60b` |
| Single-seed vvp stdout transcript | `...\gate_9d_keygen\tb\multiseed\evidence\single_seed_vvp_transcript_postbug15.log` | `/mnt/c/.../gate_9d_keygen/tb/multiseed/evidence/single_seed_vvp_transcript_postbug15.log` | `2384792f74195166cac0bd05508ba0b2` |
| Pre-fix log (preserved) | `...\gate_9d_keygen\tb\multiseed\multiseed_results.log` | `/mnt/c/.../tb/multiseed/multiseed_results.log` | `d30708c0ab291073a5150206110478a7` |
| Progress doc | `...\gate_9d_keygen\PROGRESS.md` | `/mnt/c/.../gate_9d_keygen/PROGRESS.md` | (updated this session with 100-seed result) |

**New log SUMMARY line (read from file):**  
`SUMMARY: 100 PASS, 0 FAIL, 0 TIMEOUT, 0 ERROR, 0 OTHER out of 100 attempted (target 100)`  
`Old log unchanged: True`  
`Total time: 318.9s`

**Single-seed transcript key lines (read from file):**  
`PASS: 3586  FAIL: 0` / `ALL CHECKS PASSED` / `70252 cycles`

**Per-seed:** every line `SEED N: ... PASS (ek=0/1184 dk=0/2400 ...)` for N=0..99.

**Runner / TB used (not modified this checkpoint):**
- `tb/multiseed/run_all_fips203_postbug15.py`
- `rtl_candidate/tb/mlkem_keygen_fips203_ms_tb.sv`

---

## 3. RTL hashes — log header vs current files

Recorded in `multiseed_fips203_postbug15.log` header; **recomputed this checkpoint — all MATCH**:

| File | MD5 (log = current) | Match |
|------|---------------------|-------|
| `mlkem_keygen_fips203.sv` | `6dce413efe48e66dea485e45df791012` | YES |
| `ntt_core_fips203.sv` | `53c36f6a2d3d1acee0e6fa3d1ebc00d8` | YES |
| `ntt_butterfly_gs.sv` | `a20ab1310c0c9f54e702e1ce0a597f35` | YES |
| `mlkem_keygen_fips203_ms_tb.sv` | `94a62266c7bb076f0835dc31165a5eae` | YES |
| `ntt_butterfly.sv` | `a16f226c73ccbe999b018c3504242fd5` | YES |
| `shake_sha3.sv` | `9dafa9dcae8c7fc8f714dc429d376a1d` | YES |
| `keccak_f.sv` | `a915a074044318a79491623164a440dc` | YES |
| `basemultiply.sv` | `25cabc306c463f319dd2ea890aede4f2` | YES |
| `mod_q_mul.sv` | `b88d95136b1c4d314df72548bf79b335` | YES |
| `ntt_sample.sv` | `a06b0e365aa344c3df78bc78f72c98c4` | YES |
| `cbd_sampler.sv` | `74be2f73c950c11c9060d596d38a8860` | YES |
| `key_encode.sv` | `7b2e53f962d433c2a66e4f82af1a0274` | YES |

Related (not in log header, current values):
- `mlkem_keygen_fips203_tb.sv`: `9425cb0e28a8d8c077988c82064eaa2f`

---

## 4. Preserved artifacts (frozen)

| Artifact | Status | MD5 / note |
|----------|--------|------------|
| Pre-fix log `multiseed_results.log` | **Preserved** (mtime Sep 21; not overwritten) | `d30708c0ab291073a5150206110478a7` — same before/after regression |
| Golden `ek_fips203.hex` | **Preserved** | `d393eb6479dde664005142dad3ceb0ae` (1184 lines) |
| Golden `dk_fips203.hex` | **Preserved** | `a0d8d203d3b235216641c619da2daa8d` (2400 lines) |
| ROMs / frozen RTL (`ntt_core.sv`, `ntt_butterfly.sv`, `basemultiply.sv`, etc.) | **Not modified** this checkpoint | — |
| Testbenches / RTL / goldens | **Not modified** this checkpoint | — |

---

## 5. Git status

| Item | Finding |
|------|---------|
| Repo | `C:\Users\user\Music\computational_rnd_engine` (branch `master`) |
| HEAD | `923b015` — `fix: auto-scale die area, reduce memory pressure for physical design` |
| `gate_9d_keygen/` tracked file count | **0** (`git ls-files` empty) |
| Directory status | `?? quantumvault/gate_9d_keygen/` (entire tree **untracked**) |
| Tested RTL committed? | **NO** — all listed tested files `TRACKED=NO` |
| Evidence logs committed? | **NO** — untracked / not in index |
| Goldens committed? | **NO** — `TRACKED=NO` |
| `PROGRESS.md` committed? | **NO** — `TRACKED=NO` |
| Repo-wide dirty entries | 392 porcelain lines (unrelated modified configs/docs + untracked trees) |

**Conclusion:** Tested files exist on disk with verified hashes but are **not committed** to git. No Gate 9D RTL revision history in git.

---

## 6. Next status

| Item | Status |
|------|--------|
| Post-Bug#15 100-seed regression | **DONE / ACCEPTED** (evidence re-checked this checkpoint) |
| This checkpoint | **COMPLETE** — stop; no further sim/synth |
| Open (needs human/ChatGPT direction) | Gate-level timing; whether to `git add`/commit `gate_9d_keygen/` (currently untracked); encap/decap & implicit-rejection remain **out of scope / unverified**; do **not** claim NIST KAT / side-channel / ASIC sign-off |
| Do not | Regenerate goldens; overwrite `multiseed_results.log`; modify frozen RTL/ROMs; re-run sim without new approval |

**Recommended next action (pending approval):** human decision on committing `gate_9d_keygen/` evidence tree, or proceed to gate-level timing analysis as listed in `PROGRESS.md` Next Steps.
