"""Experiment framework (Phase J).

Runs a deterministic search + promotion experiment and persists every artifact
under ``artifacts/experiments/<experiment_id>/`` with a per-artifact SHA-256
manifest. Same config -> same experiment id -> byte-identical artifacts.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ..engine import InventionEngine
from ..fidelity.model import PromotionFunnel
from ..fidelity.policy import apply_promotion
from ..models import Domain
from ..reproducibility import stable_digest
from .model import (
    EXPERIMENT_SCHEMA_VERSION,
    ArtifactRecord,
    ExperimentConfig,
    ExperimentManifest,
)

__all__ = [
    "EXPERIMENT_SCHEMA_VERSION",
    "ArtifactRecord",
    "ExperimentConfig",
    "ExperimentManifest",
    "experiment_id",
    "run_experiment",
]


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def experiment_id(config: ExperimentConfig) -> str:
    """Content-addressed experiment id: pure function of the config."""
    return stable_digest(config.model_dump(mode="json"), length=16)


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_experiment(
    config: ExperimentConfig,
    out_dir: str | Path = "artifacts",
) -> tuple[ExperimentManifest, PromotionFunnel]:
    """Execute the experiment and persist its artifacts.

    Returns the manifest (with per-artifact SHA-256 hashes) and the promotion
    funnel so callers can inspect the funnel without re-reading the disk.
    """
    exp_id = experiment_id(config)
    exp_dir = Path(out_dir) / "experiments" / exp_id
    exp_dir.mkdir(parents=True, exist_ok=True)

    engine = InventionEngine(
        population=config.population,
        generations=config.generations,
        seed=config.seed,
        domain=Domain(config.domain.lower()),
        archive_path=str(exp_dir / "archive.jsonl"),
        history_path=str(exp_dir / "run_history.json"),
    )
    engine.run()

    candidates = engine.archive.best(10_000)
    # Promotion at the fidelity the run actually evidences. This experiment
    # executes the SURROGATE loop only — no per-candidate RTL/signoff flows —
    # so every candidate's honest evidence level is SURROGATE (None ->
    # SURROGATE inside apply_promotion). Deeper-fidelity experiments arrive
    # when per-candidate flow execution is wired in Phase K's CLI.
    funnel = apply_promotion(
        [(c.score.omega if c.score else 0.0, None) for c in candidates],
        config.promotion,
    )
    _write_json(exp_dir / "promotion.json", funnel.model_dump(mode="json"))
    artifacts = [ArtifactRecord(path="promotion.json",
                                sha256=_sha256_file(exp_dir / "promotion.json"))]

    # Serialize the ranked candidate table for reproducibility.
    candidates_table = [
        {
            "rank": i + 1,
            "design_id": c.design.id,
            "omega": c.score.omega if c.score else None,
            "constraints_satisfied": (
                c.score.constraints_satisfied if c.score else None),
        }
        for i, c in enumerate(candidates)
    ]
    _write_json(exp_dir / "candidates.json", candidates_table)
    _write_json(exp_dir / "config.json", config.model_dump(mode="json"))
    _write_json(exp_dir / "run_history.json", engine.history)

    artifacts += [
        ArtifactRecord(path="candidates.json", sha256=_sha256_file(exp_dir / "candidates.json")),
        ArtifactRecord(path="config.json", sha256=_sha256_file(exp_dir / "config.json")),
        ArtifactRecord(path="run_history.json", sha256=_sha256_file(exp_dir / "run_history.json")),
        ArtifactRecord(path="archive.jsonl", sha256=_sha256_file(exp_dir / "archive.jsonl")),
    ]

    manifest = ExperimentManifest(
        experiment_id=exp_id,
        experiment_schema_version=EXPERIMENT_SCHEMA_VERSION,
        config=config,
        artifacts=artifacts,
        summary={
            "evaluated": len(candidates),
            "generations": config.generations,
            "population": config.population,
        },
        provenance={
            "engine": "InventionEngine",
            "objective": "OmegaObjective",
            "schema_version": EXPERIMENT_SCHEMA_VERSION,
        },
    )
    _write_json(exp_dir / "manifest.json", manifest.model_dump(mode="json"))
    return manifest, funnel
