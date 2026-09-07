#!/usr/bin/env bash
# Fetch OpenSTA source matching OpenROAD v2.0 (July 2021) and install into src/sta.
set -uo pipefail

API="https://api.github.com/repos/The-OpenROAD-Project/OpenSTA"
CURL=(curl -sf --retry 5 --retry-delay 2 --connect-timeout 30)

echo "==> Fetching OpenSTA commits up to 2021-07-16"
"${CURL[@]}" "$API/commits?until=2021-07-16T00:00:00Z&per_page=5" -o /tmp/sta_commits.json

python3 - <<'PY'
import json
data = json.load(open("/tmp/sta_commits.json"))
if not isinstance(data, list):
    print("Unexpected API response:", str(data)[:200])
    raise SystemExit(1)
c = data[0]
sha = c["sha"]
when = c["commit"]["committer"]["date"]
msg = c["commit"]["message"].splitlines()[0][:70]
print("Selected OpenSTA commit:", sha, when, msg)
with open("/tmp/sta_sha.txt", "w") as f:
    f.write(sha)
PY

SHA=$(cat /tmp/sta_sha.txt)
echo "==> Downloading OpenSTA tarball $SHA"
"${CURL[@]}" "https://codeload.github.com/The-OpenROAD-Project/OpenSTA/tar.gz/${SHA}" -o /tmp/opensta.tar.gz
ls -la /tmp/opensta.tar.gz

echo "==> Extracting OpenSTA"
rm -rf /tmp/opensta-src
mkdir -p /tmp/opensta-src
tar xzf /tmp/opensta.tar.gz -C /tmp/opensta-src --strip-components=1

echo "==> Checking required SWIG interface files"
ls -la /tmp/opensta-src/tcl/StaTcl.i /tmp/opensta-src/tcl/NetworkEdit.i

echo "==> Replacing src/sta with matching OpenSTA"
rm -rf /tmp/The-OpenROAD-Project-OpenROAD-4feaf99/src/sta
cp -a /tmp/opensta-src /tmp/The-OpenROAD-Project-OpenROAD-4feaf99/src/sta
echo "Done. src/sta replaced."