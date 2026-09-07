#!/usr/bin/env bash
# Parallel segmented resumable downloader (HTTP Range / GCS-friendly).
# Usage: pdk_fetch_parallel.sh URL OUT EXPECTED_SIZE [SEGS] [MAXTIME]
set -u
URL="$1"; OUT="$2"; EXP="$3"; SEGS="${4:-13}"; MT="${5:-90}"
DIR="$OUT.parts"; mkdir -p "$DIR"
SEG=$(( EXP / SEGS + 1 ))
seg_len() { local s=$1 start end; start=$(( s * SEG )); end=$(( start + SEG - 1 )); [ "$end" -ge "$EXP" ] && end=$(( EXP - 1 )); echo $(( end - start + 1 )); }
worker() {
  local s=$1 start end len part have from miss=0
  start=$(( s * SEG )); end=$(( start + SEG - 1 )); [ "$end" -ge "$EXP" ] && end=$(( EXP - 1 ))
  len=$(( end - start + 1 ))
  part=$(printf "%s/part%02d" "$DIR" "$s")
  while :; do
    have=$(stat -c %s "$part" 2>/dev/null || echo 0)
    if [ "$have" -ge "$len" ]; then echo "seg$s DONE $have/$len"; break; fi
    if [ "$have" -gt "$len" ]; then truncate -s "$len" "$part"; have=$len; fi
    from=$(( start + have ))
    curl -sfL --speed-limit 2048 --speed-time 20 --max-time "$MT" \
         -r "$from-$end" -o - "$URL" >> "$part" 2>/dev/null
    local now; now=$(stat -c %s "$part" 2>/dev/null || echo 0)
    echo "seg$s have=$now/$len $(date -u '+%T')"
    if [ "$now" -eq "$have" ]; then miss=$((miss+1)); else miss=0; fi
    if [ "$miss" -ge 40 ]; then echo "seg$s GIVEUP at $have/$len"; break; fi
    sleep 1
  done
}
for s in $(seq 0 $((SEGS-1))); do worker "$s" >> "$DIR/work.log" 2>&1 & done
# supervisor: wait until all parts complete (cap ~75 min)
it=0
while :; do
  alldone=1
  for s in $(seq 0 $((SEGS-1))); do
    len=$(seg_len "$s"); part=$(printf "%s/part%02d" "$DIR" "$s")
    have=$(stat -c %s "$part" 2>/dev/null || echo 0)
    [ "$have" -ge "$len" ] || alldone=0
  done
  [ "$alldone" -eq 1 ] && break
  it=$((it+1)); [ "$it" -ge 900 ] && { echo "SUPERVISOR_TIMEOUT"; exit 3; }
  sleep 5
done
# assemble + verify
: > "$OUT"
for s in $(seq 0 $((SEGS-1))); do
  len=$(seg_len "$s"); part=$(printf "%s/part%02d" "$DIR" "$s")
  truncate -s "$len" "$part"; cat "$part" >> "$OUT"
done
sz=$(stat -c %s "$OUT")
if [ "$sz" -eq "$EXP" ] && xz -t "$OUT" 2>/dev/null; then
  echo "PARALLEL_COMPLETE size=$sz"; rm -rf "$DIR"
else
  echo "ASSEMBLY_FAILED size=$sz — parts kept in $DIR"
  exit 1
fi
