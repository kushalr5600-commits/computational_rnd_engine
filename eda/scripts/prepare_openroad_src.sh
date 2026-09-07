#!/usr/bin/env bash
# Prepare OpenROAD v2.0 source to build on Ubuntu 22.04 (system fmt 8).
# 1. Removes fmt 7.1.3 leftovers from a prior experiment path (avoid header
#    shadowing against the system fmt 8 / spdlog 1.9.2 pair).
# 2. Patches utl/Logger.h with a generic enum formatter so 2021-era code that
#    logs enum values compiles against fmt >= 8.
set -u

LOGGER=/tmp/The-OpenROAD-Project-OpenROAD-4feaf99/src/utl/include/utl/Logger.h

echo "==> cleaning fmt7 leftovers from /usr/local"
rm -rf /usr/local/include/fmt
rm -f /usr/local/lib/libfmt.so* /usr/local/lib/libfmt.a
rm -rf /usr/local/lib/cmake/fmt
rm -f /usr/local/lib/pkgconfig/fmt.pc

echo "==> patching Logger.h with generic enum formatter (fmt 8 compat)"
python3 - "$LOGGER" <<'PY'
import sys

path = sys.argv[1]
with open(path, "r", encoding="utf-8") as f:
    src = f.read()

anchor = '#include "spdlog/spdlog.h"\n#include "spdlog/fmt/ostr.h"\n'
assert anchor in src, "anchor not found in Logger.h"

marker = "// --- computational-rnd-engine: fmt8 enum formatter shim ---"
if marker in src:
    print("already patched, skipping")
    sys.exit(0)

insert = (
    anchor
    + marker
    + """
// OpenROAD v2.0 (2021) logs enum values as their underlying integer.
// fmt >= 8 requires explicit formatter<T> specializations for enums; this
// generic shim restores fmt-7 behaviour for every project enum.
#include <fmt/format.h>
FMT_BEGIN_NAMESPACE
template <typename T>
struct formatter<T, std::enable_if_t<std::is_enum<T>::value, char>> : formatter<int> {
  template <typename FormatContext>
  auto format(const T& value, FormatContext& ctx) const {
    return formatter<int>::format(static_cast<int>(value), ctx);
  }
};
FMT_END_NAMESPACE
"""
)

with open(path, "w", encoding="utf-8") as f:
    f.write(src.replace(anchor, insert, 1))
print("patched Logger.h")
PY

echo "==> verifying patch"
grep -n "fmt8 enum formatter shim" "$LOGGER"

echo "PREPARE_SRC_DONE"