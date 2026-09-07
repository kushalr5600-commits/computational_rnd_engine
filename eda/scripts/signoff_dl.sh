#!/bin/sh
set -u
G=/tmp/signoff
mkdir -p $G
curl -sSL -m 120 -o $G/magic.tar.xz 'https://storage.googleapis.com/open_pdks/skywater-pdk/artifacts/prod/foss-fpga-tools/skywater-pdk/open_pdks/continuous/10010/20220523-011116/magic.tar.xz'
curl -sSL -m 120 -o $G/netgen-1.5.265.tgz 'https://opencircuitdesign.com/netgen/archive/netgen-1.5.265.tgz'
ls -la $G
echo '=== sha256:'
sha256sum $G/magic.tar.xz $G/netgen-1.5.265.tgz 2>/dev/null
echo '=== magic tarball root:'
tar -tJf $G/magic.tar.xz | head -6
echo '=== netgen tarball root:'
tar -tzf $G/netgen-1.5.265.tgz | head -6
echo DL_DONE
