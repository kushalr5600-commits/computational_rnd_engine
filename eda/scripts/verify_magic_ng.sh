#!/usr/bin/env bash
# Verify magic + netgen executables with real version banners
set -u
echo "=== magic banner"
timeout 25 bash -c 'echo "puts \"MAGIC_VER_[magic::version]\"; quitall" | magic -dnull -noconsole' 2>&1 | tail -5
echo "=== magic -version style check"
timeout 25 magic -dnull -noconsole <<'EOF' 2>&1 | tail -3
puts "MAGIC_VERSION_[magic::version]"
quitall
EOF
echo "=== netgen banner"
echo 'quit' | timeout 15 netgen -noconsole 2>&1 | grep -i netgen | head -2
echo "=== binaries"
ls -la /usr/bin/magic /usr/local/bin/netgen
which klayout 2>/dev/null || echo "klayout: not yet (awaiting source tarball)"
echo VERIFY_DONE
