#!/usr/bin/env python3
"""Post-Bug#15 100-seed regression for FIPS 203 keygen candidate.

Does NOT touch multiseed_results.log (Sep 21 pre-fix log).
Stops on first FAIL/TIMEOUT/ERROR.
"""
import hashlib
import os
import subprocess
import sys
import time

QV = "/mnt/c/Users/user/Music/computational_rnd_engine/quantumvault"
G9 = f"{QV}/gate_9d_keygen"
TB_DIR = f"{G9}/rtl_candidate/tb"
OUT_DIR = "/tmp"
LOG_PATH = f"{G9}/tb/multiseed/multiseed_fips203_postbug15.log"
OLD_LOG = f"{G9}/tb/multiseed/multiseed_results.log"

RTL_FILES = [
    f"{G9}/rtl_candidate/mlkem_keygen_fips203.sv",
    f"{G9}/rtl_candidate/ntt_core_fips203.sv",
    f"{G9}/rtl_candidate/ntt_butterfly_gs.sv",
    f"{QV}/rtl/ntt_butterfly.sv",
    f"{QV}/rtl/shake_sha3.sv",
    f"{QV}/rtl/keccak_f.sv",
    f"{QV}/gate_9c_vector_arithmetic/rtl/basemultiply.sv",
    f"{QV}/gate_9c_vector_arithmetic/rtl/mod_q_mul.sv",
    f"{G9}/rtl/ntt_sample.sv",
    f"{G9}/rtl/cbd_sampler.sv",
    f"{G9}/rtl/key_encode.sv",
    f"{TB_DIR}/mlkem_keygen_fips203_ms_tb.sv",
]
NUM_SEEDS = 100
VVP_TIMEOUT = 120
COMPILE_TIMEOUT = 60


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def classify(output):
    if "GLOBAL_TIMEOUT" in output or "TIMEOUT after" in output:
        return "TIMEOUT"
    for line in output.splitlines():
        if line.startswith("SEED ") and "PASS" in line:
            return "PASS", line.strip()
        if line.startswith("SEED ") and "FAIL" in line:
            return "FAIL", line.strip()
        if line.startswith("SEED ") and "TIMEOUT" in line:
            return "TIMEOUT", line.strip()
    if "error" in output.lower() or "assert" in output.lower():
        return "ERROR", output.strip()[:300]
    return "NO_OUTPUT", output.strip()[:300]


def has_xz(output):
    # Verilog X/Z often appear as x/z in %x displays or warnings
    low = output.lower()
    return ("x/z" in low) or ("contains x" in low) or ("has x" in low)


def run_seed(seed_idx):
    binary = f"{OUT_DIR}/ms_fips_tb_{seed_idx}"
    cmd_compile = [
        "bash", "-c",
        f"cd {TB_DIR} && iverilog -g2012 -P mlkem_keygen_fips203_ms_tb.SEED_IDX={seed_idx} "
        f"-o {binary} " + " ".join(RTL_FILES) + " 2>&1",
    ]
    try:
        r = subprocess.run(cmd_compile, capture_output=True, text=True, timeout=COMPILE_TIMEOUT)
    except subprocess.TimeoutExpired:
        return "ERROR", "COMPILE_TIMEOUT", ""
    if r.returncode != 0:
        return "ERROR", "COMPILE_FAIL", (r.stdout + r.stderr)[:500]

    # Run from TB_DIR so relative fips_zetas.hex resolves for ntt_core_fips203
    cmd_run = ["bash", "-c", f"cd {TB_DIR} && timeout {VVP_TIMEOUT} vvp {binary} 2>&1"]
    try:
        r = subprocess.run(cmd_run, capture_output=True, text=True, timeout=VVP_TIMEOUT + 30)
    except subprocess.TimeoutExpired:
        return "TIMEOUT", f"SEED {seed_idx}: HOST_TIMEOUT", ""
    out = (r.stdout or "") + (r.stderr or "")
    status, detail = classify(out)
    if status == "PASS" and has_xz(out):
        status = "FAIL"
        detail = detail + " [X/Z_WARN]"
    return status, detail, out


def old_log_fingerprint():
    if not os.path.exists(OLD_LOG):
        return "MISSING"
    return md5(OLD_LOG)


def main():
    old_before = old_log_fingerprint()
    rtl_hashes = {os.path.basename(p): md5(p) for p in RTL_FILES if os.path.isfile(p)}

    results = []
    t0 = time.time()
    stopped_early = False
    first_fail = None

    # Create/overwrite ONLY the new log
    with open(LOG_PATH, "w") as log:
        log.write("ML-KEM-768 FIPS203 Candidate Multi-Seed KeyGen Regression (post-Bug#15)\n")
        log.write("=" * 72 + "\n")
        log.write(f"Started (UTC epoch): {int(t0)}\n")
        log.write(f"NUM_SEEDS={NUM_SEEDS}\n")
        log.write(f"Runner: run_all_fips203_postbug15.py\n")
        log.write(f"Old pre-fix log left untouched: {OLD_LOG}\n")
        log.write(f"Old log MD5 before: {old_before}\n")
        log.write("RTL MD5 hashes:\n")
        for name, h in sorted(rtl_hashes.items()):
            log.write(f"  {h}  {name}\n")
        log.write("=" * 72 + "\n\n")
        log.flush()

        for i in range(NUM_SEEDS):
            status, detail, _raw = run_seed(i)
            elapsed = time.time() - t0
            results.append((i, status, detail))
            line = f"SEED {i:3d}: {detail if detail else status}  [{status}] ({elapsed:.1f}s)\n"
            sys.stdout.write(f"[{i+1:3d}/{NUM_SEEDS}] {line.strip()}\n")
            sys.stdout.flush()
            log.write(line)
            log.flush()

            if status != "PASS":
                stopped_early = True
                first_fail = (i, status, detail)
                err_path = f"{OUT_DIR}/ms_fips_tb_{i}.out"
                # re-run capture already discarded; store detail only
                log.write(f"\n*** STOPPED ON FIRST NON-PASS at seed {i}: {status} ***\n")
                log.write(f"detail: {detail}\n")
                log.flush()
                break

        pass_count = sum(1 for _, s, _ in results if s == "PASS")
        fail_count = sum(1 for _, s, _ in results if s == "FAIL")
        timeout_count = sum(1 for _, s, _ in results if s == "TIMEOUT")
        error_count = sum(1 for _, s, _ in results if s == "ERROR")
        other = len(results) - pass_count - fail_count - timeout_count - error_count

        log.write("\n" + "=" * 72 + "\n")
        log.write(f"SUMMARY: {pass_count} PASS, {fail_count} FAIL, {timeout_count} TIMEOUT, "
                  f"{error_count} ERROR, {other} OTHER out of {len(results)} attempted "
                  f"(target {NUM_SEEDS})\n")
        log.write(f"Stopped early: {stopped_early}\n")
        if first_fail:
            log.write(f"First divergence: seed {first_fail[0]} status={first_fail[1]} detail={first_fail[2]}\n")
        log.write(f"Total time: {time.time()-t0:.1f}s\n")
        old_after = old_log_fingerprint()
        log.write(f"Old log MD5 after: {old_after}\n")
        log.write(f"Old log unchanged: {old_before == old_after}\n")
        log.flush()

    old_after = old_log_fingerprint()
    print("=" * 60)
    print(f"RESULTS: {pass_count} PASS, {fail_count} FAIL, {timeout_count} TIMEOUT, "
          f"{error_count} ERROR out of {len(results)}")
    print(f"Total time: {time.time()-t0:.1f}s")
    print(f"Old log MD5 before/after: {old_before} / {old_after} unchanged={old_before==old_after}")
    print(f"Log: {LOG_PATH}")
    if first_fail:
        print(f"FIRST DIVERGENCE: seed {first_fail[0]} {first_fail[1]}: {first_fail[2]}")
        sys.exit(1)
    if pass_count != NUM_SEEDS:
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
