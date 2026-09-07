#!/usr/bin/env bash
# Full toolchain status verification
set -u
echo "=== Installing Python deps ==="
pip3 install -q pydantic pyyaml 2>&1 | tail -1
python3 -c 'import pydantic, yaml; print("DEPS_OK")'
echo
echo "=== Patching datetime.UTC (Python 3.10 compat — no engine files touched) ==="
# Create sitecustomize.py for UTC alias
mkdir -p /usr/local/lib/python3.10/dist-packages/
cat > /usr/local/lib/python3.10/dist-packages/sitecustomize.py << 'PYEOF'
import datetime
if not hasattr(datetime, 'UTC'):
    datetime.UTC = datetime.timezone.utc
PYEOF
python3 -c 'import datetime; print("UTC_OK" if hasattr(datetime,"UTC") else "UTC_FAIL")'
echo
echo "=== Tool binaries ==="
for t in verilator iverilog yosys abc sby openroad sta magic netgen klayout; do
    printf "%-14s " "$t"; command -v "$t" || echo MISSING
done
echo
echo "=== Tool versions ==="
echo "openroad:"; openroad -version 2>&1 | head -1
echo "yosys:"; yosys -V 2>&1 | head -1
echo "verilator:"; verilator --version 2>&1 | head -1
echo "iverilog:"; iverilog -V 2>&1 | head -1
echo "magic:"; magic -version 2>&1 | head -1
echo "netgen:"; netgen -v 2>&1 | head -1
echo "klayout (CLI):"; klayout -zz -rd batchmode=true -e -noplevel -rd help 2>&1 | head -2 || echo "(CLI works with -zz)"
echo
echo "=== PDK ==="
ls /usr/local/share/pdk/sky130A/
echo
echo "=== eda-doctor ==="
cd /work
python3 -m rnd_engine.cli eda-doctor 2>&1 | tail -60
echo "DOCTOR_DONE"
