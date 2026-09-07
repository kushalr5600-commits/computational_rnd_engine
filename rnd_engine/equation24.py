from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import Metrics


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))

@dataclass(frozen=True)
class Equation24Config:
    kappa: float = 0.20
    eta: float = 0.20
    xi: float = 0.20
    lam: float = 1.00
    mu: float = 0.25
    nu: float = 0.50
    rho: float = 0.75
    sigma: float = 1.00
    max_error: float = 1e-9
    min_generalization: float = 0.70
    min_reusability: float = 0.95
    min_reproducibility: float = 0.95
    max_resource_cost: float = 10_000.0
    v_analytical_weight: float = 0.30
    v_lint_weight: float = 0.45
    v_simulation_weight: float = 0.70
    v_formal_weight: float = 0.85
    v_synthesis_weight: float = 0.90
    v_signoff_weight: float = 1.00

def compute_A(m: Metrics) -> float:
    if m.baseline_cost <= 0 or m.optimized_cost <= 0:
        return 0.0
    return m.baseline_cost / m.optimized_cost

def compute_V(m: Metrics, c: Equation24Config) -> float:
    evidence = m.evidence or {}
    max_v = c.v_analytical_weight
    fidelity_map = {
        "SURROGATE": c.v_analytical_weight, "RTL": c.v_lint_weight,
        "SIMULATION": c.v_simulation_weight, "FORMAL": c.v_formal_weight,
        "SYNTHESIS": c.v_synthesis_weight, "PHYSICAL": c.v_signoff_weight,
        "SIGNOFF": c.v_signoff_weight,
    }
    fidelity = evidence.get("fidelity", "SURROGATE")
    max_v = max(max_v, fidelity_map.get(fidelity, c.v_analytical_weight))
    if evidence.get("simulation_passed"):
        max_v = max(max_v, c.v_simulation_weight)
    if evidence.get("formal_passed"):
        max_v = max(max_v, c.v_formal_weight)
    if evidence.get("synthesis_passed"):
        max_v = max(max_v, c.v_synthesis_weight)
    return _clamp01(max_v)

def compute_G(m: Metrics) -> float:
    return _clamp01(m.generalization)
def compute_U(m: Metrics) -> float:
    return _clamp01(m.utility)
def compute_N(m: Metrics) -> float:
    return _clamp01(m.novelty)
def compute_R(m: Metrics) -> float:
    return _clamp01(m.reusability)
def compute_H(m: Metrics) -> float:
    return _clamp01(m.hardware_efficiency)
def compute_I(m: Metrics) -> float:
    useful = _clamp01(m.useful_structure)
    if (m.evidence or {}).get("primitive_verified"):
        useful = min(1.0, useful + 0.1)
    return useful

def compute_D(m: Metrics) -> float:
    search_cost = max(m.search_cost, 1e-6)
    best = (m.evidence or {}).get("best_verified_improvement", 0.0)
    return best / search_cost

def compute_L(m: Metrics) -> float:
    evidence = m.evidence or {}
    budget = max(evidence.get("search_budget", 1.0), 1.0)
    rate = evidence.get("estimated_future_rate", m.future_discovery_rate)
    return _clamp01(rate) / budget

def _compute_denominator_terms(m: Metrics, c: Equation24Config) -> dict[str, float]:
    return {
        "C_search": max(m.search_cost, 0.0),
        "E": max(m.correctness_error, 0.0),
        "M": max(m.memory_cost, 0.0),
        "D_complexity": max(m.complexity_cost, 0.0),
        "Energy": max(m.energy_cost, 0.0),
        "Fragility": _clamp01(m.fragility),
    }

def check_feasibility(m: Metrics, c: Equation24Config) -> tuple[bool, float]:
    v = 0.0
    v += max(0.0, m.correctness_error - c.max_error)
    v += max(0.0, c.min_generalization - m.generalization)
    v += max(0.0, c.min_reusability - m.reusability)
    v += max(0.0, c.min_reproducibility - m.reproducibility)
    v += max(0.0, (m.memory_cost + m.energy_cost) - c.max_resource_cost) / max(c.max_resource_cost, 1.0)
    return (v == 0.0, v)

def evaluate(m: Metrics, config: Equation24Config | None = None) -> dict[str, Any]:
    cfg = config or Equation24Config()
    A = compute_A(m)
    V = compute_V(m, cfg)
    G = compute_G(m)
    U = compute_U(m)
    N = compute_N(m)
    R = compute_R(m)
    H = compute_H(m)
    I = compute_I(m)
    D = compute_D(m)
    L = compute_L(m)
    base_num = A * V * G * U * N * R * H
    bonus_I = 1.0 + cfg.kappa * I
    bonus_D = 1.0 + cfg.eta * D
    bonus_L = 1.0 + cfg.xi * L
    numerator = base_num * bonus_I * bonus_D * bonus_L
    denom_terms = _compute_denominator_terms(m, cfg)
    denominator = (
        1.0
        + denom_terms["C_search"]
        + cfg.lam * denom_terms["E"]
        + cfg.mu * denom_terms["M"]
        + cfg.nu * denom_terms["D_complexity"]
        + cfg.rho * denom_terms["Energy"]
        + cfg.sigma * denom_terms["Fragility"]
    )
    feasible, violation = check_feasibility(m, cfg)
    omega = (numerator / denominator) if feasible and denominator > 0 else 0.0
    return {
        "omega": omega, "feasible": feasible, "violation": violation,
        "numerator": numerator, "denominator": denominator,
        "A": A, "V": V, "G": G, "U": U, "N": N, "R": R, "H": H,
        "I": I, "D": D, "L": L,
        "bonus_I": bonus_I, "bonus_D": bonus_D, "bonus_L": bonus_L,
        **denom_terms,
    }
