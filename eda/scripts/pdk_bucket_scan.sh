#!/usr/bin/env bash
# Find the newest available prebuilt sky130A tarball in the open_pdks GCS bucket.
BASE="https://storage.googleapis.com/open_pdks?prefix=skywater-pdk/artifacts/prod/foss-fpga-tools/skywater-pdk/open_pdks/continuous"
for n in 10010 10009 10008 10007 10006 10005 10004 10003 10002 10001 10000; do
  echo "== build $n"
  curl -sS -m 25 "${BASE}/${n}/&max-keys=12" 2>/dev/null \
    | grep -oE '<Key>[^<]+</Key>|<Size>[0-9]+</Size>' \
    | sed 's/<Key>/KEY: /; s|</Key>||; s/<Size>/SIZE: /; s|</Size>||'
done
echo SCAN_DONE
