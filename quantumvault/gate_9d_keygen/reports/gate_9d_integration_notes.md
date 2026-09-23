# Gate 9D — ML-KEM-768 KeyGen Top-Level Integration Notes

## 1. Architecture Implemented

**Single shared coefficient memory with time-multiplexed ownership.**

- One `coeff_mem[0:MEM_DEPTH-1]` array (12-bit, depth 4864)
- Single write process driven by `wr_we`/`wr_addr`/`wr_data` signals
- Write port multiplexer selects owner based on `mem_owner` register
- Read ports are combinational (multiple readers OK — synthesis infers dual-port or replicated RAM)
- All operations are strictly sequential — no two submodules write simultaneously

### Submodule Ownership Model
| Owner | Module | Writes? | Reads? |
|-------|--------|---------|--------|
| `MO_NONE` | (idle) | No | No |
| `MO_NTT` | ntt_core | Yes (S_WRITE phase) | Yes (S_LOAD phase) |
| `MO_BM` | basemultiply | Yes (S_MUL2 phase) | Yes (S_READ phase) |
| `MO_CPU` | cbd_sampler / ntt_sample | Yes (via coeff_we) | No |
| (read-only) | key_encode | No | Yes (via coeff_addr) |

## 2. Memory Map

```
Base Address  | Region      | Size     | Description
------------- | ----------- | -------- | -----------
0             | A_BASE      | 2304     | A_hat[0..8] (K×K×N = 9×256)
2304          | S_BASE      | 768      | s_hat[0..2] (K×N = 3×256)
3072          | E_BASE      | 768      | e_hat[0..2] (K×N = 3×256)
3840          | T_BASE      | 768      | t_hat[0..2] (K×N = 3×256)
4608          | W_BASE      | 256      | Temp/basemultiply result buffer
4864          | —           | —        | Total depth
```

Address width: 13 bits (ceil(log2(4864)) = 13).

### Address Translation
- **ntt_core**: `physical = ntt_base + ntt_mem_addr` (8-bit local → 13-bit physical)
- **basemultiply port A**: `physical = bm_a_base + bm_addr_a` (8-bit local → 13-bit physical)
- **basemultiply port B**: `physical = bm_b_base + bm_addr_b` (8-bit local → 13-bit physical)
- **key_encode**: `physical = T_BASE + enc_coeff_addr` (10-bit {pi, ci} → 13-bit physical)
- **cbd_sampler**: `physical = cbd_wr_base + cbd_coeff_addr` (8-bit local → 13-bit physical)
- **ntt_sample**: `physical = ns_wr_base + ns_coeff_addr` (8-bit local → 13-bit physical)

## 3. FSM States

```
S_IDLE          → Wait for start pulse
S_HASH_G        → G(d||K) → (rho, sigma)
S_GEN_A_XOF     → XOF(rho, j, i) → 136 bytes
S_GEN_A_SAMP    → ntt_sample parses → A[i][j]
S_GEN_A_NEXT    → Advance to next (i,j)
S_CBD_S_PRF     → PRF(sigma, i) → 128 bytes for s[i]
S_CBD_S_SAMP    → cbd_sampler → s[i]
S_CBD_S_NEXT    → Advance vec_i
S_CBD_E_PRF     → PRF(sigma, K+i) → 128 bytes for e[i]
S_CBD_E_SAMP    → cbd_sampler → e[i]
S_CBD_E_NEXT    → Advance vec_i
S_NTT_SETUP     → Configure ntt_base for polynomial
S_NTT_RUN       → Wait for ntt_core done
S_NTT_NEXT      → Advance to next polynomial (6 total)
S_MM_INIT       → Copy e[i] → T[i] (initialize accumulator)
S_MM_COPY       → Copy A[i][j] → W (256 coefficients)
S_MM_BM         → basemultiply(W, s[j]) → W = A[i][j]*s[j]
S_MM_ACC        → T[i][k] += W[k] for all k
S_MM_NEXT_J     → Advance j or add e[i]
S_MM_NEXT_I     → Advance i
S_ENCODE_EK     → Encode t_hat, stream ek bytes
S_ENCODE_DK     → (placeholder)
S_DK_HASH       → H(ek)
S_DK_OUT        → Output dk bytes
S_ZEROIZE       → Clear sensitive data
S_DONE          → Pulse done
```

## 4. Handshake Timing

### SHAKE/SHA3 (G, H, XOF, PRF)
- **start**: 1-cycle pulse, sampled on posedge
- **done**: 1-cycle pulse
- **ready**: 1-cycle pulse (only for multi-block; not used for single-block)
- **Data**: presented on `data_in` when `start=1`, `last=1` for final block

### ntt_core
- **start**: 1-cycle pulse
- **done**: 1-cycle pulse
- **mem_re**: asserted in S_LOAD, `mem_rdata` captured next cycle (1-cycle read latency)
- **mem_we**: asserted in S_WRITE, data written next cycle (1-cycle write latency)
- **Address width**: 8-bit (0-255), translated via `ntt_base`

### basemultiply
- **start**: 1-cycle pulse
- **done**: 1-cycle pulse
- **S_READ**: addr_a, addr_b, re_a=1, re_b=1 presented
- **S_WAIT**: rdata_a, rdata_b captured (1-cycle read latency)
- **S_MUL2**: wdata_a, addr_a, we_a presented (1-cycle write latency)
- **Address width**: 8-bit (0-255) for both ports

### cbd_sampler
- **start**: 1-cycle pulse
- **done**: 1-cycle pulse
- **prf_ready**: COMBINATIONAL (high when st==ST_FILL && cnt < BITS_PER)
- **prf_valid + prf_data**: sampled on posedge when prf_ready && prf_valid
- **coeff_we**: 1-cycle pulse per accepted coefficient

### ntt_sample
- **start**: 1-cycle pulse
- **done**: 1-cycle pulse
- **xof_ready**: COMBINATIONAL (high when state==S_READ)
- **xof_valid + xof_data**: sampled on posedge when xof_valid && xof_ready
- **coeff_we**: 1-cycle pulse per accepted coefficient

### key_encode
- **start**: 1-cycle pulse
- **done**: 1-cycle pulse
- **coeff_addr**: driven combinationally in S_READ (`assign coeff_addr = {pi, ci}`)
- **coeff_rdata**: captured in S_PACK (1-cycle read latency)
- **byte_valid/byte_ready**: output handshake, stalls if !byte_ready

## 5. Data Ownership

| Region | Written By | Read By | Sensitive? |
|--------|-----------|---------|------------|
| A_hat | ntt_sample (XOF phase) | basemultiply | No (public) |
| s_hat | cbd_sampler (CBD phase) | basemultiply, key_encode | Yes (secret) |
| e_hat | cbd_sampler (CBD phase) | matmul, key_encode | Yes (secret) |
| t_hat | matmul accumulation | key_encode | No (public-ish) |
| W | basemultiply, copy loop | accumulation loop | Temp |

## 6. Zeroization Regions

On `S_ZEROIZE`, clear:
- S_BASE → E_BASE (s_hat, 768 entries)
- E_BASE → T_BASE (e_hat, 768 entries)
- T_BASE → W_BASE (t_hat, 768 entries)
- W_BASE → MEM_DEPTH (W buffer, 256 entries)
- Internal registers: rho, sigma, acc_coeff, prf_counter

Do NOT clear:
- A_BASE → S_BASE (A_hat, public)
- Final ek/dk outputs

## 7. Current Test Status

- Icarus Verilog compilation: **PASS** (clean, no errors, no warnings)
- Yosys synthesis: **TIMEOUT** — root cause: 4× SHAKE-256/128 instances each contain Keccak-f[1600] with 1600-bit state. Yosys 0.9 creates ~1606 decoders per SHAKE instance's padded_block alone. With 4 instances, total decoder count exceeds 6000+ just for SHAKE.
- No functional simulation yet (Phase 1: architecture only, no testbench)

## 8. Known Limitations

1. **Yosys 0.9 slowness**: Keccak-f[1600] with `for` loops creates enormous decoder trees. Yosys 0.9 processes each bit individually. Consider:
   - Using `(* keep *)` on SHAKE instances to prevent full unrolling
   - Running Yosys with `-defer` and `hierarchy` separately
   - Using a newer Yosys version (0.30+) with better memory handling
   - Synthesizing SHAKE instances as black boxes

2. **DK output is placeholder**: S_DK_OUT outputs zeros. Full DK encoding (Encode(s_hat, 12) || ek || H(ek) || z) needs Phase 7.

3. **Zeroization is placeholder**: S_ZEROIZE just transitions to S_DONE. Full zeroization loop needed in Phase 8.

4. **Matmul accumulation uses combinational adder**: `acc_sum = acc_read_val + acc_w_val` is combinational. For synthesis, this creates a 12-bit adder in the critical path. Acceptable for Gate 9D.

5. **`{5'd0, vec_i, 8'd0}` width**: This produces 16-bit result assigned to 13-bit `cbd_wr_base`. Upper 3 bits truncated. Works because vec_i ≤ 2 (max offset = 2×256 = 512 < 8192).

## 9. Files Changed

- `gate_9d_keygen/rtl/mlkem_keygen.sv` — **REWRITTEN** (complete architecture)
- `gate_9d_keygen/reports/gate_9d_integration_notes.md` — **CREATED** (this file)

## 10. Next Steps

1. Write single-seed testbench for Phase 1-3 (CBD + NTT)
2. Generate golden vectors from frozen Python reference
3. Verify s, e, s_hat, e_hat intermediate values
4. Then proceed to Phase 4-5 (matrix A + basemultiply)
5. Then Phase 6-7 (t_hat + encoding)
6. Yosys synthesis with SHAKE as black boxes or newer version
