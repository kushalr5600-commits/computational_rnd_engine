#!/usr/bin/env bash
echo "=== /opt contents ==="
ls /opt/ 2>&1
echo "=== openroad ==="
which openroad 2>&1
openroad -version 2>&1 | head -3
echo "=== PDK search ==="
find / -maxdepth 5 -name "sky130A" -type d 2>/dev/null | head -5
echo "=== PDK_ROOT ==="
echo $PDK_ROOT
echo "=== DONE ==="
