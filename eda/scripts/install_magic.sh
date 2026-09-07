#!/usr/bin/env bash
# Install the open_pdks CI prebuilt Magic 8.3.305 (binary built with the same
# CI run 10010 that produced the installed sky130A PDK).
set -e
TAR=/tmp/magic.tar.xz
stat -c 'magic tar size=%s (expect 2506760)' $TAR
echo "== archive root entries:"
tar -tJf $TAR | head -8
tar -xJf $TAR -C /
M=/usr/local/bin/magic
[ -f "$M" ] || { echo "MISSING $M"; find /usr/local -name magic -maxdepth 4 2>/dev/null; exit 1; }
echo "== ldd:"
ldd $M 2>&1 | head -20
echo "== version banner:"
echo quit | timeout 20 magic -dnull -noconsole 2>&1 | head -5 || echo MAGIC_BANNER_TIMEOUT
echo MAGIC_INSTALL_DONE
