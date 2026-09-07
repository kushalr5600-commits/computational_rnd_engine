"""Experiment framework models (Phase J)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from ..fidelity.model import PromotionPolicy

EXPERIMENT_SCHEMA_VERSION: int = 1


class ExperimentConfig(BaseModel):
    """Full configuration of one experiment run.

    Deterministic: the experiment id is a digest of this config, so two runs
    with identical configs land in the same directory and must produce
    byte-identical artifacts.
    """

    name: str
    seed: int
    domain: str
    population: int
    generations: int
    promotion: PromotionPolicy = Field(default_factory=PromotionPolicy)
    provenance: dict[str, Any] = Field(default_factory=dict)


class ArtifactRecord(BaseModel):
    """One artifact with its content hash."""

    path: str
    sha256: str


class ExperimentManifest(BaseModel):
    """Per-artifact SHA-256 manifest of one experiment run."""

    experiment_id: str
    experiment_schema_version: int = EXPERIMENT_SCHEMA_VERSION
    config: ExperimentConfig
    artifacts: list[ArtifactRecord] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)
