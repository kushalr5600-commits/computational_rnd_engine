#!/bin/sh
echo NETGEN_KEYS:
grep -oE '<Key>[^<]*netgen[^<]*</Key>' /tmp/gcs.xml 2>/dev/null | head -3
echo KEYS_TOTAL:
grep -c '<Key>' /tmp/gcs.xml 2>/dev/null
echo KLAYOUT_INDEX_2911:
grep -oE 'klayout_0\.29\.11[^"<]*deb' /tmp/kl_idx.html 2>/dev/null | head -4
echo KLAYOUT_INDEX_ANY29:
grep -oE 'klayout_0\.29\.[0-9]+[^"<]*deb' /tmp/kl_idx.html 2>/dev/null | head -6
echo KLAYOUT_DE_2911:
grep -oE '[^" ]*0\.29\.11[^" ]*deb' /tmp/kl_build.html 2>/dev/null | head -6
echo READBACK_DONE
