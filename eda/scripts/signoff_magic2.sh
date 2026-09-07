#!/bin/sh
echo '=== wrapper head:'
head -75 /usr/local/bin/magic | tail -20
echo '=== real binary location:'
ls /usr/local/lib/magic/tcl/ 2>/dev/null | head -6
echo '=== hardcoded /host/out refs in wrapper:'
grep -c 'host/out' /usr/local/bin/magic
echo '=== patch wrappers:'
sed -i 's#/host/out/magic#/usr/local#g' /usr/local/bin/magic /usr/local/bin/ext2sim /usr/local/bin/ext2spice 2>/dev/null
grep -c 'host/out' /usr/local/bin/magic || true
echo '=== magic version after patch:'
echo quit | timeout 20 /usr/local/bin/magic -dnull -noconsole 2>&1 | grep -iE '^magic|version' | head -4
echo MAGIC_FIX_DONE
