#!/usr/bin/env bash
echo "=== PDK_ROOT ==="
echo "PDK_ROOT=$PDK_ROOT"
echo "=== /usr/local/share/pdk/sky130A ==="
ls /usr/local/share/pdk/sky130A/ 2>&1
echo "=== required paths ==="
for p in libs.ref/sky130_fd_sc_hd/lef libs.ref/sky130_fd_sc_hd/lib libs.ref/sky130_fd_sc_hd/gds libs.ref/sky130_fd_sc_hd/spice libs.tech/magic libs.tech/netgen libs.tech/klayout; do
  if [ -e "/usr/local/share/pdk/sky130A/$p" ]; then
    echo "FOUND: $p"
  else
    echo "MISSING: $p"
  fi
done
echo "=== PDK_CHECK_DONE ==="
