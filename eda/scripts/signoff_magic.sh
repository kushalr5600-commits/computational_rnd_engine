#!/bin/sh
set -u
echo '=== extract magic to /usr/local'
tar -xJf /tmp/signoff/magic.tar.xz -C /usr/local
ls /usr/local/bin | grep -E 'magic|ext2' | head -5
echo '=== ldd magic (missing libs?):'
ldd /usr/local/lib/magic/tcl/magic 2>/dev/null | grep -E 'not found' || echo LDD_MAGIC_OK
ldd /usr/local/bin/magic 2>/dev/null | grep -E 'not found' || echo LDD_BIN_OK
echo '=== magic version:'
echo quit | timeout 20 /usr/local/bin/magic -dnull -noconsole 2>&1 | grep -iE 'magic|version' | head -4
echo MAGIC_STEP_DONE
