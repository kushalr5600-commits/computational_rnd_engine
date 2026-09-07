from __future__ import annotations

from dataclasses import dataclass

from .models import Metrics, OmegaScore


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))

@dataclass(frozen=True)
class OmegaConfig:
    kappa: float = 0.20
    eta: float = 0.20
    xi: float = 0.20
    lam: float = 1.00
    mu: float = 0.25
    nu: float = 0.50
    rho: float = 0.75
    sigma: float = 1.00
    tau_llm: float = 0.50
    max_error: float = 1e-9
    min_generalization: float = 0.70
    min_reusability: float = 0.95
    min_reproducibility: float = 0.95
    max_resource_cost: float = 10_000.0

class OmegaObjective:
    """Canonical, deterministic Ω objective. No model/LLM dependency."""
    def __init__(self, config: OmegaConfig | None = None):
        self.config = config or OmegaConfig()

    def evaluate(self, m: Metrics) -> OmegaScore:
        if m.baseline_cost <= 0 or m.optimized_cost <= 0:
            raise ValueError("Costs must be positive")
        amplification = m.baseline_cost / m.optimized_cost
        verified = m.correctness_error <= self.config.max_error
        feasible = (
            verified
            and m.generalization >= self.config.min_generalization
            and m.reusability >= self.config.min_reusability
            and m.reproducibility >= self.config.min_reproducibility
            and m.memory_cost + m.energy_cost <= self.config.max_resource_cost
        )
        numerator = (
            amplification
            * clamp01(m.generalization)
            * clamp01(m.utility)
            * clamp01(m.novelty)
            * clamp01(m.reusability)
            * clamp01(m.hardware_efficiency)
            * (1.0 + self.config.kappa * clamp01(m.useful_structure))
            * (1.0 + self.config.eta * clamp01(m.search_efficiency))
            * (1.0 + self.config.xi * clamp01(m.future_discovery_rate))
        )
        denominator = (
            1.0
            + max(m.search_cost, 0.0)
            + self.config.lam * max(m.correctness_error, 0.0)
            + self.config.mu * max(m.memory_cost, 0.0)
            + self.config.nu * max(m.complexity_cost, 0.0)
            + self.config.rho * max(m.energy_cost, 0.0)
            + self.config.sigma * max(m.fragility, 0.0)
        )
        return OmegaScore(
            omega=(numerator / denominator) if feasible else 0.0,
            amplification=amplification,
            numerator=numerator,
            denominator=denominator,
            metrics=m,
            verified=verified,
            constraints_satisfied=feasible,
        )
