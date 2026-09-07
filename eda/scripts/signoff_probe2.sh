#!/usr/bin/env bash
# Probe klayout.org name variants + check codeload tarball progress
set -u
for u in "Ubuntu-22/klayout_0.29.11_amd64.deb" "Ubuntu-20/klayout_0.29.11-1_amd64.deb" "Ubuntu-22.04/klayout_0.29.11-1_amd64.deb"; do
  code=$(curl -s -o /dev/null -w '%{http_code}' -I -m 20 "https://www.klayout.org/downloads/$u")
  echo "$u -> $code"
done
echo "=== codeload tarball:"
ls -la /tmp/klayout-0.29.11.tar.gz 2>/dev/null || echo "no tarball yet"
echo "=== magic internals:"
file /usr/bin/magic | head -1
grep -a -m2 -n "MAGIC_EXEC\|magicdnull" /usr/bin/magic 2>/dev/null | head -4
ls /usr/lib/magic 2>/dev/null | head -8
ls /usr/lib/magic/tcl 2>/dev/null | head -6
echo "=== real magic ELF candidates:"
find /usr/lib /usr/bin /opt -maxdepth 4 -name 'magic*' -type f 2>/dev/null | xargs -r file 2>/dev/null | grep -i elf | head -5
echo "=== apt2 status:"
ps aux | grep -E 'apt|dpkg' | grep -v grep | head -3
tail -2 /tmp/apt2.log 2>/dev/null
echo PROBE_DONE
