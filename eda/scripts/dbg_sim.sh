#!/usr/bin/env bash
# In-container diagnostic: cycle-by-cycle pipeline trace (debug TB).
# Scratch diagnostic — excluded from ruff (eda/scripts).
set -u
cd /work || exit 2
D=5883a330-0055-dc00-6e2c-e532e9399ba6
LOG=/work/_dbg_check.log
: > "$LOG"
iverilog -g2012 -s dbg_tb -o /tmp/dbg.vvp \
  eda/scripts/dbg_tb.sv artifacts/rtl/$D/*.sv >> "$LOG" 2>&1
echo "DBG_COMPILE_RC=$?" >> "$LOG"
timeout 90 vvp -n /tmp/dbg.vvp >> "$LOG" 2>&1
echo "DBG_RUN_RC=$?" >> "$LOG"
tail -70 "$LOG"
echo "DBGCHECK_DONE"