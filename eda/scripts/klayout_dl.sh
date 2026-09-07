#!/bin/sh
set -u
K=/tmp/signoff/klayout
mkdir -p $K && cd $K
URL='https://www.klayout.org/downloads/source/klayout-0.29.11.tar.gz'
i=0
while [ $i -lt 12 ]; do
  i=$((i+1))
  curl -sS -C - -m 45 -o klayout.tar.gz "$URL" && break
  sleep 2
done
SZ=$(stat -c %s klayout.tar.gz 2>/dev/null || echo 0)
echo "attempts=$i size=$SZ"
if [ "$SZ" -lt 30000000 ]; then echo KL_DL_TOO_SMALL; exit 1; fi
echo '=== sha256:'
sha256sum klayout.tar.gz
echo '=== tarball root:'
tar -tzf klayout.tar.gz | head -4
echo KL_DL_DONE
