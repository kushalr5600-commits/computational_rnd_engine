#!/bin/sh
set -u
echo "== magic tech dir in PDK:"
ls /usr/local/share/pdk/sky130A/libs.tech/magic/ 2>/dev/null | head -8
echo "== magic version (batch, no X):"
magic -dnull -noconsole --version 2>&1 | head -3
echo MAGIC_RC=$?
echo "== magic loads sky130A tech:"
cat > /tmp/mtech.tcl <<'EOF'
tech load /usr/local/share/pdk/sky130A/libs.tech/magic/sky130A.tech
puts "TECH_LOADED_OK"
quit
EOF
magic -dnull -noconsole /tmp/mtech.tcl 2>&1 | tail -6
echo "== netgen batch banner:"
echo quit | netgen -batch 2>&1 | head -4
echo VERIFY_DONE
