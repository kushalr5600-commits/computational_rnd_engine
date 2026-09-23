#!/bin/bash
set -euo pipefail
cd /mnt/c/Users/user/Music/computational_rnd_engine
echo "=== BRANCH / HEAD ==="
git rev-parse --abbrev-ref HEAD
git log -1 --oneline || true
echo "=== Is git repo? ==="
git rev-parse --is-inside-work-tree
echo "=== gate_9d tracked file count ==="
git ls-files -- 'quantumvault/gate_9d_keygen/*' | wc -l
echo "=== gate_9d status (first 50) ==="
git status --porcelain=v1 -- 'quantumvault/gate_9d_keygen/' | head -50 || true
echo "=== Specific tested files ==="
files=(
  "quantumvault/gate_9d_keygen/rtl_candidate/mlkem_keygen_fips203.sv"
  "quantumvault/gate_9d_keygen/rtl_candidate/ntt_core_fips203.sv"
  "quantumvault/gate_9d_keygen/rtl_candidate/ntt_butterfly_gs.sv"
  "quantumvault/gate_9d_keygen/rtl_candidate/tb/mlkem_keygen_fips203_ms_tb.sv"
  "quantumvault/gate_9d_keygen/rtl_candidate/tb/mlkem_keygen_fips203_tb.sv"
  "quantumvault/gate_9d_keygen/tb/multiseed/multiseed_fips203_postbug15.log"
  "quantumvault/gate_9d_keygen/tb/multiseed/run_all_fips203_postbug15.py"
  "quantumvault/gate_9d_keygen/tb/multiseed/multiseed_results.log"
  "quantumvault/gate_9d_keygen/tb/golden/ek_fips203.hex"
  "quantumvault/gate_9d_keygen/tb/golden/dk_fips203.hex"
  "quantumvault/gate_9d_keygen/PROGRESS.md"
  "quantumvault/gate_9d_keygen/tb/multiseed/evidence/single_seed_vvp_transcript_postbug15.log"
)
for f in "${files[@]}"; do
  tracked=$(git ls-files -- "$f" || true)
  st=$(git status --porcelain=v1 -- "$f" || true)
  if [ -n "$tracked" ]; then t=YES; else t=NO; fi
  if [ -z "$st" ]; then s="(clean/absent-from-status)"; else s="$st"; fi
  echo "TRACKED=$t STATUS=$s FILE=$f"
done
echo "=== Overall repo status (summary counts) ==="
git status --porcelain=v1 | wc -l
echo "=== Overall status sample (first 30) ==="
git status --porcelain=v1 | head -30
