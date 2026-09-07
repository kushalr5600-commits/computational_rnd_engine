#!/usr/bin/env bash
# Install the CI prebuilt sky130A tree (rooted at ./usr/local/...) to / .
set -u
TAR=/tmp/pdk-SKY130A.tar.xz
rm -rf /opt/pdk   # remove the earlier misplaced extraction
echo "== extracting to / (this may take a minute)"
tar -xJf "$TAR" -C /
P=/usr/local/share/pdk/sky130A
[ -d "$P" ] || { echo "MISSING $P"; exit 1; }
echo "== top:"; ls "$P"
echo "== libs.ref:"; ls "$P/libs.ref" 2>/dev/null
echo "== libs.tech:"; ls "$P/libs.tech" 2>/dev/null
echo "== libs.tech/openroad:"; ls "$P/libs.tech/openroad" 2>/dev/null | head -30
echo "== hd techlef:"; find "$P/libs.ref/sky130_fd_sc_hd" -name '*.tlef' 2>/dev/null | head
echo "== hd lef:"; ls "$P/libs.ref/sky130_fd_sc_hd/lef" 2>/dev/null | head -5
echo "== hd tt lib:"; ls "$P/libs.ref/sky130_fd_sc_hd/lib" 2>/dev/null | grep 'tt_025C_1v80' | head -5
echo "== sizes:"; du -sh "$P" "$P/libs.ref" "$P/libs.tech" 2>/dev/null
echo INSTALL2_DONE
