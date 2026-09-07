#!/bin/sh
cd /tmp/signoff/klayout/klayout-0.29.11
rm -rf build-release bin-release
nohup ./build.sh -j4 -without-qtbinding > /tmp/signoff/klayout_build3.log 2>&1 &
echo RELAUNCHED_PID=$!
sleep 25
echo EARLY_TAIL:
tail -3 /tmp/signoff/klayout_build3.log | cut -c1-100
echo KL_CXX_PROCS:
ps aux | grep '[c][+][+]' | wc -l
echo RELAUNCH_DONE
