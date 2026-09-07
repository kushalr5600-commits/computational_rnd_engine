import sys
sys.path.insert(0, "/tmp")
sys.path.insert(0, "/work")
exec(open("/work/eda/scripts/sitecustomize.py").read())
from rnd_engine.config import _config_dir, load_config
print("CONFIG_DIR:", _config_dir())
cfg = load_config(profile="sky130")
print("LINT OPTIONS:", cfg["flows"]["lint"]["options"])
