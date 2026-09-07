#!/usr/bin/env bash
set -u
apt-get update -qq > /tmp/apt_upd.log 2>&1 || { echo APT_UPDATE_FAIL; tail -3 /tmp/apt_upd.log; }
if DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
     qtbase5-dev qttools5-dev qttools5-dev-tools libqt5svg5-dev \
     ruby-dev ruby zlib1g-dev libbz2-dev tk8.6 tcl8.6 \
     libgl1 libglu1-mesa libglx-mesa0 libx11-dev libxext-dev \
     > /tmp/apt4.log 2>&1; then
  echo APT4_OK
else
  echo APT4_FAIL; tail -8 /tmp/apt4.log
fi
echo "=== magic banner retest"
timeout 20 bash -c 'echo "puts \"MAGIC_VER [magic::version]\"; quitall" | magic -dnull -noconsole' 2>&1 | tail -4
echo "=== klayout tarball progress"
ls -la /tmp/klayout-0.29.11.tar.gz 2>/dev/null || echo "not yet"
echo RETEST_DONE

echo "=== [A] magic forensics"
grep -n "TCL_MAG_DIR=" /usr/bin/magic | head -2
ls -la /usr/lib/magic/tcl/ 2>/dev/null | head -10
for f in /usr/lib/magic/tcl/magicdnull /usr/lib/magic/tcl/magic; do
  if [ -f "$f" ]; then
    sig=$(head -c 4 "$f" | od -An -tx1 | tr -d ' \n')
    echo "$f sig=$sig"
  fi
done
echo "=== [B] magic symlink fix"
mkdir -p /host/out/magic/lib/magic
ln -sfn /usr/lib/magic/tcl /host/out/magic/lib/magic/tcl
ln -sfn /usr/lib/magic/sys /host/out/magic/lib/magic/sys 2>/dev/null
grep -o '/host/out/magic/[a-z/]*' /usr/bin/magic | sort -u
echo "=== [C] magic banner"
timeout 20 bash -c 'echo "puts \"MAGIC_VER [magic::version]\"; quitall" | magic -dnull -noconsole' 2>&1 | tail -4
echo "=== [D] klayout codeload download (background)"
nohup bash -c 'curl -sL -m 900 --retry 5 --retry-all-errors -C - -o /tmp/klayout-0.29.11.tar.gz https://codeload.github.com/KLayout/klayout/tar.gz/refs/tags/v0.29.11 && echo KL_DL_OK >> /tmp/kldl.log || echo KL_DL_FAIL >> /tmp/kldl.log' > /dev/null 2>&1 &
echo "=== [E] apt deps for klayout build (foreground)"
if DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
     qtbase5-dev qttools5-dev qttools5-dev-tools libqt5svg5-dev libqt5xml5-dev \
     libqt5multimediawidgets5 libqt5designer5 \
     ruby-dev ruby zlib1g-dev libbz2-dev tk8.6 tcl8.6 libx11-dev libxext-dev \
     > /tmp/apt3.log 2>&1; then
  echo APT3_OK
else
  echo APT3_FAIL; tail -5 /tmp/apt3.log
fi
echo FIX_SCRIPT_DONE
