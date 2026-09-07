import sys
try:
    import pya  # embedded binding
    where = "pya"
except ImportError:
    try:
        import klayout.db as pya  # 0.29 package API
        where = "klayout.db"
    except ImportError as e:
        print("IMPORT_FAIL", e)
        sys.exit(1)
ly = pya.Layout()
ly.dbu = 0.001
top = ly.create_cell("TOP")
top.shapes(ly.layer(1, 0)).insert(pya.Box(0, 0, 10000, 5000))
ly.write("/tmp/kl_pkg.gds")
ly2 = pya.Layout()
ly2.read("/tmp/kl_pkg.gds")
print("BINDING:", where)
print("PY_ROUNDTRIP_OK cells=", ly2.cells(), "TOP?=", ly2.has_cell("TOP"))
