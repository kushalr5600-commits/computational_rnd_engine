#!/usr/bin/env bash
# Probe #2: KLayout GitHub release assets + opencircuitdesign source tarballs.
OUT=/tmp/probe2_out.txt
{
echo "== KLayout releases (tags):"
curl -sS -m 40 "https://api.github.com/repos/KLayout/klayout/releases?per_page=30" -o /tmp/kl_rel.json
python3 - <<'PY'
import json
try:
    d = json.load(open('/tmp/kl_rel.json'))
    if isinstance(d, list):
        for r in d:
            tag = r.get('tag_name','')
            assets = [(a['name'], a['size']) for a in r.get('assets',[]) if a['name'].endswith('.deb')]
            print(tag, assets)
    else:
        print('unexpected:', str(d)[:300])
except Exception as e:
    print('parse fail:', e)
PY
echo
echo "== netgen tarball HEAD (opencircuitdesign):"
for u in http://opencircuitdesign.com/netgen/archive/netgen-1.5.265.tgz https://opencircuitdesign.com/netgen/archive/netgen-1.5.265.tgz; do
  echo "-- $u"
  curl -sSI -m 25 "$u" | head -6
done
echo
echo "== magic tarball HEAD (opencircuitdesign):"
curl -sSI -m 25 http://opencircuitdesign.com/magic/archive/magic-8.3.305.tgz | head -6
echo
echo "== netgen github tag probe (codeload, HEAD):"
curl -sSI -m 25 https://codeload.github.com/RTimothyEdwards/netgen/tar.gz/refs/tags/1.5.265 | head -4
echo PROBE2_RESULTS_DONE
} > $OUT 2>&1
