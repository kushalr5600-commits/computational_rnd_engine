#!/bin/sh
set -u
cd /tmp/signoff
tar -xzf netgen-1.5.265.tgz
cd netgen-1.5.265
./configure --prefix=/usr/local >/tmp/signoff/netgen_conf.log 2>&1 || { echo CONFIGURE_FAIL; tail -15 /tmp/signoff/netgen_conf.log; exit 1; }
echo CONFIGURE_OK
make -j4 >/tmp/signoff/netgen_make.log 2>&1 || { echo MAKE_FAIL; tail -15 /tmp/signoff/netgen_make.log; exit 1; }
echo MAKE_OK
make install >/tmp/signoff/netgen_inst.log 2>&1 || { echo INSTALL_FAIL; tail -10 /tmp/signoff/netgen_inst.log; exit 1; }
echo INSTALL_OK
echo '=== netgen version:'
echo quit | timeout 20 /usr/local/bin/netgen -batch 2>&1 | head -4
echo NETGEN_STEP_DONE
