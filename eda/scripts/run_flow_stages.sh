#!/usr/bin/env bash
# In-container: run the real lint/simulation/formal/synthesis stages for the
# seed-42 candidate and print the receipt summary. Scratch diagnostic.
set -u
cd /work || exit 2
export PYTHONPATH=/work
# Ensure Python deps are available (pydantic + pyyaml needed by flow.py)
pip3 install --no-cache-dir pydantic pyyaml 1>/dev/null 2>&1 || true
LOG=/work/_flow_check.log
: > "$LOG"
python3 eda/scripts/run_cli.py flow \
  --stages lint,simulation,formal,synthesis --seed 42 \
  --out-dir artifacts --config-dir configs >> "$LOG" 2>&1
echo "FLOW_RC=$?" >> "$LOG"
tail -50 "$LOG"
echo "FLOWCHECK_DONE"