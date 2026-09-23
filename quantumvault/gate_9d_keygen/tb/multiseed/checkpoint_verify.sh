#!/bin/bash
set -euo pipefail
BASE=/mnt/c/Users/user/Music/computational_rnd_engine/quantumvault/gate_9d_keygen
QV=/mnt/c/Users/user/Music/computational_rnd_engine/quantumvault
NEWLOG="$BASE/tb/multiseed/multiseed_fips203_postbug15.log"
XSCRIPT="$BASE/tb/multiseed/evidence/single_seed_vvp_transcript_postbug15.log"
OLDLOG="$BASE/tb/multiseed/multiseed_results.log"

echo "=== 1. EXISTENCE ==="
for f in "$NEWLOG" "$XSCRIPT" "$OLDLOG"; do
  if [ -f "$f" ]; then echo "EXISTS $f"; else echo "MISSING $f"; fi
done

echo "=== 2. MD5 CURRENT FILES ==="
md5sum \
  "$NEWLOG" \
  "$XSCRIPT" \
  "$OLDLOG" \
  "$BASE/tb/golden/ek_fips203.hex" \
  "$BASE/tb/golden/dk_fips203.hex" \
  "$BASE/rtl_candidate/mlkem_keygen_fips203.sv" \
  "$BASE/rtl_candidate/ntt_core_fips203.sv" \
  "$BASE/rtl_candidate/ntt_butterfly_gs.sv" \
  "$BASE/rtl_candidate/tb/mlkem_keygen_fips203_ms_tb.sv" \
  "$BASE/rtl_candidate/tb/mlkem_keygen_fips203_tb.sv" \
  "$QV/rtl/ntt_butterfly.sv" \
  "$QV/rtl/shake_sha3.sv" \
  "$QV/rtl/keccak_f.sv" \
  "$QV/gate_9c_vector_arithmetic/rtl/basemultiply.sv" \
  "$QV/gate_9c_vector_arithmetic/rtl/mod_q_mul.sv" \
  "$BASE/rtl/ntt_sample.sv" \
  "$BASE/rtl/cbd_sampler.sv" \
  "$BASE/rtl/key_encode.sv"

echo "=== 3. LOG HEADER (recorded hashes) ==="
sed -n '1,30p' "$NEWLOG"

echo "=== 4. LOG SUMMARY ==="
tail -12 "$NEWLOG"

echo "=== 5. TRANSCRIPT ==="
cat "$XSCRIPT"

echo "=== 6. GOLDEN LINE COUNTS ==="
wc -l "$BASE/tb/golden/ek_fips203.hex" "$BASE/tb/golden/dk_fips203.hex"
