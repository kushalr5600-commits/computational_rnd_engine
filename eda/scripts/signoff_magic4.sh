#!/bin/sh
echo '=== files containing /host/out/magic:'
FILES=$(grep -rl '/host/out/magic' /usr/local/lib/magic /usr/local/bin 2>/dev/null)
echo "$FILES"
echo '=== length-preserving patch (15 chars -> 10 + 5 NUL):'
for f in $FILES; do
  perl -pi -e 's#/host/out/magic#/usr/local\x00\x00\x00\x00\x00#g' "$f"
done
echo '=== remaining refs:'
grep -rl '/host/out/magic' /usr/local/lib/magic /usr/local/bin 2>/dev/null || echo NONE
echo '=== magic run:'
printf 'puts "MAGIC_VERSION=$VERSION"\nquit\n' > /tmp/mver.tcl
timeout 30 /usr/local/bin/magic -dnull -noconsole < /tmp/mver.tcl 2>&1 | head -10
echo MAGIC_PATCH_DONE
