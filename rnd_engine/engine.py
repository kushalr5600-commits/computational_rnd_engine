
from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from .archive import Archive
from .evaluator import Evaluator
from .models import Candidate, Domain
from .objective import OmegaObjective
from .search import SearchEngine


class InventionEngine:
    """Closed-loop CPU/GPU invention search."""

    def __init__(
        self,
        population: int = 32,
        generations: int = 10,
        seed: int = 42,
        domain: Domain = Domain.HETEROGENEOUS,
        workloads: list[str] | None = None,
        archive_path: str | None = None,
        history_path: str | None = None,
    ):
        self.population_size = population
        self.generations = generations
        self.domain = domain
        self.objective = OmegaObjective()
        self.search = SearchEngine(seed, objective_config=dataclasses.asdict(self.objective.config))
        self.evaluator = Evaluator(workloads)
        self.archive = (
            Archive(path=archive_path) if archive_path is not None else Archive()
        )
        self._history_path = history_path or "artifacts/run_history.json"
        self.history = []

    def _constraint_violation(self, candidate: Candidate) -> float:
        m = candidate.metrics
        config = self.objective.config

        violation = 0.0

        violation += max(
            0.0,
            m.correctness_error - config.max_error,
        )

        violation += max(
            0.0,
            config.min_generalization - m.generalization,
        )

        violation += max(
            0.0,
            config.min_reusability - m.reusability,
        )

        violation += max(
            0.0,
            config.min_reproducibility - m.reproducibility,
        )

        violation += max(
            0.0,
            (m.memory_cost + m.energy_cost)
            - config.max_resource_cost,
        ) / max(config.max_resource_cost, 1.0)

        return violation

    def _selection_key(self, candidate: Candidate) -> tuple[bool, float, float]:
        score = candidate.score
        if score is None:
            return False, float("-inf"), float("-inf")

        if score.constraints_satisfied:
            return True, score.omega, 0.0

        return False, -self._constraint_violation(candidate), score.omega

    def run(self):
        population = self.search.seed(
            self.population_size,
            self.domain,
        )

        for generation in range(self.generations):
            evaluated = []
            designs = self.archive.designs()

            for design in population:
                metrics = self.evaluator.evaluate(design, designs)
                score = self.objective.evaluate(metrics)

                candidate = Candidate(
                    design=design,
                    metrics=metrics,
                    score=score,
                    status=(
                        "accepted"
                        if score.constraints_satisfied
                        else "rejected"
                    ),
                )

                evaluated.append(candidate)
                self.archive.add(candidate)

            evaluated.sort(
                key=self._selection_key,
                reverse=True,
            )

            elite = max(
                2,
                int(self.population_size * 0.2),
            )
            survivors = evaluated[:elite]
            best = survivors[0]

            row = {
                "generation": generation,
                "best_omega": best.score.omega,
                "speedup": best.score.amplification,
                "design_id": best.design.id,
                "verified": best.score.verified,
                "feasible": best.score.constraints_satisfied,
                "constraint_violation": self._constraint_violation(best),
                "generalization": best.metrics.generalization,
                "reusability": best.metrics.reusability,
                "reproducibility": best.metrics.reproducibility,
                "population": len(evaluated),
            }

            self.history.append(row)
            self._save_history()

            population = self.search.evolve(
                [candidate.design for candidate in survivors],
                generation + 1,
                self.population_size,
            )

        return {
            "history": self.history,
            "best": (
                self.archive.best(1)[0].model_dump()
                if self.archive.best(1)
                else None
            ),
        }

    def _save_history(self):
        path = Path(self._history_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.history, indent=2),
        )

