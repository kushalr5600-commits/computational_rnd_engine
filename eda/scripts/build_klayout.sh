#!/usr/bin/env bash
# Build KLayout 0.29.11 from the official GitHub tag tarball (pinned).
# Waits for the background apt Qt install to finish first.
LOG=/tmp/klayout_build.log
{
echo "== waiting for apt (polling for APT_RC in /tmp/apt_klayout.log)"
for i in $(seq 1 90); do
  grep -q APT_RC /tmp/apt_klayout.log 2>/dev/null && break
  sleep 10
done
tail -2 /tmp/apt_klayout.log
grep APT_RC /tmp/apt_klayout.log || { echo APT_NEVER_FINISHED; exit 1; }
cd /tmp
rm -rf klayout-0.29.11
tar -xzf klayout-0.29.11.tar.gz
cd klayout-0.29.11
echo "== running build.sh -j4 (this is the long pole)"
./build.sh -j4 > /tmp/klayout_make.log 2>&1 || { echo BUILD_FAIL; tail -40 /tmp/klayout_make.log; exit 1; }
echo BUILD_OK
BIN=$(find . -type f -name klayout -perm -u+x | head -1)
echo "binary: $BIN"
[ -n "$BIN" ] || { echo NO_BINARY; exit 1; }
cp "$BIN" /usr/local/bin/klayout
/usr/local/bin/klayout -v
echo KLAYOUT_BUILD_DONE
} > $LOG 2>&1
