#!/usr/bin/env bash
# Test codeload direct-download with resume for io (35 MB). Retry loop.
cd /tmp
URL=https://codeload.github.com/google/skywater-pdk-libs-sky130_fd_io/tar.gz/01b18699b4102d8e54ad1406b3991ecb652e5aee
OUT=/tmp/dl_io.tar.gz
rm -f "$OUT" /tmp/dl_io.log
echo "START $(date -u +%H:%M:%S)" > /tmp/dl_io.log
for attempt in 1 2 3 4 5; do
  echo "attempt $attempt $(date -u +%H:%M:%S)" >> /tmp/dl_io.log
  curl -sL -C - --max-time 240 --connect-timeout 20 -o "$OUT" "$URL" || true
  sz=$(stat -c %s "$OUT" 2>/dev/null || echo 0)
  echo "after attempt $attempt: size=$sz ($((sz/1024/1024)) MB)" >> /tmp/dl_io.log
  if [ "$sz" -gt 30000000 ]; then echo "COMPLETE size=$sz" >> /tmp/dl_io.log; break; fi
done
tail -8 /tmp/dl_io.log