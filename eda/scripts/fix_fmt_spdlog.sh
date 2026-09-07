#!/usr/bin/env bash
# Build fmt 7.1.3 + spdlog 1.9.2 into /usr/local for OpenROAD v2.0 compatibility.
# OpenROAD v2.0 (July 2021) needs fmt < 8 (enum formatting without explicit
# formatter specializations). Ubuntu 22.04 ships fmt 8.1 which breaks it.
set -u

cd /tmp
CURL="curl -fsSL --retry 5 --retry-delay 2 --connect-timeout 30"

echo "==> downloading fmt 7.1.3"
$CURL -o fmt.tar.gz https://codeload.github.com/fmtlib/fmt/tar.gz/7.1.3
tar xzf fmt.tar.gz
cd fmt-7.1.3
cmake -B build -DCMAKE_INSTALL_PREFIX=/usr/local -DFMT_TEST=OFF -DFMT_DOC=OFF > /tmp/fmt_cmake.log 2>&1
rc=$?
if [ $rc -ne 0 ]; then echo "FMT_CMAKE_FAILED"; tail -12 /tmp/fmt_cmake.log; exit 1; fi
cmake --build build -j4 >> /tmp/fmt_cmake.log 2>&1
rc=$?
if [ $rc -ne 0 ]; then echo "FMT_BUILD_FAILED"; tail -12 /tmp/fmt_cmake.log; exit 1; fi
cmake --install build >> /tmp/fmt_cmake.log 2>&1
rc=$?
if [ $rc -ne 0 ]; then echo "FMT_INSTALL_FAILED"; tail -12 /tmp/fmt_cmake.log; exit 1; fi

cd /tmp
echo "==> downloading spdlog 1.9.2"
$CURL -o spdlog.tar.gz https://codeload.github.com/gabime/spdlog/tar.gz/v1.9.2
tar xzf spdlog.tar.gz
cd spdlog-1.9.2
cmake -B build -DCMAKE_INSTALL_PREFIX=/usr/local -DSPDLOG_BUILD_SHARED=ON -DSPDLOG_FMT_EXTERNAL=ON -DSPDLOG_BUILD_EXAMPLE=OFF > /tmp/spdlog_cmake.log 2>&1
rc=$?
if [ $rc -ne 0 ]; then echo "SPDLOG_CMAKE_FAILED"; tail -12 /tmp/spdlog_cmake.log; exit 1; fi
cmake --build build -j4 >> /tmp/spdlog_cmake.log 2>&1
rc=$?
if [ $rc -ne 0 ]; then echo "SPDLOG_BUILD_FAILED"; tail -12 /tmp/spdlog_cmake.log; exit 1; fi
cmake --install build >> /tmp/spdlog_cmake.log 2>&1
rc=$?
if [ $rc -ne 0 ]; then echo "SPDLOG_INSTALL_FAILED"; tail -12 /tmp/spdlog_cmake.log; exit 1; fi

ldconfig

echo "==> verifying versions"
grep -m1 "FMT_VERSION" /usr/local/include/fmt/base.h 2>/dev/null || grep -m1 "FMT_VERSION" /usr/local/include/fmt/core.h
pkg-config --modversion fmt 2>/dev/null || true
pkg-config --modversion spdlog 2>/dev/null || true
echo "FMT_SPDLOG_DONE"