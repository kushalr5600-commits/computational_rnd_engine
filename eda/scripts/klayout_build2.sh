#!/usr/bin/env bash
# Extract + build KLayout v0.29.11 from pinned source (background-friendly)
set -u
TAR=/tmp/klayout-0.29.11.tar.gz
echo "== size check"
stat -c '%s (expect 97526183)' "$TAR" || exit 1
echo "== sha256"
sha256sum "$TAR"
echo "== extract"
rm -rf /tmp/klayout-0.29.11
tar -xzf "$TAR" -C /tmp && echo EXTRACT_OK
ls /tmp/klayout-0.29.11 | head -8
echo "== build start (log: /tmp/klayout_build.log)"
nohup bash -c 'cd /tmp/klayout-0.29.11 && ./build.sh -j4 > /tmp/klayout_build.log 2>&1 && echo KL_BUILD_OK >> /tmp/klayout_build.log || echo KL_BUILD_FAIL >> /tmp/klayout_build.log' > /dev/null 2>&1 &
echo BUILD_STARTED
