#!/usr/bin/env bash
# Run `rnd-engine eda-doctor` inside the signoff container (repo mounted at /work).
# Deps are installed into the throwaway container only — never into the image.
set -u
export PDK_ROOT=/usr/local/share/pdk
export OPENSTA_BIN=/usr/local/bin/sta
export PYTHONPATH=/work
export PYTHONUNBUFFERED=1
echo "== deps"
pip3 install -q pydantic pyyaml >/tmp/pip.log 2>&1 \
  || { echo PIP_FAIL; tail -3 /tmp/pip.log; exit 3; }
echo "== doctor"
python3 -u - <<'PY'
import datetime, sys
# Interpreter-level 3.11 compat shim for the Ubuntu-22.04 python3.10 in the
# container: datetime.UTC is an alias, nothing else. Engine code untouched.
datetime.UTC = datetime.timezone.utc
sys.argv = ['rnd-engine', 'eda-doctor']
from rnd_engine.cli import main
main()
PY
echo "DOCTOR_RC=$?"

