#!/usr/bin/env bash
# Functional smoke test for OpenROAD v2.0 built in this container.
# Runs the bundled gcd_nangate45 testcase (real LEF/LIB/Verilog), which
# exercises read_verilog + read_lef + read_liberty + synthesis plumbing.
set -u

cd /tmp/The-OpenROAD-Project-OpenROAD-4feaf99/test || exit 3

echo "==> openroad -version"
/opt/openroad/bin/openroad -version || exit 10

echo "==> openroad banner+exit (stdin)"
echo "exit" | /opt/openroad/bin/openroad || exit 11

echo "==> sta -version"
/opt/openroad/bin/sta -version || exit 12

echo "==> gcd_nangate45.tcl functional run (300s budget)"
timeout 300 /opt/openroad/bin/openroad -no_init gcd_nangate45.tcl > /tmp/gcd_run.log 2>&1
RC=$?
echo "gcd run exit code: $RC"
echo "--- last 25 lines ---"
tail -25 /tmp/gcd_run.log
echo "SMOKE_TEST_DONE rc=$RC"