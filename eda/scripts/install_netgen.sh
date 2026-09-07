#!/usr/bin/env bash
# Build netgen 1.5.265 from the opencircuitdesign.com tarball (pinned).
set -e
cd /tmp
rm -rf netgen-1.5.265
tar -xzf netgen-1.5.265.tgz
cd netgen-1.5.265
./configure --prefix=/usr/local > /tmp/netgen_cfg.log 2>&1 || { echo CONFIG_FAIL; tail -20 /tmp/netgen_cfg.log; exit 1; }
echo CONFIG_OK
make -j4 > /tmp/netgen_make.log 2>&1 || { echo MAKE_FAIL; tail -30 /tmp/netgen_make.log; exit 1; }
echo MAKE_OK
make install > /tmp/netgen_inst.log 2>&1 || { echo INSTALL_FAIL; tail -20 /tmp/netgen_inst.log; exit 1; }
echo INSTALL_OK
which netgen
echo quit | netgen -batch 2>&1 | head -4 || true
echo NETGEN_BUILD_DONE
