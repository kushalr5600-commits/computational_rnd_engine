#!/usr/bin/env bash
# Re-query GitHub API with raw responses + rate-limit check.
set -u
echo "== rate limit status =="
cat /tmp/t1.json 2>/dev/null

echo
echo "== skywater-pdk latest release (raw head) =="
curl -s --max-time 30 -w "\n[http_code=%{http_code}]\n" \
  "https://api.github.com/repos/google/skywater-pdk/releases?per_page=5" -o /tmp/sky2.json
head -c 1200 /tmp/sky2.json
echo
echo "== open_pdks tags =="
curl -s --max-time 30 -w "\n[http_code=%{http_code}]\n" \
  "https://api.github.com/repos/RTimothyEdwards/open_pdks/tags?per_page=5" -o /tmp/op2.json
head -c 1200 /tmp/op2.json
echo
echo "QUERY_DONE"