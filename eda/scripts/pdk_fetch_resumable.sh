#!/usr/bin/env bash
# Generic resumable single-file downloader for a flaky link (GCS supports Range).
# Usage: pdk_fetch_resumable.sh URL OUT EXPECTED_SIZE [ATTEMPTS] [MAXTIME_PER_ATTEMPT]
URL="$1"; OUT="$2"; EXP="$3"; N="${4:-80}"; MT="${5:-150}"
stalled=0
echo "START $(date -u '+%F %T') url=$URL out=$OUT expected=$EXP attempts=$N"
for i in $(seq 1 "$N"); do
  sz=$(stat -c %s "$OUT" 2>/dev/null || echo 0)
  if [ "$sz" -ge "$EXP" ]; then echo "COMPLETE size=$sz"; exit 0; fi
  curl -sfL -C - --max-time "$MT" --connect-timeout 20 -o "$OUT" "$URL"
  rc=$?
  sz2=$(stat -c %s "$OUT" 2>/dev/null || echo 0)
  echo "attempt $i rc=$rc size=$sz2 delta=$((sz2-sz)) $(date -u '+%T')"
  if [ "$sz2" -ge "$EXP" ]; then echo "COMPLETE size=$sz2"; exit 0; fi
  if [ "$sz2" -eq "$sz" ]; then stalled=$((stalled+1)); else stalled=0; fi
  if [ "$stalled" -ge 6 ]; then echo "ABORT_STALLED size=$sz2 after 6 zero-delta attempts"; exit 2; fi
  sleep 2
done
echo "EXHAUSTED_AT size=$sz2"
