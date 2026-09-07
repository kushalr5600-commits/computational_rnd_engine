from rnd_engine.models import Metrics
from rnd_engine.objective import OmegaObjective


def m(**kw):
    d = {"baseline_cost": 100, "optimized_cost": 50, "correctness_error": 0, "generalization": 0.9,
         "utility": 0.9, "novelty": 0.8, "reusability": 0.99, "hardware_efficiency": 0.9,
         "useful_structure": 0.8, "search_cost": 0.1, "memory_cost": 0.1, "complexity_cost": 0.2,
         "energy_cost": 0.2, "fragility": 0.05, "future_discovery_rate": 0.8,
         "search_efficiency": 0.9, "reproducibility": 0.99}
    d.update(kw); return Metrics(**d)

def test_real_speedup_is_baseline_relative(): assert OmegaObjective().evaluate(m()).amplification==2

def test_incorrect_is_rejected():
    s=OmegaObjective().evaluate(m(correctness_error=.1)); assert not s.verified and s.omega==0

def test_faster_is_better():
    a=OmegaObjective().evaluate(m(optimized_cost=80)); b=OmegaObjective().evaluate(m(optimized_cost=40)); assert b.omega>a.omega
