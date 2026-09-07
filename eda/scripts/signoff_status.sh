#!/bin/sh
echo MAKE_PROCS:
ps aux | grep -E '[m]ake|[c][+][+]' | head -3
echo KL_LOG_TAIL:
tail -2 /tmp/signoff/klayout_build.log 2>/dev/null | cut -c1-90
echo KL_BIN:
ls /tmp/signoff/klayout/klayout-0.29.11/bin-release/ 2>/dev/null
echo SIGNOFF_DIR:
ls /tmp/signoff/ 2>/dev/null
echo MAGIC_FILES:
ls -la /tmp/magic.tar.xz* 2>/dev/null | head -4
echo NETGEN_FILES:
ls /tmp/signoff/netgen* 2>/dev/null
echo KLAYOUT_TAR:
ls /tmp/signoff/klayout/*.tar* 2>/dev/null
echo STATUS_DONE
