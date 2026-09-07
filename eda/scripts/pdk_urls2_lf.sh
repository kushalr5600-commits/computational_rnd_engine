#!/usr/bin/env bash
set -u
echo "=== sky130 custom scripts dir ==="
curl -s --max-time 30 "https://api.github.com/repos/efabless/open_pdks/contents/sky130/custom/scripts" -o /tmp/custom.json
python3 - <<'PY'
import json
try:
    d = json.load(open("/tmp/custom.json"))
    if isinstance(d, list):
        for x in d:
            print(x["name"], x["size"])
    else:
        print("not a list:", str(d)[:200])
except Exception as e:
    print("failed:", e)
PY

echo "=== pdk_download.sh ==="
curl -s --max-time 30 "https://raw.githubusercontent.com/efabless/open_pdks/master/sky130/custom/scripts/pdk_download.sh" -o /tmp/pdk_dl.sh
wc -c /tmp/pdk_dl.sh
cat /tmp/pdk_dl.sh

echo "=== URL defaults in configure ==="
curl -s --max-time 30 "https://raw.githubusercontent.com/efabless/open_pdks/master/configure" -o /tmp/op_configure
grep -n -i -E "_URL=" /tmp/op_configure | head -30