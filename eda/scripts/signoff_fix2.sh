#!/usr/bin/env bash
set -u
apt-get update -qq > /tmp/apt_upd.log 2>&1 || { echo APT_UPDATE_FAIL; tail -3 /tmp/apt_upd.log; }
if DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
     qtbase5-dev qttools5-dev qttools5-dev-tools libqt5svg5-dev \
     ruby-dev ruby zlib1g-dev libbz2-dev tk8.6 tcl8.6 \
     libgl1 libglu1-mesa libglx-mesa0 libx11-dev libxext-dev \
     > /tmp/apt4.log 2>&1; then
  echo APT4_OK
else
  echo APT4_FAIL; tail -8 /tmp/apt4.log
fi
echo "=== magic banner retest"
timeout 20 bash -c 'echo "puts \"MAGIC_VER [magic::version]\"; quitall" | magic -dnull -noconsole' 2>&1 | tail -4
echo "=== klayout tarball progress"
ls -la /tmp/klayout-0.29.11.tar.gz 2>/dev/null || echo "not yet"
echo RETEST_DONE
