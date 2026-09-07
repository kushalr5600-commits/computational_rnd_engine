#!/usr/bin/env bash
set -u
curl -s --max-time 30 "https://raw.githubusercontent.com/efabless/open_pdks/master/sky130/Makefile.in" -o /tmp/sky_mk.in
wc -c /tmp/sky_mk.in
echo "=== download / tar.gz / git references ==="
grep -n -i -E "download|\.tar\.gz|tar\.gz|clone" /tmp/sky_mk.in | head -40