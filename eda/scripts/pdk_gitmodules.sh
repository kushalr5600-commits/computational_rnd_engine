#!/usr/bin/env bash
# Phase 3: review .gitmodules, then background submodule update.
set -u
cd /tmp/skywater-pdk

echo "== .gitmodules (name, url, path) =="
awk '/\[submodule/{name=$0} /path =/{p=$0; sub(".*path = ","",p)} /url =/{u=$0; sub(".*url = ","",u); print name " | path=" p " | url=" u}' .gitmodules | grep "/latest" | sed 's/\\[submodule "//; s/"\\]//'
echo
echo "== all registered submodules count =="
grep -c 'path = ' .gitmodules
echo
echo "== per-lib latest pin (gitls-tree) =="
for lib in sky130_fd_io sky130_fd_pr sky130_fd_sc_hd sky130_fd_sc_hdll sky130_fd_sc_hs sky130_fd_sc_hvl sky130_fd_sc_lp sky130_fd_sc_ls sky130_fd_sc_ms; do
  echo -n "$lib latest -> "
  git ls-tree HEAD "libraries/$lib/latest"
done