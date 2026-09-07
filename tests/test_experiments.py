"""Phase J tests: deterministic experiment runs with provenance manifests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from rnd_engine.experiments import (
    EXPERIMENT_SCHEMA_VERSION,
    ExperimentConfig,
    experiment_id,
    run_experiment,
)
from rnd_engine.fidelity import PromotionPolicy


def _config(**overrides) -> ExperimentConfig:
    defaults = {
        "name": "funnel-demo", "seed": 42, "domain": "heterogeneous",
        "population": 8, "generations": 3,
        "promotion": PromotionPolicy(counts={"SURROGATE": 1000, "RTL": 5,
                                             "SYNTHESIS": 2, "PHYSICAL": 1,
                                             "SIGNOFF": 1}),
    }
    defaults.update(overrides)
    return ExperimentConfig(**defaults)


def test_experiment_id_is_content_addressed(tmp_path):
    assert experiment_id(_config()) == experiment_id(_config())
    assert experiment_id(_config(seed=43)) != experiment_id(_config())


def test_run_is_deterministic_across_trees(tmp_path):
    """Same config -> same experiment id -> byte-identical artifacts."""
    cfg = _config()
    ids, digests = [], []
    for sub in ("a", "b"):
        manifest, funnel = run_experiment(cfg, tmp_path / sub)
        ids.append(manifest.experiment_id)
        digests.append(hashlib.sha256(
            json.dumps(funnel.model_dump(mode="json"), sort_keys=True)
            .encode()).hexdigest())
    assert ids[0] == ids[1] == experiment_id(cfg)
    assert digests[0] == digests[1]


def test_manifest_artifacts_match_on_disk(tmp_path):
    manifest, _ = run_experiment(_config(), tmp_path)
    assert manifest.experiment_schema_version == EXPERIMENT_SCHEMA_VERSION
    assert {a.path for a in manifest.artifacts} == {
        "promotion.json", "candidates.json", "config.json",
        "run_history.json", "archive.jsonl"}
    for record in manifest.artifacts:
        data = (Path(tmp_path) / "experiments" / manifest.experiment_id
                / record.path).read_bytes()
        assert hashlib.sha256(data).hexdigest() == record.sha256


def test_summary_and_funnel_shape(tmp_path):
    cfg = _config()
    manifest, funnel = run_experiment(cfg, tmp_path)
    assert manifest.summary["population"] == 8
    assert manifest.summary["generations"] == 3
    assert manifest.summary["evaluated"] > 0
    # SURROGATE-only run: honest evidence, no candidate claims RTL+.
    assert set(funnel.summary()) == {"SURROGATE"}
    assert funnel.summary()["SURROGATE"] == manifest.summary["evaluated"]
    assert all(rec.promoted_to == "SURROGATE" for recs in
               funnel.levels.values() for rec in recs)


def test_promotion_counts_respected_in_experiment(tmp_path):
    cfg = _config(promotion=PromotionPolicy(
        counts={"SURROGATE": 3, "RTL": 5, "SYNTHESIS": 2, "PHYSICAL": 1,
                "SIGNOFF": 1}))
    _, funnel = run_experiment(cfg, tmp_path)
    assert funnel.summary()["SURROGATE"] == 3


def test_funnel_persisted_with_manifest(tmp_path):
    manifest, funnel = run_experiment(_config(), tmp_path)
    exp_dir = Path(tmp_path) / "experiments" / manifest.experiment_id
    persisted = json.loads((exp_dir / "promotion.json").read_text("utf-8"))
    assert persisted == funnel.model_dump(mode="json")
    candidates = json.loads((exp_dir / "candidates.json").read_text("utf-8"))
    assert candidates[0]["rank"] == 1
    assert all("omega" in row for row in candidates)


def test_different_seeds_diverge(tmp_path):
    m1, _ = run_experiment(_config(seed=1), tmp_path / "a")
    m2, _ = run_experiment(_config(seed=2), tmp_path / "a")
    assert m1.experiment_id != m2.experiment_id
