# sky130A PDK — download list (UPDATED)
#
# ============ OPTION A (PREFERRED): ONE prebuilt PDK file ============
# Prebuilt, OpenROAD-ready sky130A (open_pdks install tree, from skywater CI).
# Drop into:  C:\Users\user\Music\computational_rnd_engine\eda\pdk_downloads\
# Name it:    pdk-SKY130A.tar.xz
#
# URL:
#   https://storage.googleapis.com/open_pdks/skywater-pdk/artifacts/prod/foss-fpga-tools/skywater-pdk/open_pdks/continuous/10010/20220523-011116/pdk-SKY130A.tar.xz
#
# Exact size: 100,640,940 bytes (96 MB)  — verify after download!
# Browser download auto-resumes on flaky links (plain static file on GCS).
# Optional bonus (built Magic binary, 2.5 MB):
#   ...same folder.../magic.tar.xz
#
# ============ OPTION B (FALLBACK): per-library source tarballs ============
# Only needed if Option A proves unusable. Build open_pdks from source afterwards.
#
# Drop the .tar.gz files into:
#   C:\Users\user\Music\computational_rnd_engine\eda\pdk_downloads\
# using this exact naming:  <lib>-latest.tar.gz
#
# Download URL pattern (GitHub codeload, pinned SHA):
#   https://codeload.github.com/google/<repo>/tar.gz/<sha>
#
# CORE (needed for the engine's PDK required paths) — recommended:
#   sky130_fd_sc_hd   (~212 MB)  https://codeload.github.com/google/skywater-pdk-libs-sky130_fd_sc_hd/tar.gz/ac7fb61f06e6470b94e8afdf7c25268f62fbd7b1
#   sky130_fd_io      (~35 MB)   https://codeload.github.com/google/skywater-pdk-libs-sky130_fd_io/tar.gz/01b18699b4102d8e54ad1406b3991ecb652e5aee
#   sky130_fd_pr      (~111 MB)  https://codeload.github.com/google/skywater-pdk-libs-sky130_fd_pr/tar.gz/f62031a1be9aefe902d6d54cddd6f59b57627436
#
# OPTIONAL (extra standard-cell flavors; skip unless you want full PDK):
#   sky130_fd_sc_hdll (~218 MB)  https://codeload.github.com/google/skywater-pdk-libs-sky130_fd_sc_hdll/tar.gz/0694bd23893de20f5233ef024acf6cca1e750ac6
#   sky130_fd_sc_hvl  (~74 MB)   https://codeload.github.com/google/skywater-pdk-libs-sky130_fd_sc_hvl/tar.gz/4fd4f858d16c558a6a488b200649e909bb4dd800
#   sky130_fd_sc_hs   (~1171 MB) https://codeload.github.com/google/skywater-pdk-libs-sky130_fd_sc_hs/tar.gz/1d051f49bfe4e2fe9108d702a8bc2e9c081005a4
#   sky130_fd_sc_lp   (~953 MB)  https://codeload.github.com/google/skywater-pdk-libs-sky130_fd_sc_lp/tar.gz/e2c1e0646999163d35ea7b2521c3ec5c28633e63
#   sky130_fd_sc_ls   (~1219 MB) https://codeload.github.com/google/skywater-pdk-libs-sky130_fd_sc_ls/tar.gz/4f549e30dd91a1c264f8895e07b2872fe410a8c2
#   sky130_fd_sc_ms   (~943 MB)  https://codeload.github.com/google/skywater-pdk-libs-sky130_fd_sc_ms/tar.gz/ae1b7f68821505cf2d93d9d44cce5ece22710fad
#
# NOT needed for sky130A (ReRAM variant):
#   sky130_fd_pr_reram (~3.6 MB)
#
# NOTE: codeload does NOT support HTTP Range/resume (verified 2026-09-05:
# 35 MB io tarball stalled at 13.9 MB; retries added zero bytes). If you
# download Option B files, prefer a browser (it restarts cleanly) over curl -C -.

#