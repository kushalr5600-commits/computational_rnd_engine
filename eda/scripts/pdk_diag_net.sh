#!/usr/bin/env bash
# Network diagnosis from inside the container.
set -u
echo "== env proxy vars =="
env | grep -i -E "proxy|http" || echo "none"
echo
echo "== DNS test github.com =="
getent hosts github.com || echo "DNS FAIL"
echo
echo "== curl github api verbose (10s cap) =="
curl -v --max-time 10 "https://api.github.com/rate_limit" -o /tmp/t1.json 2>&1 | head -25
echo "curl_exit=$?"
echo
echo "== bytes received? =="
ls -la /tmp/t1.json 2>/dev/null || echo "no file"
echo
echo "== google =="
curl -sSI --max-time 10 https://www.google.com 2>&1 | head -5
echo "google_curl_exit=$?"
echo
echo "== debian mirror =="
curl -sSI --max-time 10 http://deb.debian.org/debian/ 2>&1 | head -5
echo "debian_curl_exit=$?"
echo "DIAG_DONE"