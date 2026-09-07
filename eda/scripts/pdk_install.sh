#!/usr/bin/env bash
# Verify + install the prebuilt sky130A PDK (skywater CI tarball) into /opt/pdk.
# Usage: pdk_install.sh [/path/to/pdk-SKY130A.tar.xz]
set -u
TAR=${1:-/tmp/pdk-SKY130A.tar.xz}
EXP=100640940
echo "== size check"; stat -c %s "$TAR"
[ "$(stat -c %s "$TAR")" -eq "$EXP" ] || { echo "SIZE_MISMATCH"; exit 1; }
echo "== xz integrity"; xz -t "$TAR" && echo XZ_OK || { echo "XZ_CORRUPT"; exit 1; }
echo "== archive root entries"; tar -tJf "$TAR" | head -6
echo "== extract to /opt/pdk"
mkdir -p /opt/pdk && tar -xJf "$TAR" -C /opt/pdk
echo "== /opt/pdk:"; ls /opt/pdk
P=/opt/pdk/sky130A
if [ ! -d "$P" ]; then echo "NO sky130A top dir — dumping first archive entries:"; tar -tJf "$TAR" | head -20; exit 1; fi
echo "== top level:"; ls "$P"
echo "== libs.tech/openroad:"; ls "$P/libs.tech/openroad" 2>/dev/null | head -20
echo "== libs.ref dirs:"; ls "$P/libs.ref" 2>/dev/null | head -15
echo "== hd liberty (tt_025C_1v80):"; find "$P/libs.ref" -name 'sky130_fd_sc_hd__tt_025C_1v80.lib' 2>/dev/null | head -3
echo "== hd lef files:"; find "$P/libs.ref/sky130_fd_sc_hd" -name '*.lef' 2>/dev/null | head -5
echo "== techlef:"; find "$P" -name '*.tlef' 2>/dev/null | head -5
echo "== openroad helper scripts:"; ls "$P/libs.tech/openroad" 2>/dev/null | grep -E '\.tcl|rules' | head -10
echo "== magic tarball (bonus):"; ls -l /tmp/magic.tar.xz 2>/dev/null
echo INSTALL_SCRIPT_DONE
