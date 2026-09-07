#!/usr/bin/env bash
# Phase 2: attempt shallow clone of skywater-pdk main repo (depth 1, single branch).
set -u
echo "== disk space =="
df -h / /tmp | tail -3

echo "== start: shallow clone skywater-pdk main =="
cd /tmp
rm -rf skywater-pdk skywater-pdk.tar.gz
timeout 900 git clone --depth 1 --single-branch --branch main \
  https://github.com/google/skywater-pdk.git /tmp/skywater-pdk > /tmp/clone_main.log 2>&1
RC=$?
echo "clone exit code: $RC"
tail -5 /tmp/clone_main.log
if [ $RC -ne 0 ]; then
  echo "MAIN_CLONE_FAILED rc=$RC"
  exit 1
fi
du -sh /tmp/skywater-pdk
ls /tmp/skywater-pdk | head -20
echo "== submodule gitlink SHAs recorded =="
cd /tmp/skywater-pdk
git ls-tree HEAD libraries/ | sed -n '1,30p'
echo "MAIN_CLONE_OK"