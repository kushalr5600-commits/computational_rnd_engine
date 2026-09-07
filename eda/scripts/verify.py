#!/usr/bin/env python3
"""Quick status verifier — runs in the signoff container."""
import datetime, subprocess, shutil, os, pydantic, yaml
if not hasattr(datetime, "UTC"):
    datetime.UTC = datetime.timezone.utc
print("DEPS_OK", datetime.UTC)
print("=== TOOLS ===")
for t in ["verilator","iverilog","yosys","abc","sby","openroad","sta","magic","netgen","klayout"]:
    p = shutil.which(t)
    print(f"  {t:14s}: {p or 'MISSING'}")
print("=== VERSIONS ===")
subs = [
    ("openroad","-version"),
    ("yosys","-V"),
    ("verilator","--version"),
    ("iverilog","-V"),
    ("magic","-version"),
    ("netgen","-v"),
]
for tool, flag in subs:
    try:
        r = subprocess.run([tool, flag], capture_output=True, text=True, timeout=10)
        print(f"  {tool}: {(r.stdout or r.stderr).strip()[:60]}")
    except Exception as e:
        print(f"  {tool}: ERROR {e}")
print("=== PDK ===")
pdk = "/usr/local/share/pdk/sky130A"
if os.path.isdir(pdk):
    print("  sky130A present:", os.listdir(pdk))
    hd = os.path.join(pdk, "libs.ref/sky130_fd_sc_hd")
    print("  sky130_fd_sc_hd present:", os.path.isdir(hd))
else:
    print("  sky130A MISSING")
print("=== DONE ===")
