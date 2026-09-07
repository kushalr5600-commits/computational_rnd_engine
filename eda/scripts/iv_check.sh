#!/usr/bin/env bash
# In-container diagnostic: iverilog compile + vvp run of the generated TB/RTL.
# Scratch diagnostic — excluded from ruff (eda/scripts).
set -u
cd /work || exit 2
D=5883a330-0055-dc00-6e2c-e532e9399ba6
LOG=/work/_iv_check.log
: > "$LOG"
echo "=== iverilog compile ===" >> "$LOG"
iverilog -g2012 -s tb_top -o /tmp/tb.vvp \
  artifacts/verification/$D/tb_top.sv artifacts/rtl/$D/*.sv >> "$LOG" 2>&1
echo "COMPILE_RC=$?" >> "$LOG"
echo "=== vvp run (timeout 120) ===" >> "$LOG"
timeout 120 vvp -n /tmp/tb.vvp >> "$LOG" 2>&1
echo "VVP_RC=$?" >> "$LOG"
tail -25 "$LOG"
echo "IVCHECK_DONE"