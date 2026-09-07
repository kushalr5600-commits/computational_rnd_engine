#!/usr/bin/env python3
"""Self-contained tool status verifier. Run inside signoff container."""
import datetime, subprocess, shutil, os, json, sys

# Patch UTC for Python 3.10
if not hasattr(datetime, "UTC"):
    datetime.UTC = datetime.timezone.utc

results = {"deps": {}, "tools": {}, "versions": {}, "pdk": {}, "error": None}

# Check deps
try:
    import pydantic, yaml
    results["deps"]["pydantic"] = "OK"
    results["deps"]["yaml"] = "OK"
except ImportError as e:
    results["deps"]["error"] = str(e)

# Check tools
for t in ["verilator","iverilog","yosys","abc","sby","openroad","sta","magic","netgen","klayout"]:
    p = shutil.which(t)
    results["tools"][t] = p or "MISSING"

# Check versions
version_cmds = {
    "openroad": ["-version"],
    "yosys": ["-V"],
    "verilator": ["--version"],
    "iverilog": ["-V"],
    "magic": ["-version"],
    "netgen": ["-v"],
}
for tool, args in version_cmds.items():
    try:
        r = subprocess.run([tool] + args, capture_output=True, text=True, timeout=10)
        results["versions"][tool] = (r.stdout or r.stderr).strip()[:80]
    except Exception as e:
        results["versions"][tool] = f"ERROR: {e}"

# Check klayout via Ruby
try:
    r = subprocess.run(["klayout", "-zz", "-rd", "batchmode=true", "-noplevel", "-rd", "help"],
                      capture_output=True, text=True, timeout=10)
    results["versions"]["klayout"] = "CLI_OK" if r.returncode == 0 or len(r.stdout) > 0 else "CLI_FAIL"
except Exception as e:
    results["versions"]["klayout"] = f"ERROR: {e}"

# Check PDK
pdk = "/usr/local/share/pdk/sky130A"
results["pdk"]["path"] = pdk
results["pdk"]["exists"] = os.path.isdir(pdk)
if results["pdk"]["exists"]:
    results["pdk"]["contents"] = os.listdir(pdk)[:10]
    hd = os.path.join(pdk, "libs.ref/sky130_fd_sc_hd")
    results["pdk"]["sky130_fd_sc_hd"] = os.path.isdir(hd)

print("VERIFY_DONE")
print(json.dumps(results, indent=2, default=str))
