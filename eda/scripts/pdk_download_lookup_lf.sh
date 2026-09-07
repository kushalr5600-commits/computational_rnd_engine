#!/usr/bin/env bash
set -u
echo "=== open_pdks scripts/download.sh ==="
curl -s --max-time 30 "https://raw.githubusercontent.com/efabless/open_pdks/master/scripts/download.sh" -o /tmp/dl.sh
cat /tmp/dl.sh