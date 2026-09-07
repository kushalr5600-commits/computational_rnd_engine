#!/usr/bin/env bash
set -u
echo "== install missing Qt modules"
if DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
     qtmultimedia5-dev libqt5xmlpatterns5-dev > /tmp/apt5.log 2>&1; then
  echo APT5_OK
else
  echo APT5_FAIL; tail -5 /tmp/apt5.log; exit 1
fi
echo "== rebuild klayout"
cd /tmp/klayout-0.29.11
rm -rf build-release bin-release
nohup bash -c 'cd /tmp/klayout-0.29.11 && ./build.sh -j4 > /tmp/klayout_build.log 2>&1 && echo KL_BUILD_OK >> /tmp/klayout_build.log || echo KL_BUILD_FAIL >> /tmp/klayout_build.log' > /dev/null 2>&1 &
echo REBUILD_STARTED
