#!/bin/sh
echo KL_TAIL:
tail -2 /tmp/signoff/klayout_build2.log 2>/dev/null | cut -c1-90
echo KL_CXX_PROCS:
ps aux | grep '[c][+][+]' | wc -l
echo KL_BIN:
ls /tmp/signoff/klayout/klayout-0.29.11/bin-release/ 2>/dev/null
echo KL_ERRORS:
grep -ciE 'error' /tmp/signoff/klayout_build2.log 2>/dev/null
echo POLL_DONE
