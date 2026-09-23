# Regression Forensics Report — ML-KEM-768 Gate 9D
**Date**: Sep 21 2026

## STEP 1 — Preservation
- File hashes saved: `tb/multiseed/file_hashes.txt`
- All RTL files are untracked by git (no version history available)
- Git has 5 commits; none touch RTL files
- Golden files timestamp: Sep 19 06:43 UTC
- mlkem_keygen.sv modified: Sep 20 14:10 UTC
- shake_sha3.sv modified: Sep 19 06:29 UTC
- basemultiply.sv modified: Sep 20 16:54 UTC

## STEP 2 — Diff
No git history for RTL files. Key interface change found:
- **G hash module**: `mlkem_keygen.sv:241` — `shake_sha3 #(.MODE(3), .RATE_BYTES(72), .D_OUT_BYTES(64))`
  - MODE(3) + RATE_BYTES(72) = SHA3-512 (correct, matches Python reference `hashlib.sha3_512`)
  - AGENTS.md Bug #12 previously documented MODE(1) + RATE_BYTES(136) = SHAKE-256
  - Change from SHAKE-256 to SHA3-512 was apparently intentional
- **Data width warning**: `Port 5 (data_in) of shake_sha3 expects 576 bits, got 1088`
  - g_din is 1088 bits (line 236: `reg [1087:0] g_din`)
  - shake_sha3 data_in port is RATE_BYTES*8 = 576 bits
  - Icarus Verilog prunes upper 512 bits — not necessarily a bug (upper bits are zeros)

## STEP 3 — Localization (First Divergent Intermediate)

### Intermediate Comparison (Seed: d=0x00..0x1F, z=0x64×32)

| Intermediate | RTL Value | Python Ref | Match? |
|---|---|---|---|
| g_out[31:0] | 5e43481c | 5e43481c | **YES** |
| g_out[63:32] | 3eeb397e | 3eeb397e | **YES** |
| A_hat[0][0][0:7] | 772 cea 449 68a 577 041 cb7 | 772 cea 449 68a 577 041 cb7 | **YES** |
| A_hat[0][1][0:7] | 293 88b 074 402 8de 9a2 67f 389 | 293 88b 074 402 8de 9a2 67f 389 | **YES** |
| s_hat[0][0:7] | ce3 9d8 cb2 c5c 4a2 9b1 3e0 | 227 a7d 37f 753 16f 206 18e | **NO** |
| e_hat[0][0:7] | cf8 436 27e 748 0f5 129 824 | 5ad 8f6 8a9 ac3 788 99a 0c7 | **NO** |
| t_hat[0][0:7] | a5f 46c 276 34e 7b7 cc8 4c3 | a29 a18 20d 3c4 a8d 06d 29d | **NO** |
| ek[0:8] | 5fca4676e234b787 | 298aa10d423c8dda | **NO** |

### Root Cause Narrowed

**First divergent intermediate: s_hat (NTT output of secret vector)**

- G hash output: CORRECT ✓
- XOF/rho: CORRECT ✓ (A_hat matches, proving XOF path works)
- Forward NTT: CORRECT ✓ (A_hat NTT matches perfectly)
- **CBD/PRF path: WRONG ✗** (s_hat and e_hat both wrong despite correct sigma)

The regression is isolated to the **PRF→CBD→coeff_mem** path that generates
the secret (s) and error (e) vectors. The forward NTT of these vectors is
correct (verified independently), so the input to NTT is wrong.

### Suspected Areas
1. **PRF module** (`prf_sha3` or equivalent): May use wrong MODE, RATE, or byte count
2. **CBD sampler** (`cbd_sampler.sv`): May have changed bit extraction or sign extension
3. **PRF→CBD data path**: sigma may not reach PRF correctly, or counter may differ
4. **Coeff_mem write address**: s/e vectors may be written to wrong addresses

## STEP 4 — Proposed Repair
- **Do NOT modify files yet**
- Isolate PRF output by adding debug probes at PRF done/data signals
- Compare PRF output byte-by-byte against Python `shake_256(sigma + bytes([counter])).digest(128)`
- If PRF matches, check CBD bit extraction
- If PRF differs, check PRF module configuration (MODE, RATE, byte_len)

## Files
- `tb/multiseed/regression_diff.md` — This report
- `tb/multiseed/file_hashes.txt` — Current RTL MD5 hashes
- `tb/mlkem_locate_tb.sv` — Localization testbench
- `tb/multiseed/dump_intermediates.py` — Python reference intermediate generator
- `tb/multiseed/multiseed_results.log` — 100-seed test results
