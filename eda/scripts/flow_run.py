"""Introspective driver: regenerate candidate RTL in-container, parse-check with
Verilator + Yosys, and attempt the real flow stages. Self-diagnosing output."""
import inspect, sys, traceback, warnings

warnings.filterwarnings('ignore')
sys.path.insert(0, '/work')

import rnd_engine.rtl.generator as G
print('RTL MODULE:', G.__file__)
print('RTL API:', [n for n in dir(G) if not n.startswith('_')])

from rnd_engine import flow as F
from rnd_engine.engine import InventionEngine
print('RUN_FLOW SIG:', inspect.signature(F.run_flow))

eng = InventionEngine(seed=42)
res = eng.run(population=4, generations=1)
best = getattr(res, 'best', None) or (res.get('best') if isinstance(res, dict) else None)
print('BEST:', best)

# find a generator entry point
gen = None
for name in ('RTLGenerator', 'RtlGenerator', 'Generator'):
    if hasattr(G, name):
        gen = getattr(G, name)()
        print('USING GENERATOR CLASS:', name)
        break
if gen is None:
    sys.exit('NO GENERATOR CLASS FOUND')

design = getattr(best, 'design', best)
try:
    art = gen.generate(design)
except TypeError:
    art = gen.generate(design, out_dir='/tmp/cand')
print('GENERATE RESULT TYPE:', type(art))
print('GENERATE RESULT:', art if isinstance(art, (str, list)) else dir(art))

import subprocess, glob, os
sv = art if isinstance(art, list) else (
    sorted(glob.glob(os.path.join(art, '*.sv'))) if isinstance(art, str) and os.path.isdir(art) else [art])
print('SV FILES:', sv)

for f in sv:
    for tool, cmd in (('verilator', f'verilator --lint-only -Wno-fatal {f}'),
                      ('yosys', f'yosys -q -p "read_verilog -sv {f}"')):
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=120)
        print(f'=== {tool} on {os.path.basename(f)}: rc={r.returncode}')
        if r.returncode != 0:
            print((r.stderr or r.stdout)[-600:])

try:
    rc = F.run_flow(design, stages=('lint', 'synthesis'), out_dir='/work/artifacts/cand_run')
    print('FLOW OK:', rc)
except TypeError as e:
    print('FLOW SIG MISMATCH:', e)
    print(inspect.getsource(F.run_flow)[:1200])
except Exception:
    traceback.print_exc()
