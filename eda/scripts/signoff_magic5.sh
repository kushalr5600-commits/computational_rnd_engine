#!/bin/sh
echo '=== restore pristine magic binaries:'
tar -xJf /tmp/signoff/magic.tar.xz -C /usr/local
echo '=== create compatibility symlink:'
mkdir -p /host/out
ln -sfn /usr/local /host/out/magic
ls -la /host/out/
echo '=== magic run:'
printf 'puts "MAGIC_VERSION=$VERSION"\nquit\n' > /tmp/mver.tcl
timeout 30 /usr/local/bin/magic -dnull -noconsole < /tmp/mver.tcl 2>&1 | head -10
echo MAGIC_SYMLINK_DONE
