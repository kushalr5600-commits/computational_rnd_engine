#!/bin/sh
set -u
echo "== 1) install magic from CI tarball (rooted ./bin ./lib -> /usr/local)"
tar -xJf /tmp/magic.tar.xz -C /usr/local
ls /usr/local/bin/magic && echo MAGIC_BIN_OK
ls /usr/local/lib/magic >/dev/null 2>&1 && echo MAGIC_LIBDIR_OK
echo "== 2) fix netgen python runtime dir + rerun install"
mkdir -p /usr/local/lib/netgen/python
cd /tmp/signoff/netgen-1.5.265 && make install > /tmp/signoff/netgen_inst2.log 2>&1
echo NETGEN_INSTALL_RC=$?
tail -3 /tmp/signoff/netgen_inst2.log | cut -c1-90
ls /usr/local/lib/netgen/ | head -8
echo "== 3) relaunch klayout build (detached)"
cd /tmp/signoff/klayout/klayout-0.29.11
rm -rf build-release bin-release
nohup ./build.sh -j4 -without-qtbinding -without-ruby -without-python > /tmp/signoff/klayout_build2.log 2>&1 &
echo KLAYOUT_BUILD_LAUNCHED
echo SCRIPT_DONE
