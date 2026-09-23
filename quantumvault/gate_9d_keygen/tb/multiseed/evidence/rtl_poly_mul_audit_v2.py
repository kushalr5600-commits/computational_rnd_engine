#!/usr/bin/env python3
"""
RTL Polynomial Multiplication Audit v2 — CORRECT RTL model.
RTL ntt_butterfly.sv uses CT butterfly (a+tw*b, a-tw*b) for BOTH forward and inverse.
The inverse NTT uses tw_rom_inv with CT butterflies, then scales by N_INV.
"""

import sys, os, time
sys.path.insert(0, r"C:\Users\user\Music\computational_rnd_engine\quantumvault\vectors")
os.chdir(r"C:\Users\user\Music\computational_rnd_engine\quantumvault\vectors")

Q = 3329
N = 256
LOG2_N = 8

# ============================================================
# Load twiddle ROMs
# ============================================================
def load_rom(path):
    rom = []
    with open(path, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                rom.append(int(line, 16))
    return rom

TW_ROM = load_rom(r"C:\Users\user\Music\computational_rnd_engine\quantumvault\tb\tw_rom.hex")
TW_ROM_INV = load_rom(r"C:\Users\user\Music\computational_rnd_engine\quantumvault\tb\tw_rom_inv.hex")
assert len(TW_ROM) == 1024
assert len(TW_ROM_INV) == 1024

# ============================================================
# RTL address functions (ntt_core.sv lines 47-91)
# ============================================================
def bit_reverse(x, n=LOG2_N):
    r = 0
    for _ in range(n):
        r = (r << 1) | (x & 1)
        x >>= 1
    return r

def compute_addr_a(stage, pair):
    m = 1 << stage
    base = (pair // m) * (2 * m)
    offset = pair % m
    return base + offset

def compute_addr_b(stage, pair):
    m = 1 << stage
    base = (pair // m) * (2 * m)
    offset = pair % m
    return base + m + offset

def compute_tw_index(stage, pair):
    m = 1 << stage
    pos = pair % m
    return stage * (N >> 1) + pos

# ============================================================
# RTL butterfly: CT for BOTH directions (ntt_butterfly.sv)
# a_out = (a + tw*b) mod Q
# b_out = (a + Q - tw*b) mod Q
# ============================================================
def rtl_ct_butterfly(a, b, tw):
    tw_b = (tw * b) % Q
    a_out = (a + tw_b) % Q
    b_out = (a + Q - tw_b) % Q
    return a_out, b_out

# ============================================================
# RTL forward NTT
# S_BREV: bit-reverse input
# S_COMPUTE: 8 CT stages with tw_rom (stage 0->7)
# S_WRITE: output in sequential order
# ============================================================
def rtl_ntt_forward(f):
    buf = list(f[:256])

    # S_BREV: bit-reverse the input (ntt_core.sv lines 152-166)
    for i in range(N):
        ri = bit_reverse(i)
        if i < ri:
            buf[i], buf[ri] = buf[ri], buf[i]

    # S_COMPUTE: 8 CT butterfly stages
    for stage in range(LOG2_N):
        for pair in range(N // 2):
            tw_addr = compute_tw_index(stage, pair)
            tw = TW_ROM[tw_addr]
            a_idx = compute_addr_a(stage, pair)
            b_idx = compute_addr_b(stage, pair)
            buf[a_idx], buf[b_idx] = rtl_ct_butterfly(buf[a_idx], buf[b_idx], tw)

    return buf

# ============================================================
# RTL inverse NTT
# S_BREV: bit-reverse input
# S_COMPUTE: 8 CT stages with tw_rom_inv (stage 0->7) — SAME butterfly
# S_SCALE: multiply by N_INV = 3316
# S_WRITE: output in sequential order
# ============================================================
N_INV = 3316  # 256^{-1} mod 3329 (ntt_core.sv line 280)

def rtl_ntt_inverse(f_hat):
    buf = list(f_hat[:256])

    # S_BREV: bit-reverse the input
    for i in range(N):
        ri = bit_reverse(i)
        if i < ri:
            buf[i], buf[ri] = buf[ri], buf[i]

    # S_COMPUTE: 8 CT butterfly stages with tw_rom_inv
    for stage in range(LOG2_N):
        for pair in range(N // 2):
            tw_addr = compute_tw_index(stage, pair)
            tw = TW_ROM_INV[tw_addr]
            a_idx = compute_addr_a(stage, pair)
            b_idx = compute_addr_b(stage, pair)
            buf[a_idx], buf[b_idx] = rtl_ct_butterfly(buf[a_idx], buf[b_idx], tw)

    # S_SCALE: multiply by N_INV (ntt_core.sv lines 243-254)
    for i in range(N):
        buf[i] = (buf[i] * N_INV) % Q

    return buf

# ============================================================
# RTL basemultiply (basemultiply.sv)
# ============================================================
RTL_ZETAS = [
    17, 2761, 583, 2649, 1637, 723, 2288, 1100,
    1409, 2662, 3281, 233, 756, 2156, 3015, 3050,
    1703, 1651, 2789, 1789, 1847, 952, 1461, 2687,
    939, 2308, 2437, 2388, 733, 2337, 268, 641,
    1584, 2298, 2037, 3220, 375, 2549, 2090, 1645,
    1063, 319, 2773, 757, 2099, 561, 2466, 2594,
    2804, 1092, 403, 1026, 1143, 2150, 2775, 886,
    1722, 1212, 1874, 1029, 2110, 2935, 885, 2154
]

def rtl_basemultiply(a_hat, b_hat):
    c_hat = [0] * 256
    for g in range(64):
        zeta = RTL_ZETAS[g]
        neg_zeta = Q - zeta
        a0, a1 = a_hat[4*g], a_hat[4*g+1]
        a2, a3 = a_hat[4*g+2], a_hat[4*g+3]
        b0, b1 = b_hat[4*g], b_hat[4*g+1]
        b2, b3 = b_hat[4*g+2], b_hat[4*g+3]
        c_hat[4*g]   = (a0*b0 + zeta * a1*b1) % Q
        c_hat[4*g+1] = (a1*b0 + a0*b1) % Q
        c_hat[4*g+2] = (a2*b2 + neg_zeta * a3*b3) % Q
        c_hat[4*g+3] = (a3*b2 + a2*b3) % Q
    return c_hat

# ============================================================
# Schoolbook negacyclic multiplication (reference)
# ============================================================
def schoolbook_mul(f, g):
    h = [0] * N
    for i in range(N):
        fi = f[i]
        if fi == 0: continue
        for j in range(N):
            gj = g[j]
            if gj == 0: continue
            k = i + j
            coeff = (fi * gj) % Q
            if k < N:
                h[k] = (h[k] + coeff) % Q
            else:
                h[k - N] = (h[k - N] + Q - coeff) % Q
    return h

# ============================================================
# TEST 1: NTT/INTT roundtrip
# ============================================================
import random
random.seed(42)

print("=" * 70)
print("TEST 1: RTL NTT/INTT Roundtrip (100 random polynomials)")
print("=" * 70)
t0 = time.time()
failures = 0
for trial in range(100):
    f = [random.randint(0, Q-1) for _ in range(N)]
    f_hat = rtl_ntt_forward(f)
    f_rt = rtl_ntt_inverse(f_hat)
    diffs = sum(1 for a, b in zip(f, f_rt) if a != b)
    if diffs > 0:
        failures += 1
        if trial < 5:
            print(f"  Trial {trial}: FAIL ({diffs}/256 mismatches)")
            for i in range(min(4, N)):
                if f[i] != f_rt[i]:
                    print(f"    [{i}]: orig={f[i]}, roundtrip={f_rt[i]}")
elapsed = time.time() - t0
print(f"  Result: {100-failures}/100 PASS ({elapsed:.2f}s)")

# ============================================================
# TEST 2: RTL polynomial multiplication vs schoolbook
# ============================================================
print("\n" + "=" * 70)
print("TEST 2: RTL NTT + basemultiply + INTT vs schoolbook")
print("=" * 70)

test_cases = []
test_cases.append(([0]*N, [0]*N, "zero*zero"))
test_cases.append(([0]*N, [1]+[0]*255, "zero*unit"))
test_cases.append(([1]+[0]*255, [0]*N, "unit*zero"))
test_cases.append(([1]+[0]*255, [1]+[0]*255, "unit*unit"))
test_cases.append(([1]+[0]*255, [1,1]+[0]*254, "unit*(1+x)"))
test_cases.append(([Q-1]*N, [Q-1]*N, "(Q-1)*(Q-1)"))

f_x128 = [0]*N; f_x128[128] = 1
g_x128 = [0]*N; g_x128[128] = 1
test_cases.append((f_x128, g_x128, "X^128 * X^128 (negacyclic wrap)"))

f_x255 = [0]*N; f_x255[255] = 1
g_x = [0]*N; g_x[1] = 1
test_cases.append((f_x255, g_x, "X^255 * X = -1"))

for trial in range(100):
    f = [random.randint(0, Q-1) for _ in range(N)]
    g = [random.randint(0, Q-1) for _ in range(N)]
    test_cases.append((f, g, f"random_{trial}"))

t0 = time.time()
failures = 0
first_fail = None
for idx, (f, g, name) in enumerate(test_cases):
    a_hat = rtl_ntt_forward(f)
    b_hat = rtl_ntt_forward(g)
    c_hat = rtl_basemultiply(a_hat, b_hat)
    c = rtl_ntt_inverse(c_hat)
    expected = schoolbook_mul(f, g)
    diffs = sum(1 for a, b in zip(c, expected) if a != b)
    if diffs > 0:
        failures += 1
        if first_fail is None:
            first_fail = (idx, name, diffs, c, expected)

elapsed = time.time() - t0
total = len(test_cases)
print(f"  Result: {total-failures}/{total} PASS ({elapsed:.2f}s)")
if first_fail:
    idx, name, diffs, got, expected = first_fail
    print(f"  First failure: [{idx}] {name} ({diffs}/256 mismatches)")
    for i in range(min(16, N)):
        if got[i] != expected[i]:
            print(f"    [{i}]: got={got[i]}, expected={expected[i]}")

# ============================================================
# DIAGNOSTIC: Compare RTL NTT output vs FIPS 203 NTT output
# ============================================================
print("\n" + "=" * 70)
print("DIAGNOSTIC: RTL NTT vs FIPS 203 NTT output comparison")
print("=" * 70)

GAMMA = 17
def bitrev7(x):
    r = 0
    for _ in range(7):
        r = (r << 1) | (x & 1)
        x >>= 1
    return r

ZETAS_FIPS = [pow(GAMMA, bitrev7(i), Q) for i in range(128)]

def fips_ntt_forward(f):
    f = list(f[:256])
    k_idx = 1
    length = 128
    while length >= 2:
        start = 0
        while start < 256:
            zeta = ZETAS_FIPS[k_idx]
            k_idx += 1
            for j in range(start, start + length):
                t = (zeta * f[j + length]) % Q
                f[j + length] = (f[j] - t) % Q
                f[j] = (f[j] + t) % Q
            start += 2 * length
        length >>= 1
    return f

f_test = [random.randint(0, Q-1) for _ in range(N)]
rtl_out = rtl_ntt_forward(f_test)
fips_out = fips_ntt_forward(f_test)

diffs = sum(1 for a, b in zip(rtl_out, fips_out) if a != b)
print(f"  RTL vs FIPS 203 NTT: {diffs}/256 mismatches")
if diffs > 0:
    # Check if RTL output is bit-reversed FIPS output
    rtl_br = [rtl_out[bit_reverse(i)] for i in range(N)]
    diffs_br = sum(1 for a, b in zip(rtl_br, fips_out) if a != b)
    print(f"  bitrev(RTL) vs FIPS: {diffs_br}/256 mismatches")
    
    # Check if FIPS output is bit-reversed RTL output
    fips_br = [fips_out[bit_reverse(i)] for i in range(N)]
    diffs_br2 = sum(1 for a, b in zip(rtl_out, fips_br) if a != b)
    print(f"  RTL vs bitrev(FIPS): {diffs_br2}/256 mismatches")

# ============================================================
# KEY TEST: Does RTL multiplication = schoolbook for ALL tests?
# ============================================================
print("\n" + "=" * 70)
print("KEY: If RTL poly_mul fails, check if the issue is NTT or basemultiply")
print("=" * 70)

# Test: RTL NTT → schoolbook pointwise multiply → RTL INTT vs schoolbook
print("  Test: RTL_NTT(f) * pointwise * RTL_NTT(g) → RTL_INTT vs schoolbook:")
f_test = [random.randint(0, Q-1) for _ in range(N)]
g_test = [random.randint(0, Q-1) for _ in range(N)]

a_hat = rtl_ntt_forward(f_test)
b_hat = rtl_ntt_forward(g_test)

# Pointwise multiply (standard NTT multiplication)
c_hat_pw = [(a_hat[i] * b_hat[i]) % Q for i in range(N)]
c_pw = rtl_ntt_inverse(c_hat_pw)
expected = schoolbook_mul(f_test, g_test)
diffs_pw = sum(1 for a, b in zip(c_pw, expected) if a != b)
print(f"    Pointwise: {diffs_pw}/256 mismatches")

# RTL basemultiply
c_hat_bm = rtl_basemultiply(a_hat, b_hat)
c_bm = rtl_ntt_inverse(c_hat_bm)
diffs_bm = sum(1 for a, b in zip(c_bm, expected) if a != b)
print(f"    Basemultiply: {diffs_bm}/256 mismatches")

# Check if basemultiply gives same result as pointwise (it shouldn't if NTT is "partial")
diffs_bm_pw = sum(1 for a, b in zip(c_bm, c_pw) if a != b)
print(f"    Basemultiply vs Pointwise: {diffs_bm_pw}/256 mismatches")
