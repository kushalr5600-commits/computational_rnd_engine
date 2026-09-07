#!/usr/bin/env bash
# In-container diagnostic: yosys synthesis (latch check) + formal prep with
# the generated properties wrapper. Mirrors flow.py stage commands.
# Scratch diagnostic — excluded from ruff (eda/scripts).
set -u
cd /work || exit 2
D=5883a330-0055-dc00-6e2c-e532e9399ba6
LOG=/work/_ys_check.log
: > "$LOG"
SRCS=$(cd artifacts/rtl/$D && ls *.sv | grep -v arch_pkg | sed 's|^|artifacts/rtl/'"$D"'/|')
echo "=== yosys synth (latch/abort check) ===" >> "$LOG"
yosys -q -p "read_verilog -sv artifacts/rtl/$D/*.sv; synth -top top; opt_clean; stat" >> "$LOG" 2>&1
echo "SYNTH_RC=$?" >> "$LOG"
echo "=== yosys formal prep ===" >> "$LOG"
SRCARG=$(echo "$SRCS" | tr '\n' ' ')
yosys -q -p "read_verilog -sv -formal $SRCARG; read_verilog -sv -formal artifacts/verification/formal/$D/properties.sva; prep -top formal_properties" >> "$LOG" 2>&1
echo "FORMAL_PREP_RC=$?" >> "$LOG"
grep -iE 'latch|: error|ERROR:' "$LOG" | head -20
tail -15 "$LOG"
echo "YSCHECK_DONE"