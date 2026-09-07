from __future__ import annotations

from rnd_engine.equation24 import (
    Equation24Config,
    compute_A,
    compute_V,
    evaluate,
)
from rnd_engine.models import Metrics


def _mk(**kw):
    defaults = {
        "baseline_cost": 100, "optimized_cost": 50, "correctness_error": 0,
        "generalization": 0.8, "utility": 0.6, "novelty": 0.5, "reusability": 0.95,
        "hardware_efficiency": 0.7, "useful_structure": 0.4, "search_cost": 0.01,
        "memory_cost": 1.0, "complexity_cost": 0.5, "energy_cost": 2.0, "fragility": 0.1,
        "future_discovery_rate": 0.3, "reproducibility": 0.98, "search_efficiency": 0.3, "evidence": {},
    }
    defaults.update(kw)
    return Metrics(**defaults)

def test_exact_equation_structure():
    """Equation 24 must have: base_product * (1+kappa*I) * (1+eta*D) * (1+xi*L) / denominator."""
    m = _mk()
    r = evaluate(m)
    assert "omega" in r
    assert "numerator" in r and "denominator" in r
    assert "bonus_I" in r and "bonus_D" in r and "bonus_L" in r
    # Verify structure: numerator = base * bonus_I * bonus_D * bonus_L
    base = r["A"] * r["V"] * r["G"] * r["U"] * r["N"] * r["R"] * r["H"]
    expected_num = base * r["bonus_I"] * r["bonus_D"] * r["bonus_L"]
    assert abs(r["numerator"] - expected_num) < 1e-9

def test_multiplicative_V():
    """V must be multiplicative in the numerator, not a hard gate."""
    m1 = _mk(evidence={})
    m2 = _mk(evidence={"fidelity": "SIGNOFF"})
    r1 = evaluate(m1)
    r2 = evaluate(m2)
    # Higher fidelity evidence should increase V and thus omega
    assert r2["V"] > r1["V"]
    assert r2["omega"] > r1["omega"]

def test_hard_feasibility_gate():
    """Constraints must be hard gates: violation -> omega=0."""
    infeasible = _mk(generalization=0.1)  # below min_generalization=0.70
    r = evaluate(infeasible)
    assert r["feasible"] is False
    assert r["omega"] == 0.0

def test_all_terms_present():
    r = evaluate(_mk())
    expected_keys = {"A","V","G","U","N","R","H","I","D","L","C_search","E","M","D_complexity","Energy","Fragility"}
    assert expected_keys.issubset(r.keys())

def test_D_literal_computation():
    """D(S) = best_verified_improvement / search_cost."""
    m = _mk(search_cost=2.0, evidence={"best_verified_improvement": 0.5})
    r = evaluate(m)
    assert abs(r["D"] - 0.25) < 1e-9

def test_L_literal_computation():
    """L(P,K) = estimated_future_rate / search_budget."""
    m = _mk(future_discovery_rate=0.5, evidence={"search_budget": 2.0})
    r = evaluate(m)
    assert abs(r["L"] - 0.25) < 1e-9

def test_deterministic():
    m = _mk()
    assert evaluate(m) == evaluate(m)

def test_zero_cost_gives_zero_A():
    m = _mk(baseline_cost=0)
    assert compute_A(m) == 0.0

def test_V_evidence_levels():
    cfg = Equation24Config()
    v_surrogate = compute_V(_mk(evidence={"fidelity": "SURROGATE"}), cfg)
    v_signoff = compute_V(_mk(evidence={"fidelity": "SIGNOFF"}), cfg)
    assert v_signoff > v_surrogate
    assert v_signoff == 1.0

def test_config_coefficients():
    cfg = Equation24Config(kappa=0.5)
    m = _mk(evidence={"primitive_verified": True})
    r = evaluate(m, cfg)
    assert r["bonus_I"] > 1.0

