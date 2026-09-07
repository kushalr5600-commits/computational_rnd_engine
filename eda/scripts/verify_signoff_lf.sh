#!/usr/bin/env bash
# Complete signoff-tool verification battery
set -u
echo "=== magic version banner"
timeout 25 /usr/bin/magic -dnull -noconsole <<'EOF' 2>&1 | tail -2
puts "MAGIC_VERSION_[magic::version]"
quitall
EOF
echo "=== magic sky130A tech load"
M=/usr/local/share/pdk/sky130A/libs.tech/magic/sky130A.tech
timeout 60 /usr/bin/magic -dnull -noconsole <<EOF 2>&1 | tail -3
tech load $M
puts "TECH_LOADED layers_[count layers]"
quit
EOF
echo "=== netgen banner"
echo 'quit' | timeout 15 netgen -noconsole 2>&1 | grep -i netgen | head -1
echo "=== klayout embedded python (pya)"
timeout 60 klayout -zz -r /tmp/sky130_test/kl_pya_test.py 2>&1 | tail -3
echo "=== klayout embedded ruby (rba)"
timeout 60 klayout -zz -r /tmp/sky130_test/kl_rba_test.rb 2>&1 | tail -3
echo "=== binaries"
ls -la /usr/bin/magic /usr/local/bin/netgen /usr/local/bin/klayout 2>&1
echo VERIFY_BATTERY_DONE
