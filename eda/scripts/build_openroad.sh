#!/usr/bin/env bash
# Build OpenROAD from source inside container.
set -u

SRC=/tmp/The-OpenROAD-Project-OpenROAD-4feaf99
BUILD=$SRC/build

cd "$SRC" || exit 3
mkdir -p "$BUILD"
cd "$BUILD" || exit 4

echo "==> cmake configure"
rm -rf ./*
cmake .. -DCMAKE_INSTALL_PREFIX=/opt/openroad -DCUDD_DIR=/usr/local > /tmp/cmake2.log 2>&1
CMAKE_RC=$?
tail -12 /tmp/cmake2.log
echo "cmake exit code: $CMAKE_RC"
if [ "$CMAKE_RC" -ne 0 ]; then
  echo "BUILD_FAILED_AT_CMAKE"
  exit 1
fi

echo "==> make -j4"
make -j4 > /tmp/make.log 2>&1
MAKE_RC=$?
echo "make exit code: $MAKE_RC"
if [ "$MAKE_RC" -ne 0 ]; then
  echo "build errors:"
  grep -iE "\b(error|Error)\b" /tmp/make.log | tail -20
  echo "BUILD_FAILED_AT_MAKE"
  exit 1
fi
tail -8 /tmp/make.log

echo "==> make install"
make install > /tmp/install.log 2>&1
INSTALL_RC=$?
echo "install exit code: $INSTALL_RC"
if [ "$INSTALL_RC" -ne 0 ]; then
  echo "BUILD_FAILED_AT_INSTALL"
  exit 1
fi
tail -5 /tmp/install.log

echo "==> verify binary"
ls -la /opt/openroad/bin/ 2>/dev/null || true
which openroad 2>/dev/null || true
/opt/openroad/bin/openroad -version 2>&1 | head -5 || true
echo "OPENROAD_BUILD_DONE"