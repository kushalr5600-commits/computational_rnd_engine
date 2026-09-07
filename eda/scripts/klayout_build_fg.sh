#!/usr/bin/env bash
set -u
cd /tmp/klayout-0.29.11
rm -rf build-release bin-release
echo "FG_BUILD_START $(date +%H:%M:%S)"
./build.sh -j4 > /tmp/klayout_build.log 2>&1
rc=$?
echo "FG_BUILD_RC=$rc $(date +%H:%M:%S)"
tail -3 /tmp/klayout_build.log
exit $rc
