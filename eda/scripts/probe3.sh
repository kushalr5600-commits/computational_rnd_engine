#!/bin/sh
echo '=== any deb links on build page (any version):'
grep -oE 'https?://[^" ]*\.deb' /tmp/kl_build.html | head -8
echo '=== hrefs mentioning 0.29:'
grep -oE '"[^"]*0\.29[^"]*"' /tmp/kl_build.html | head -8
echo '=== netgen source tarball probe:'
curl -sSI -m 25 http://opencircuitdesign.com/netgen/archive/netgen-1.5.265.tgz | head -6
echo '=== klayout github release tarball probe:'
curl -sSIL -m 30 https://github.com/KLayout/klayout/archive/refs/tags/v0.29.11.tar.gz | grep -E 'HTTP/|location:' | head -6
echo PROBE3_DONE
