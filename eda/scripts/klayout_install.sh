#!/usr/bin/env bash
# Install KLayout 0.29.11 (modular Qt build) system-wide + functional GDS test
set -u
SRC=/tmp/klayout-0.29.11/build-release
DST=/usr/local/lib/klayout029
mkdir -p "$DST"
cp -a "$SRC"/klayout "$SRC"/strm2gds "$SRC"/gds2strm "$DST"/ 2>/dev/null
cp -a "$SRC"/libklayout_*.so* "$DST"/
for d in db_plugins lay_plugins; do
  [ -d "$SRC/$d" ] && cp -a "$SRC/$d" "$DST"/
done
echo "/usr/local/lib/klayout029" > /etc/ld.so.conf.d/klayout029.conf
ldconfig
ln -sf "$DST/klayout" /usr/local/bin/klayout
ln -sf "$DST/strm2gds" /usr/local/bin/strm2gds
ln -sf "$DST/gds2strm" /usr/local/bin/gds2strm 2>/dev/null
echo "== version:"; klayout -v
echo "== strm2gds:"; strm2gds -h 2>&1 | head -2
cat > /tmp/gds_test.py <<'PY'
import pya, sys
ly = pya.Layout()
ly.dbu = 0.001
top = ly.create_cell("TOP")
l1 = ly.layer(1, 0)
top.shapes(l1).insert(pya.Box(0, 0, 10000, 5000))
ly.write("/tmp/kl_test.gds")
print("WROTE_GDS")
ly2 = pya.Layout()
ly2.read("/tmp/kl_test.gds")
print("READBACK_CELLS", ly2.cells(), "TOP?", ly2.has_cell("TOP"))
PY
echo "== functional GDS round-trip:"
klayout -zz -r /tmp/gds_test.py 2>&1 | tail -4
ls -la /tmp/kl_test.gds
echo KLAYOUT_INSTALL_DONE
