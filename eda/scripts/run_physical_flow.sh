#!/usr/bin/env bash
# In-container: run physical stages only (after RTL stages pass).
set -u
cd /work || exit 2
export PYTHONPATH=/work
export PDK_ROOT=/usr/local/share/pdk
export OPENSTA_BIN=/usr/local/bin/sta
export OPENROAD_BIN=/usr/local/bin/openroad
export MAGIC_BIN=/usr/bin/magic
export NETGEN_BIN=/usr/local/bin/netgen
LOG=/work/_physical_flow.log
python3 -c "import pydantic" 2>/dev/null || pip3 install --no-cache-dir pydantic pyyaml 2>&1 | tail -3
echo "=== Running physical flow (physical, sta, drc, lvs) ==="
python3 eda/scripts/run_cli.py flow \
  --stages physical,sta,drc,lvs \
  --seed 42 \
  --out-dir /work/artifacts \
  --config-dir configs > "$LOG" 2>&1
echo "FLOW_RC=$?" >> "$LOG"
tail -80 "$LOG"
echo "PHYSICAL_FLOW_DONE"
