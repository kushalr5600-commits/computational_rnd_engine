import sys
print("EXE:", sys.executable or "(embedded)")
print("VER:", sys.version.split()[0])
try:
    import pya
    print("PYA_OK", pya.Layout().dbu)
except Exception as e:
    print("PYA_FAIL:", e)
