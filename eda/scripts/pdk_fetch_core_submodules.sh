#!/usr/bin/env bash
# Fetch core sky130 'latest' submodules (sc_hd, io, pr) at pinned SHAs, depth 1.
cd /tmp/skywater-pdk || exit 9
{
  echo "START $(date -u +%H:%M:%S)"
  git submodule update --init --depth 1 \
    libraries/sky130_fd_sc_hd/latest \
    libraries/sky130_fd_io/latest \
    libraries/sky130_fd_pr/latest
  echo "SUBMODULE_RC=$?"
  du -sh libraries/sky130_fd_sc_hd/latest libraries/sky130_fd_io/latest libraries/sky130_fd_pr/latest
  echo "END $(date -u +%H:%M:%S)"
} > /tmp/sub.log 2>&1