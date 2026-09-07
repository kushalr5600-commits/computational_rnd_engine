#!/bin/sh
curl -sS -m 90 'https://storage.googleapis.com/open_pdks?prefix=skywater-pdk/artifacts/prod/foss-fpga-tools/skywater-pdk/open_pdks/continuous/&max-keys=2000' -o /tmp/gcs.xml
curl -sS -m 30 'https://www.klayout.org/downloads/Ubuntu-22.04/' -o /tmp/kl_idx.html
curl -sS -m 30 'https://www.klayout.de/build.html' -o /tmp/kl_build.html
ls -la /tmp/gcs.xml /tmp/kl_idx.html /tmp/kl_build.html
echo FETCH_DONE
