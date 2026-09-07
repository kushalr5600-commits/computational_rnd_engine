#!/usr/bin/env bash
# smoke-test.sh — run a minimal end-to-end smoke test of the EDA flow
# Uses a tiny known-good design, not a candidate artifact
set -euo pipefail

TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

echo "=== Verilator lint-only smoke test ==="
cat > $TMPDIR/smoke.sv << 'EOF'
module smoke(input logic clk, output logic q);
  always_ff @(posedge clk) q <= ~q;
endmodule
EOF
verilator --lint-only --top-module smoke $TMPDIR/smoke.sv
echo "VERILATOR: PASS"

echo "=== Yosys synthesis smoke test ==="
yosys -p "read_verilog $TMPDIR/smoke.sv; synth -top smoke; write_verilog $TMPDIR/smoke_synth.v"
if [ -f $TMPDIR/smoke_synth.v ]; then
    echo "YOSYS: PASS"
else
    echo "YOSYS: FAIL"
    exit 1
fi

echo "=== All smoke tests PASSED ==="