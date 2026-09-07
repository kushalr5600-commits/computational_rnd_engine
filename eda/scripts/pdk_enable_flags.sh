#!/usr/bin/env bash
# Inspect open_pdks sky130 Makefile.in library enable/disable comments.
set -u
curl -s --max-time 30 "https://raw.githubusercontent.com/efabless/open_pdks/master/sky130/Makefile.in" -o /tmp/sky_mk.in
sed -n '20,125p' /tmp/sky_mk.in