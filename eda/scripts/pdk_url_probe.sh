#!/usr/bin/env bash
# Probe candidate prebuilt-PDK (sky130A) tarball URLs — status codes only.
# Small requests; safe on a flaky link.
URLS=(
  "https://storage.googleapis.com/volare/sky130A/"
  "https://storage.googleapis.com/open_pdks/"
  "https://storage.googleapis.com/volare-public/sky130A/"
  "https://storage.googleapis.com/volare/versions/sky130/"
  "https://storage.googleapis.com/efabless-sky130A/"
)
for u in "${URLS[@]}"; do
  code=$(curl -sS -o /dev/null -m 15 -w "%{http_code}" "$u" 2>/dev/null)
  echo "HTTP ${code}  ${u}"
done
echo "---- bucket listing probe (volare) ----"
curl -sS -m 20 "https://storage.googleapis.com/volare?prefix=&max-keys=20" 2>/dev/null | head -c 2000
echo
echo "---- bucket listing probe (open_pdks) ----"
curl -sS -m 20 "https://storage.googleapis.com/open_pdks?prefix=&max-keys=20" 2>/dev/null | head -c 2000
echo
echo PROBE_DONE
