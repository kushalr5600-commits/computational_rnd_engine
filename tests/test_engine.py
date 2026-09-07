from rnd_engine.engine import InventionEngine
from rnd_engine.models import Domain


def test_small_run(tmp_path,monkeypatch):
    monkeypatch.chdir(tmp_path); r=InventionEngine(population=8,generations=2,seed=7,domain=Domain.CPU).run(); assert len(r['history'])==2
