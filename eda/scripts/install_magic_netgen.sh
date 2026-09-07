#!/usr/bin/env bash
# Install Magic (CI build 10010 tarball) + Netgen (pinned 1.5.265) into the
# running container. Magic installs via STAGING dir then copies into /usr/*
# (usrmerge-safe; NEVER extract ./bin ./lib tarballs directly to / — it
# replaces the /bin and /lib symlinks with real dirs and breaks libc paths).
set -u
MAGIC_URL="https://storage.googleapis.com/open_pdks/skywater-pdk/artifacts/prod/foss-fpga-tools/skywater-pdk/open_pdks/continuous/10010/20220523-011116/magic.tar.xz"
MAGIC_SHA_EXPECT="unset"   # recorded after first download in PROVISIONING_LOG
NETGEN_TAG="1.5.265"

echo "=== [1] fetch magic.tar.xz (2.5 MB)"
if [ ! -s /tmp/magic.tar.xz ]; then
  curl -fSL --retry 5 --retry-delay 3 --retry-all-errors -m 120 -o /tmp/magic.tar.xz "$MAGIC_URL" \
    && echo MAGIC_DL_OK || { echo MAGIC_DL_FAIL; exit 1; }
fi
stat -c 'magic.tar.xz size=%s (expect 2506760)' /tmp/magic.tar.xz
sha256sum /tmp/magic.tar.xz

echo "=== [2] magic staging install"
rm -rf /tmp/mstage && mkdir -p /tmp/mstage
tar -xJf /tmp/magic.tar.xz -C /tmp/mstage || { echo MAGIC_TAR_FAIL; exit 1; }
echo "staging top-level:"; ls /tmp/mstage
for d in bin lib share man; do
  if [ -d "/tmp/mstage/$d" ]; then
    mkdir -p "/usr/$d"
    cp -a "/tmp/mstage/$d/." "/usr/$d/"
    echo "copied ./$d -> /usr/$d ($(find /tmp/mstage/$d -type f | wc -l) files)"
  fi
done
echo "=== [3] magic verify"
command -v magic || { echo MAGIC_BIN_MISSING; }
ldd "$(command -v magic)" 2>&1 | grep -i 'not found' && echo MAGIC_LDL_MISSING || echo MAGIC_LDL_OK
timeout 25 magic -version 2>&1 | head -3
echo "banner probe:"
echo quit | timeout 25 magic -dnull -noconsole 2>&1 | head -6

echo "=== [4] netgen clone (small repo)"
rm -rf /tmp/netgen-src
if git clone --depth 1 --branch "$NETGEN_TAG" https://github.com/RTimothyEdwards/netgen /tmp/netgen-src 2>&1 | tail -2; then
  echo NETGEN_CLONE_OK
else
  echo "clone failed; codeload fallback"
  curl -fSL --retry 5 --retry-delay 3 --retry-all-errors -m 180 -o /tmp/netgen.tar.gz \
    "https://codeload.github.com/RTimothyEdwards/netgen/tar.gz/refs/tags/$NETGEN_TAG" \
    && mkdir -p /tmp/netgen-src && tar -xzf /tmp/netgen.tar.gz -C /tmp/netgen-src --strip-components=1 \
    && echo NETGEN_TARBALL_OK || { echo NETGEN_FETCH_FAIL; exit 1; }
fi
cd /tmp/netgen-src
git rev-parse HEAD 2>/dev/null || true
echo "=== [5] netgen build"
./configure --prefix=/usr/local > /tmp/netgen_conf.log 2>&1 && echo NG_CONF_OK || { echo NG_CONF_FAIL; tail -15 /tmp/netgen_conf.log; exit 1; }
make -j4 > /tmp/netgen_make.log 2>&1 && echo NG_MAKE_OK || { echo NG_MAKE_FAIL; tail -15 /tmp/netgen_make.log; exit 1; }
make install > /tmp/netgen_install.log 2>&1 && echo NG_INSTALL_OK || { echo NG_INSTALL_FAIL; tail -5 /tmp/netgen_install.log; exit 1; }
echo "=== [6] netgen verify"
command -v netgen
echo quit | timeout 25 netgen -noconsole 2>&1 | head -6
echo SCRIPT_ALL_DONE
