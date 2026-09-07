#!/usr/bin/env bash
echo "=== Checking tools ==="
which openroad 2>&1 || echo "openroad: NOT FOUND"
which magic 2>&1 || echo "magic: NOT FOUND"  
which netgen 2>&1 || echo "netgen: NOT FOUND"
which klayout 2>&1 || echo "klayout: NOT FOUND"
echo ""
echo "=== Checking PDK ==="
ls /opt/pdk/ 2>&1 || echo "no /opt/pdk directory"
ls /opt/pdk/sky130A/ 2>&1 | head -20 || echo "no sky130A PDK"
echo ""
echo "=== Checking Python deps ==="
python3 -c "import pydantic; print('pydantic:', pydantic.VERSION)" 2>&1 || echo "pydantic: NOT FOUND"
echo ""
echo "=== Checking tools in PATH ==="
for t in verilator iverilog vvp yosys sby; do
  p=$(command -v $t 2>/dev/null)
  if [ -n "$p" ]; then echo "$t: $p"; else echo "$t: NOT FOUND"; fi
done
echo "DONE"
