# Polynomial Multiplication Root-Cause Analysis
**Date**: Sep 22 2026  
**Status**: RTL DEFECT CONFIRMED — NTT convention mismatch  
**Scope**: RTL `ntt_core.sv` + `basemultiply.sv` vs FIPS 203 Algorithm 9/10  

## Executive Summary

The RTL implements a **standard 256-point DFT** (omega=17) with 8 butterfly stages.
ML-KEM requires a **FIPS 203 partial NTT** (7 layers, length 128→2) with specific
twiddle ordering. The `basemultiply.sv` ZETAS are correct for FIPS 203 but wrong
for the standard DFT. This convention mismatch causes **100% failure** on
polynomial multiplication (0/1000 PASS), while FIPS 203's convention passes 1000/1000.

## Evidence

### 1. NTT Convention Identification

| Comparison | Result |
|-----------|--------|
| RTL NTT vs standard DFT(omega=17) | **MATCH** (0/256 diffs) |
| RTL NTT vs FIPS 203 partial NTT | **256/256 diffs** |
| RTL NTT vs bitrev(DFT) | **240/256 diffs** |
| RTL NTT vs DFT(bitrev(input)) | **255/256 diffs** |

**Conclusion**: RTL implements `DFT(omega=17)` with pre-processing bit-reversal.
This is NOT the FIPS 203 partial NTT.

### 2. NTT Convention Comparison (unit input)

```
Input: f = [1, 0, 0, ...] (unit polynomial)

RTL NTT(f):  [1, 1, 1, 1, 1, 1, 1, 1, ...]   ← all-ones (DFT of delta)
FIPS NTT(f): [1, 0, 1, 0, 1, 0, 1, 0, ...]   ← alternating (partial NTT of delta)
```

128/256 coefficients differ. The RTL's NTT output is completely different from
FIPS 203's for the same input.

### 3. Polynomial Multiplication Test

| Pipeline | Result | Detail |
|----------|--------|--------|
| RTL NTT → BaseCaseMultiply → RTL INTT | **0/1000 PASS** | Wrong multiplication |
| FIPS 203 NTT → BaseCaseMultiply → FIPS INTT | **1000/1000 PASS** | Correct multiplication |
| RTL NTT → pointwise multiply → RTL INTT | **255/256 FAIL** | Still wrong |

### 4. Basis Polynomial Traces

#### Unit * Unit (1·1 = 1)
```
RTL  NTT(1):  [1, 1, 1, 1, 1, 1, 1, 1, ...]  (DFT convention)
FIPS NTT(1):  [1, 0, 1, 0, 1, 0, 1, 0, ...]  (partial NTT convention)

RTL  BM output: [18, 2, 3313, 2, 2762, 2, 569, 2, ...]
FIPS BM output: [1, 0, 1, 0, 1, 0, 1, 0, ...]  (= NTT(1), correct)

RTL  INTT output: [1666, 1574, 1050, 2648, 492, ...]  ← WRONG (should be [1,0,0,...])
FIPS INTT output: [1, 0, 0, 0, 0, 0, 0, 0, ...]      ← CORRECT
Schoolbook:       [1, 0, 0, 0, 0, 0, 0, 0, ...]      ← REFERENCE
```

First divergence: **index 0**, RTL=1666, expected=1.

#### X^128 * X^128 (should be -X^255 = Q-1 at index 255)
```
RTL  NTT(X^128): [1, 3328, 1, 3328, ...]  (alternating ±1)
FIPS NTT(X^128): [1729, 0, 1729, 0, ...]

RTL  INTT output: [1664, 1574, 1050, ...]  ← WRONG
FIPS INTT output: [3328, 0, 0, 0, ...]      ← CORRECT (3328 = Q-1)
Schoolbook:       [3328, 0, 0, 0, ...]
```

### 5. Structural Root Cause

**RTL ntt_core.sv** (8 stages):
```
S_BREV: bit-reverse input coefficients
S_FORWARD: 8 CT stages, tw_rom[stage*128 + pair%2^stage]
  → Computes: f_hat[k] = sum f[bitrev(j)] * omega^{j*k}  (standard DFT)
```

**FIPS 203 Algorithm 9** (7 layers):
```
No bit-reversal
7 CT stages (length 128→2), zeta = omega^{bitrev7(k_idx)}
  → Computes: f_hat[k] = partial NTT (different transform)
```

**basemultiply.sv** ZETAS[0..63] = FIPS 203 ZETAS[64..127]:
```
These zeta values are correct for FIPS 203's partial NTT convention.
They are WRONG for the standard DFT convention.
```

### 6. Why RTL Roundtrip Passes But Multiplication Fails

The RTL's 8-stage NTT is a **valid** DFT: forward followed by inverse recovers the
original polynomial. But a valid DFT is not necessarily the **correct** transform
for negacyclic polynomial multiplication.

For negacyclic multiplication, the transform must satisfy:
```
INTT(NTT(f) ⊙ NTT(g)) = f*g mod (X^256+1) mod 3329
```

The standard 256-point DFT does NOT satisfy this for negacyclic convolution.
The FIPS 203 partial NTT DOES satisfy this (with the correct BaseCaseMultiply).

### 7. Impact on ML-KEM Keygen

The RTL keygen computes:
```
s_hat = RTL_NTT(s)
e_hat = RTL_NTT(e)
A_hat = RTL_NTT(A)  [via XOF sampling]
t_hat = e_hat + Σ basemultiply(A_hat[i][j], s_hat[j])
ek = encode(rho || t_hat)  [no INTT on t_hat]
dk = encode(s_hat || ek || H(ek) || z)
```

Because RTL_NTT ≠ FIPS_NTT, the NTT-domain values s_hat, e_hat, t_hat are all
wrong. The encoded ek and dk contain incorrect NTT-domain coefficients.

**Note**: The RTL keygen was previously reported as matching golden files. This
needs re-verification — the golden files may have been generated using the same
standard-DFT convention (via `gen_golden.py` which calls `gate_9b345_mlkem.py`,
and `gate_9b345_mlkem.py` uses FIPS 203 partial NTT). If the golden files use
partial NTT and the RTL uses standard DFT, the outputs should differ.

## Defect Classification

**Type**: NTT convention mismatch (RTL implements standard DFT, ML-KEM requires FIPS 203 partial NTT)

**Localization**: 
- `ntt_core.sv`: Wrong transform (standard DFT instead of partial NTT)
- `basemultiply.sv`: ZETAS correct for FIPS 203 but incompatible with RTL's DFT
- `ntt_butterfly.sv`: No defect (CT butterfly is correct for both conventions)

**Severity**: Critical — all polynomial multiplications produce wrong results

## Proposed Smallest RTL Correction

**Option A (change NTT to match basemultiply)**:
1. Remove bit-reversal pre-processing (`S_BREV` state)
2. Reduce from 8 stages to 7 stages (or make stage 0 a pass-through)
3. Change twiddle factor indexing to match FIPS 203's zeta ordering
4. Change `N_INV` from 3316 (256^-1) to 3303 (128^-1)

**Option B (change basemultiply to match NTT)**:
1. Replace `basemultiply.sv` with pointwise multiply in standard DFT domain
2. This is non-trivial: standard DFT + pointwise multiply does NOT give
   negacyclic convolution (need circular convolution with wrap-around twist)

**Recommendation**: Option A is simpler and more evidence-supported. The FIPS 203
partial NTT is specifically designed for negacyclic polynomial multiplication, and
the `basemultiply.sv` ZETAS already match this convention.

## Test Parameters

- 10 basis/unit/boundary polynomial pairs (fully traced)
- 1000 deterministic random polynomial pairs (seeded RNG)
- All comparisons use exact modular arithmetic mod 3329
- Schoolbook reference: f*g mod (X^256+1) mod 3329

## Files

- `poly_mul_root_cause.py` — Comprehensive diagnostic script
- `evidence/ntt_core.sv` — RTL NTT (immutable copy)
- `evidence/basemultiply.sv` — RTL BaseCaseMultiply (immutable copy)
- `evidence/gate_9b345_mlkem.py` — FIPS 203 reference (immutable copy)
- `evidence/tw_rom.hex` — Forward twiddle ROM (immutable copy)
- `evidence/tw_rom_inv.hex` — Inverse twiddle ROM (immutable copy)
