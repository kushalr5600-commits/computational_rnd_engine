#!/usr/bin/env bash
# Sky130A PDK provisioning - phase 1: discover source URLs + network probe.
set -u

echo "== 1. skywater-pdk releases (looking for PDK tarball assets) =="
curl -sf --max-time 30 "https://api.github.com/repos/google/skywater-pdk/releases?per_page=10" -o /tmp/sky_releases.json
python3 - <<'PY'
import json
data = json.load(open("/tmp/sky_releases.json"))
if not isinstance(data, list):
    print("unexpected:", str(data)[:200]); raise SystemExit(1)
for r in data:
    print("tag:", r.get("tag_name"), "| name:", r.get("name"))
    for a in r.get("assets", []):
        print("    asset:", a["name"], "size:", a["size"], "url:", a["browser_download_url"])
PY

echo
echo "== 2. open_pdks latest release/tag =="
curl -sf --max-time 30 "https://api.github.com/repos/RTimothyEdwards/open_pdks/releases/latest" -o /tmp/openpdks_rel.json
python3 - <<'PY'
import json
try:
    data = json.load(open("/tmp/openpdks_rel.json"))
except Exception as e:
    print("no release:", e); raise SystemExit(0)
print("tag:", data.get("tag_name"), "| name:", data.get("name"))
for a in data.get("assets", []):
    print("    asset:", a["name"], "size:", a["size"], "url:", a["browser_download_url"])
PY

echo
echo "== 3. network stability probe: 20MB from a known-good mirror =="
curl -sf --max-time 120 --retry 3 --retry-delay 2 \
   -o /tmp/netprobe.bin \
   -w "downloaded %{size_download} bytes in %{time_total}s at %{speed_download} B/s\n" \
   https://proof.ovh.net/files/20Mb.dat || echo "NET PROBE FAILED rc=$?"
rm -f /tmp/netprobe.bin

echo "NETWORK_PHASE1_DONE"