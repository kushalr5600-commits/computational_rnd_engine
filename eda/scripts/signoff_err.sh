#!/bin/sh
echo CONTEXT:
grep -n -i -B4 -A10 'error' /tmp/signoff/klayout_build2.log | head -40
echo LOG_SIZE:
wc -l /tmp/signoff/klayout_build2.log
echo BUILD_SH_HEAD:
head -30 /tmp/signoff/klayout/klayout-0.29.11/build.sh
echo ERR_DONE
