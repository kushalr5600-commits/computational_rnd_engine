#!/usr/bin/env bash
# Fetch open_pdks scripts listing + download-sources.sh content.
set -u
curl -s --max-time 30 "https://api.github.com/repos/efabless/open_pdks/contents/scripts" -o /tmp/op_scripts.json
python3 - <<'PY'
import json
for x in json.load(open("/tmp/op_scripts.json")):
    print(x["name"], x["size"])
PY

echo "=== download-sources.sh ==="
curl -s --max-time 30 "https://raw.githubusercontent.com/efabless/open_pdks/master/scripts/download-sources.sh" -o /tmp/dl.sh
wc -c /tmp/dl.sh
sed -n '1,120p' /tmp/dl.sh