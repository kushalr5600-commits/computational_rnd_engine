#!/usr/bin/env python3
"""Standalone toolchain verifier — Python stdlib only, no external deps.
Run: docker run --rm --dns 8.8.8.8 rnd-engine-eda:signoff python3 /verify.py"""
import subprocess, shutil, os, json, sys

def ver(cmd):
    """Run a version command, capture output."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
        out = (r.stdout or r.stderr).strip()
        # Clean ANSI colors
        import re
        out = re.sub(r'\x1b\[[0-9;]*m', '', out)
        return out.split('\n')[0][:70] if out else "NO_OUTPUT"
    except Exception as e:
        return f"ERROR: {e}"

def check_tool(name):
    p = shutil.which(name)
    if not p:
        return {"path": "MISSING", "version": "MISSING"}
    return {"path": p}

# Tools and their version commands
tools = {
    "openroad":  ["openroad", "-version"],
    "opensta":   ["sta", "-version"],
    "yosys":     ["yosys", "-V"],
    "verilator": ["verilator", "--version"],
    "iverilog":  ["iverilog", "-V"],
    "abc":       ["abc", "-h"],
    "sby":       ["sby", "--version"],
    "magic":     ["magic", "-version"],
    "netgen":    ["netgen", ""],
    "klayout":   ["klayout", "-v"],
}

results = {"tools": {}, "pdk": {}, "functional": {}}

# Binary + version checks
print("=== TOOL CHECKS ===")
for name, cmd in tools.items():
    info = check_tool(name)
    if info["path"] == "MISSING":
        print(f"  {name:14s} MISSING")
        results["tools"][name] = info
        continue
    v = ver(cmd)
    print(f"  {name:14s} {v}")
    results["tools"][name] = {**info, "version": v}

# PDK
print("\n=== PDK ===")
pdk = "/usr/local/share/pdk/sky130A"
if os.path.isdir(pdk):
    contents = sorted(os.listdir(pdk))
    print(f"  sky130A: present ({len(contents)} top entries)")
    hd = os.path.join(pdk, "libs.ref", "sky130_fd_sc_hd")
    print(f"  sky130_fd_sc_hd: {os.path.isdir(hd)}")
    results["pdk"] = {"present": True, "contents": contents, "hd": os.path.isdir(hd)}
else:
    print("  sky130A: MISSING")
    results["pdk"] = {"present": False}

# Functional checks
print("\n=== FUNCTIONAL TESTS ===")
# Magic sky130A tech load (quick)
try:
    r = subprocess.run(["magic", "-dnull", "-noconsole", "-log", "/dev/null", "-nowarn",
                        "-dnull", "-noconsole", "-c", "quit"],
                        capture_output=True, text=True, timeout=10,
                        env={**os.environ, "CAD": "/usr/share", "MAGIC_HOME": "/usr/share/magic"})
    print("  magic batch launch: OK")
    results["functional"]["magic_batch"] = "OK"
except Exception as e:
    print(f"  magic batch launch: {e}")
    results["functional"]["magic_batch"] = str(e)

# KLayout batch
try:
    r = subprocess.run(["klayout", "-zz", "-rd", "batchmode=true", "-e", "-noplevel", "-rd", "help"],
                       capture_output=True, text=True, timeout=10)
    has_output = "KLayout" in (r.stdout + r.stderr)
    print(f"  klayout batch: {'OK' if has_output else 'NO_OUTPUT'}")
    results["functional"]["klayout_batch"] = "OK" if has_output else "FAIL"
except Exception as e:
    print(f"  klayout batch: {e}")
    results["functional"]["klayout_batch"] = str(e)

# OpenROAD quick init
try:
    r = subprocess.run(["openroad", "-no_init", "-cmd", "quit"],
                       capture_output=True, text=True, timeout=10)
    has_init = "OpenROAD" in (r.stdout + r.stderr)
    print(f"  openroad init: {'OK' if has_init else 'NO_OUTPUT'}")
    results["functional"]["openroad_init"] = "OK" if has_init else "FAIL"
except Exception as e:
    print(f"  openroad init: {e}")
    results["functional"]["openroad_init"] = str(e)

print("\n=== SUMMARY ===")
all_tools = all(results["tools"][t]["path"] != "MISSING" for t in tools)
pdk_ok = results["pdk"].get("present", False)
print(f"  All tools present: {all_tools}")
print(f"  PDK installed: {pdk_ok}")
func_ok = all(v == "OK" for v in results["functional"].values() if "ERROR" not in v)
print(f"  Functional tests: {func_ok}")
print(f"  OVERALL: {'READY' if (all_tools and pdk_ok) else 'INCOMPLETE'}")

# Write JSON report
with open("/work/eda/verify_report.json", "w") as f:
    json.dump(results, f, indent=2, default=str)
print("\nVerify report written to /work/eda/verify_report.json")
