#!/usr/bin/env bash
set -u
cd /tmp
# copy project
mkdir -p /tmp/rnd
cp -r /mnt/c/Users/user/Music/computational_rnd_engine/* /tmp/rnd/
cd /tmp/rnd
# install deps
pip3 install -q pydantic pyyaml 2>&1 | tail -2
python3 -c 'import pydantic, yaml; print("DEPS_OK")'
# install project
pip3 install -q -e . 2>&1 | tail -5
python3 -c 'import rnd_engine; print("RND_PKG_OK")'
# check for datetime.UTC issue
python3 -c 'import datetime; print(datetime.UTC)' 2>&1 || echo "NEEDS_UTC_SHIM"
# tool check
echo "=== TOOL BINARIES ==="
for t in verilator iverilog yosys abc sby openroad sta magic netgen klayout; do
  printf "%-12s: " "$t"
  command -v "$t" || echo "MISSING"
done
echo "=== TOOL VERSIONS ==="
openroad -version 2>&1 | head -1
yosys -V 2>&1 | head -1
magic -version 2>&1 | head -1
netgen -v 2>&1 | head -1
klayout -v 2>&1 | head -1
echo "=== PDK ==="
ls /usr/local/share/pdk/sky130A/
echo "=== DONE ==="
