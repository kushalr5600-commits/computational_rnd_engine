#!/usr/bin/env bash
set -u
echo "=== configure.ac URL defaults ==="
curl -s --max-time 30 "https://raw.githubusercontent.com/efabless/open_pdks/master/configure.ac" -o /tmp/op_configure.ac
grep -n -i -E "PDK_URL|ALPHA_URL|SRAM_URL|XSCHEM_URL|KLAYOUT_URL|OSU_.*URL" /tmp/op_configure.ac | head -30

echo
echo "=== custom/scripts/pdk_download.sh ==="
curl -s --max-time 30 "https://api.github.com/repos/efabless/open_pdks/contents/custom/scripts" -o /tmp/custom.json
python3 - <<'PY'
import json
try:
    for x in json.load(open("/tmp/custom.json")):
        print(x["name"], x["size"])
except Exception as e:
    print("list failed:", e)
PY
curl -s --max-time 30 "https://raw.githubusercontent.com/efabless/open_pdks/master/custom/scripts/pdk_download.sh" -o /tmp/pdk_dl.sh
wc -c /tmp/pdk_dl.sh
cat /tmp/pdk_dl.sh | head -80