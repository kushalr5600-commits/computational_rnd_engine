#!/usr/bin/env bash
echo "=== opensta ==="
which opensta 2>&1 || echo "opensta NOT FOUND"
echo "=== sta ==="
which sta 2>&1 || echo "sta NOT FOUND"
echo "=== openroad dir ==="
ls /opt/openroad/bin/ 2>&1 || echo "no /opt/openroad/bin"
echo "=== DONE ==="
