# FIPS 203 Ordering Audit — Gate 9D Keygen Integration
**Date**: Sep 22 2026 (v2 — definitive)  
**Author**: OpenCode (automated audit)  
**Status**: RESOLVED — RTL ordering is CORRECT. No BREV needed.

---

## Executive Summary (Corrected)

**The RTL forward NTT produces standard-order output, matching the Python FIPS 203 reference exactly.** The original audit's claim about bit-reversed output was wrong. The RTL address formula (`compute_addr_a/b`) produces standard-order butterfly pairs, not bit-reversed pairs.

**Evidence:**
1. RTL address trace: `compute_addr_a(stage=0, pair=0)=0`, `compute_addr_b(0,0)=128` — pairs (0,128) at distance 128 ✓
2. RTL zeta index: stage 0 → `zeta_idx=1`, stage 1 → `zeta_idx=2+pair_idx[6]` — matches Python `k_idx=1,2,3,...` ✓
3. RTL S_WRITE: `mem_addr=write_idx`, `mem_wdata=coeff_buf[write_idx]` — sequential write, standard order ✓
4. **Hardware test**: 4 keygen polynomial pairs (A[0][0]·s[0], A[0][1]·s[1], A[1][0]·s[0], A[0][2]·s[2]) — **256/256 PASS for each** ✓
5. **Full NTT roundtrip**: 5 seeds (0,42,999,2000,31415) — **all PASS** ✓
6. **Basemul verification**: NTT(basemul(f,g)) == direct_convolution(f,g) — **PASS** ✓

**Conclusion: Variant A (current RTL) is CORRECT.** No S_BREV_OUT, no S_BREV, no address remapping needed.

---

## 1. FIPS 203 Algorithm Analysis

### Algorithm 9 — NTT(f)
- Input: f ∈ Z_q^N in **standard order** (f[0], f[1], ..., f[255])
- Output: f̂ = NTT(f) in **standard order** (f̂[0], f̂[1], ..., f̂[255])
- The CT butterfly naturally produces standard-order output when stages are processed in order (length=128→64→32→...→2)

### Algorithm 10 — NTT⁻¹(f̂)
- Input: f̂ ∈ Z_q^N in **standard order**
- Output: f = NTT⁻¹(f̂) in **standard order**
- The GS butterfly naturally produces standard-order output when stages are processed in order (length=2→4→...→128)

### Algorithm 11 — MultiplyNTTs(f̂, ĝ)
- Input: f̂, ĝ ∈ Z_q^N — both in **standard order**
- Output: ĥ = f̂ ⊙ ĝ in **standard order**
- Uses 64 groups of 4 coefficients: (f̂[4i], f̂[4i+1], f̂[4i+2], f̂[4i+3]) × (ĝ[4i], ĝ[4i+1], ĝ[4i+2], ĝ[4i+3])
- Twiddle: ZETAS[64+i] for group i

### Algorithm 12 — BaseCaseMultiply(a₀,a₁,b₀,b₁,γ)
- Degree-1 polynomial multiplication mod (x²-γ)
- (a₀ + a₁x)(b₀ + b₁x) mod (x²-γ) = (a₀b₀ + γa₁b₁) + (a₀b₁ + a₁b₀)x

**Key insight: All algorithms use standard-order indexing.** There is no bit-reversal in any FIPS 203 algorithm. The NTT output is in standard order, and MultiplyNTTs reads indices sequentially.

---

## 2. RTL Address Formula Trace

### compute_addr_a(stage, pair)
```
m = N >> (stage + 1)
mask = m - 1
a = ((pair & ~mask) << 1) | (pair & mask)
```

### Trace for each stage (pair_idx=0):

| Stage | m | mask | pair & ~mask | a | b | Pairs |
|-------|------|------|-------------|---|---|-------|
| 0 | 128 | 127 | 0 | 0 | 128 | (0,128) |
| 1 | 64 | 63 | 0 | 0 | 64 | (0,64) |
| 2 | 32 | 31 | 0 | 0 | 32 | (0,32) |
| 3 | 16 | 15 | 0 | 0 | 16 | (0,16) |
| 4 | 8 | 7 | 0 | 0 | 8 | (0,8) |
| 5 | 4 | 3 | 0 | 0 | 4 | (0,4) |
| 6 | 2 | 1 | 0 | 0 | 2 | (0,2) |

**All stages produce standard-order butterfly pairs.** The RTL's CT butterfly processes:
- Stage 0: pairs at distance 128 → (0,128), (1,129), ..., (127,255)
- Stage 1: pairs at distance 64 → (0,64), (1,65), ..., (63,127)
- ...
- Stage 6: pairs at distance 2 → (0,2), (1,3), ..., (254,255)

This is the standard CT butterfly structure. After all7 stages, `coeff_buf[k]` = NTT(f)[k] for k=0..255 (standard order).

### Zeta index trace (forward, inverse=0):

| Stage | zeta_base | zeta_group | zeta_idx range | Python k range |
|-------|-----------|------------|----------------|----------------|
| 0 | 1 | 0 | 1 | 1 |
| 1 | 2 | pair_idx[6] | 2..3 | 2..3 |
| 2 | 4 | pair_idx[6:5] | 4..7 | 4..7 |
| 3 | 8 | pair_idx[6:4] | 8..15 | 8..15 |
| 4 | 16 | pair_idx[6:3] | 16..31 | 16..31 |
| 5 | 32 | pair_idx[6:2] | 32..63 | 32..63 |
| 6 | 64 | pair_idx[6:1] | 64..127 | 64..127 |

**RTL zeta_idx matches Python k_idx exactly for all stages.**

---

## 3. Python Reference Analysis

### ntt_forward(f)
- Input: f in standard order (f[0], f[1], ..., f[255])
- CT butterfly: length=128→64→...→2, k_idx=1→2→...→127
- Output: f̂ in **standard order** (f̂[0], f̂[1], ..., f̂[255])
- **No bit-reversal occurs.** The CT butterfly with this stage ordering produces standard-order output.

### ntt_sample(bytes)
- Parse algorithm: extracts coefficients from byte stream
- Places at positions 0,1,2,...,255 sequentially
- Output: **standard order**

### basemultiply(a_hat, b_hat)
- Reads a_hat[4i..4i+3] and b_hat[4i..4i+3] sequentially
- Uses ZETAS[64+i] as twiddle factor
- **Assumes standard-order inputs**

### mlkem_keygen
- A_hat = generate_matrix(rho) → ntt_sample(XOF(rho,j,i)) → **standard order**
- s_hat = ntt_forward(s_time) → **standard order**
- e_hat = ntt_forward(e_time) → **standard order**
- t_hat = e_hat + Σ_j basemultiply(A_hat[i][j], s_hat[j]) → all standard order

---

## 4. RTL Address Mapping vs Python Reference

| Component | RTL | Python | Match? |
|-----------|-----|--------|--------|
| A_hat generation | XOF(rho,j,i) → ntt_sample → coeff_mem[A_BASE + (i*3+j)*256 + k] | XOF(rho,bytes([j]),bytes([i])) → ntt_sample → A_hat[i][j][k] | ✓ |
| s_hat generation | CBD → coeff_mem[S_BASE + i*256 + k] → NTT forward → coeff_mem[S_BASE + i*256 + k] | CBD → s_time[i] → ntt_forward → s_hat[i][k] | ✓ |
| NTT output order | Standard (coeff_buf[write_idx] → mem[write_idx]) | Standard (f[k] in-place) | ✓ |
| basemultiply reads | W_BASE+k and S_BASE+j*256+k (sequential) | a_hat[k] and b_hat[k] (sequential) | ✓ |
| basemultiply twiddle | ZETAS[64+i] via tw_rom | ZETAS[64+i] | ✓ |
| Accumulation | T[i][k] += W[k] (sequential) | acc[k] += bp[k] | ✓ |

**All address mappings match.** There is no ordering mismatch.

---

## 5. Three Variants Evaluation

### Variant A: Current NTT output mapping (CORRECT)
- Forward NTT: standard input → CT layers → standard output in coeff_buf → S_WRITE writes to coeff_mem[0..255]
- A_hat: standard order in coeff_mem
- s_hat/e_hat: standard order in coeff_mem after forward NTT
- basemultiply: reads both sequentially (same index)
- **Result: All basemultiply tests PASS (256/256 for 4 keygen pairs)**

### Variant B: Re-add S_BREV_OUT (INCORRECT)
- Would make NTT output bit-reversed in coeff_buf
- coeff_mem[k] = NTT_output[bitrev8(k)] — bit-reversed order
- A_hat would be in standard order (from ntt_sample), s_hat in bit-reversed order (from FWD NTT with BREV)
- basemultiply would read A_hat[k] and NTT(s)[bitrev8(k)] — **mismatched indices**
- **Result: basemultiply would produce WRONG output for all off-diagonal pairs**

### Variant C: Address remap (UNNECESSARY)
- Would change memory addressing to match a different ordering
- No benefit: current addressing is already correct
- **Result: Same as Variant A (current is already correct)**

---

## 6. Hardware Verification Evidence

### basemul_ordering_tb.sv — RTL basemultiply test
Tested 4 polynomial pairs from keygen with d=0x00..0x1F, z=0x64:

| Test | Pair | RTL output vs Python | Result |
|------|------|---------------------|--------|
| 1 | A[0][0] × s[0] | 256/256 match | **PASS** |
| 2 | A[0][1] × s[1] | 256/256 match | **PASS** |
| 3 | A[1][0] × s[0] | 256/256 match | **PASS** |
| 4 | A[0][2] × s[2] | 256/256 match | **PASS** |

**First differing coefficient: NONE — all 256 coefficients match for all 4 pairs.**

### NTT roundtrip verification
| Seed | Result |
|------|--------|
| 0 | PASS |
| 42 | PASS |
| 999 | PASS |
| 2000 | PASS |
| 31415 | PASS |

### Basemul end-to-end verification
- NTT(basemul(NTT(a), NTT(b))) == direct_convolution(a,b) for seeds 42,999: **PASS**

---

## 7. Root Cause of Keygen ek/dk Mismatch (Separate Issue)

The RTL basemultiply and NTT are both correct. The keygen ek/dk mismatch (1145/1184) must be caused by a different issue, likely:

1. **Golden file generation bug**: The golden files (`ek_fips203.hex`, `dk_fips203.hex`) may have been generated with an earlier buggy Python reference
2. **SHAKE/SHA3 difference in G hash**: Earlier golden files used SHAKE-256 for G instead of SHA3-512
3. **Accumulation timing issue**: The RTL accumulation (S_MM_ACC) may have a read-after-write hazard

**The NTT ordering is NOT the cause of the keygen mismatch.** The original audit incorrectly identified a non-existent ordering problem.

---

## 8. Corrected AGENTS.md Entries

Remove the incorrect claim about bit-reversed NTT output. The correct statements are:
- Forward NTT: standard input → 7 CT layers → **standard output** (not bit-reversed)
- Inverse NTT: standard input → 7 GS layers → standard output
- NTT uses standard-order addressing throughout
- No S_BREV or S_BREV_OUT states needed

---

## Files Modified
| File | Change |
|------|--------|
| `tb/multiseed/ordering_audit.md` | This file (replaced with corrected v2) |
| `tb/basemul_ordering_tb.sv` | New testbench for direct basemul verification |
| `tb/vectors/trace_*.hex` | Python-generated reference coefficients |
| `tb/vectors/fwd*_expected_v2.hex` | Python-generated NTT expected outputs |

## Recommendation
**Do NOT add S_BREV_OUT or S_BREV to ntt_core_fips203.sv.** The current RTL is correct.
Investigate the keygen ek/dk mismatch through golden file verification, not NTT ordering changes.
