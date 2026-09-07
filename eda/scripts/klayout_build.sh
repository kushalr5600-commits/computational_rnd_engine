#!/bin/sh
set -u
echo '=== qt5 build deps:'
apt-get install -y -qq qtbase5-dev qt5-qmake >/tmp/apt_qt.log 2>&1 && echo QT_APT_OK || { echo QT_APT_FAIL; tail -5 /tmp/apt_qt.log; exit 1; }
qmake --version | head -1
cd /tmp/signoff/klayout
tar -xzf klayout.tar.gz
cd klayout-0.29.11
nohup ./build.sh -j4 -without-qtbinding -without-ruby -without-python > /tmp/signoff/klayout_build.log 2>&1 &
echo "BUILD_PID=$!"
echo KL_BUILD_STARTED
