#!/bin/sh
echo ARTIFACT_HASHES:
sha256sum /tmp/magic.tar.xz /tmp/signoff/netgen-1.5.265.tgz /tmp/signoff/klayout/klayout.tar.gz 2>/dev/null
echo NETGEN_TAR_INFO:
tar -tzf /tmp/signoff/netgen-1.5.265.tgz 2>/dev/null | head -3
echo KLAYOUT_TAR_INFO:
tar -tzf /tmp/signoff/klayout/klayout.tar.gz 2>/dev/null | head -3
echo RND_ENGINE_CHECK:
command -v rnd-engine
rnd-engine --help 2>&1 | head -6
echo PDK_ROOT_HINT:
docker_env=$(grep -c . /proc/1/environ 2>/dev/null); echo proc_env_lines=$docker_env
echo HASH_DONE
