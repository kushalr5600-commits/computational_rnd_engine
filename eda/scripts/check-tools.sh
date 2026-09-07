#!/usr/bin/env bash
# check-tools.sh — verify all EDA tools are present and executable
# Exit code: 0 if all READY, 1 if any MISSING/FAILED
set -euo pipefail

TOOLS="verilator iverilog vvp yosys abc sby openroad opensta magic netgen klayout ghdl"

fail=0
for tool in $TOOLS; do
    if command -v "$tool" &>/dev/null; then
        path=$(command -v "$tool")
        version=$("$tool" --version 2>&1 | head -1 || echo "unknown")
        echo "OK   $tool  $path  $version"
    else
        echo "MISSING  $tool"
        fail=1
    fi
done

exit $fail