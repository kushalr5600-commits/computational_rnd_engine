#!/usr/bin/env bash
# Prove magic loads sky130A tech; record hashes for provenance
set -u
M=/usr/local/share/pdk/sky130A/libs.tech/magic
echo "=== libs.tech/magic contents:"
ls "$M" 2>/dev/null | head -12
echo "=== sky130A tech load test"
if [ -f "$M/sky130A.tech" ]; then
  timeout 60 magic -dnull -noconsole <<EOF 2>&1 | tail -8
tech load $M/sky130A.tech
puts "TECH_LOADED_[tech filename]_layers_[count layers]"
quit
EOF
else
  echo "no sky130A.tech at $M"
fi
echo "=== sha256 provenance"
sha256sum /tmp/magic.tar.xz 2>/dev/null | cut -c1-24
sha256sum /tmp/pdk-SKY130A.tar.xz 2>/dev/null | cut -c1-24
echo TECHTEST_DONE
