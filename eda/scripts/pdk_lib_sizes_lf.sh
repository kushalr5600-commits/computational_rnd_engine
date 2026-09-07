#!/usr/bin/env bash
# Query sizes of the 10 sky130 library submodule repos via GitHub API.
set -u
python3 - <<'PY'
import json, subprocess
libs = ["sky130_fd_io","sky130_fd_pr","sky130_fd_sc_hd","sky130_fd_sc_hdll",
        "sky130_fd_sc_hs","sky130_fd_sc_hvl","sky130_fd_sc_lp",
        "sky130_fd_sc_ls","sky130_fd_sc_ms","sky130_fd_pr_reram"]
total = 0
for lib in libs:
    url = f"https://api.github.com/repos/google/skywater-pdk-libs-{lib}"
    out = subprocess.run(["curl","-s","--max-time","30",url], capture_output=True, text=True)
    try:
        d = json.loads(out.stdout)
    except Exception:
        print(lib, "PARSE_FAIL"); continue
    if "size" in d:
        kb = d["size"]
        total += kb
        print(f"{lib:22s} {kb:>9,} KB (~{kb/1024:.1f} MB)")
    else:
        print(lib, "no size:", str(d)[:120])
print(f"TOTAL: {total/1024:.1f} MB")
PY