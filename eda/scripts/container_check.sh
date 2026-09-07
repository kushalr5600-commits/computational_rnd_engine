#!/usr/bin/env bash
# In-container verification: tools on PATH, python deps, rnd_engine importable.
set -u
echo "=== TOOL BINARIES ==="
for t in verilator iverilog vvp yosys abc sby openroad opensta magic netgen klayout; do
  if command -v "$t" >/dev/null 2>&1; then
    printf '%-10s PRESENT (%s)\n' "$t" "$(command -v "$t")"
  else
    printf '%-10s MISSING\n' "$t"
  fi
done
echo "=== PYTHON ==="
python3 --version
python3 -c "import pydantic, yaml" && echo "pydantic+yaml OK" || echo "deps MISSING"
python3 -c "import rnd_engine; print('rnd_engine OK from', rnd_engine.__file__)" 2>&1 || echo "rnd_engine NOT importable"
echo "=== REPO MOUNT ==="
ls /work/rnd_engine >/dev/null 2>&1 && echo "/work/rnd_engine present" || echo "/work/rnd_engine MISSING"
ls /work/configs/default.yaml >/dev/null 2>&1 && echo "configs mounted" || echo "configs MISSING"
echo "=== PDK ==="
ls /usr/local/share/pdk/sky130A/libs.ref/sky130_fd_sc_hd/lef >/dev/null 2>&1 && echo "PDK lef present" || echo "PDK lef MISSING"
echo "DONE"