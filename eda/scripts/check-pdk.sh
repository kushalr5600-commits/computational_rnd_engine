#!/usr/bin/env bash
# check-pdk.sh — verify the SKY130A PDK tree structure
# Checks for required LEF/Liberty/GDS/SPICE/technology/DRC/LVS files
set -euo pipefail

PDK_ROOT="${PDK_ROOT:-${1:-}}"
if [ -z "$PDK_ROOT" ]; then
    echo "PDK_ROOT not set"
    exit 1
fi

if [ ! -d "$PDK_ROOT" ]; then
    echo "PDK_ROOT not a directory: $PDK_ROOT"
    exit 1
fi

# Required file patterns for sky130A
REQUIRED_PATTERNS=(
    "sky130A/libs.ref/sky130_fd_sc_hd/liberty/sky130_fd_sc_hd__tt_025C_1v80.lib"
    "sky130A/libs.ref/sky130_fd_sc_hd/lef/sky130_fd_sc_hd.lef"
    "sky130A/libs.ref/sky130_fd_sc_hd/gds/sky130_fd_sc_hd.gds"
    "sky130A/libs.tech/magic/sky130A.magicrc"
    "sky130A/libs.tech/netgen/sky130A_setup.tcl"
)

fail=0
for pattern in "${REQUIRED_PATTERNS[@]}"; do
    if [ -e "$PDK_ROOT/$pattern" ]; then
        echo "OK   $pattern"
    else
        echo "MISSING  $pattern"
        fail=1
    fi
done

if [ $fail -eq 0 ]; then
    echo "PDK OK: $PDK_ROOT"
else
    echo "PDK INCOMPLETE: $PDK_ROOT"
fi

exit $fail