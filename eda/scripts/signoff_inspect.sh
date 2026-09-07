#!/bin/sh
echo MAGIC_TAR_ROOT:
tar -tJf /tmp/magic.tar.xz 2>/dev/null | head -6
echo MAGIC_TAR_COUNT:
tar -tJf /tmp/magic.tar.xz 2>/dev/null | wc -l
echo NETGEN_BIN:
command -v netgen
ls -la /usr/local/bin/netgen 2>/dev/null
echo NETGEN_MAKE_TAIL:
tail -3 /tmp/signoff/netgen_make.log 2>/dev/null | cut -c1-90
echo NETGEN_INST_TAIL:
tail -5 /tmp/signoff/netgen_inst.log 2>/dev/null | cut -c1-90
echo NETGEN_VERSION_FILE:
cat /tmp/signoff/netgen-1.5.265/VERSION 2>/dev/null
echo NPROC:
nproc
echo INSPECT_DONE
