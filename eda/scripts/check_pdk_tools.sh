#!/usr/bin/env bash
echo "=== magic ==="
which magic 2>&1 || echo "magic NOT FOUND"
echo "=== netgen ==="
which netgen 2>&1 || echo "netgen NOT FOUND"
echo "=== openroad ==="
which openroad 2>&1 || echo "openroad NOT FOUND"
echo "=== pydantic ==="
python3 -c "import pydantic; print(pydantic.VERSION)" 2>&1 || echo "pydantic NOT FOUND"
echo "=== sky130A PDK ==="
ls /usr/local/share/pdk/sky130A/ 2>&1 | head -10
echo "=== PDK_ROOT env ==="
echo "PDK_ROOT=$PDK_ROOT"
echo "=== DONE ==="

