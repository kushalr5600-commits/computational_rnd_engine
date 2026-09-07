"""Traceability models: one chained manifest per build (Phase F)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class StageLink(BaseModel):
    """One stage of the architecture->silicon chain with its content hash."""

    stage: str
    artifact: str  # relative path of the stage's manifest
    sha256: str
    schema_version: int | None = None
    status: str | None = None


class TraceabilityManifest(BaseModel):
    """End-to-end provenance chain for one design build.

    Every link is content-addressed: recomputing any stage deterministically
    must reproduce the recorded hash, which is what makes the chain auditable.
    """

    design_id: str
    architecture_schema_version: int
    specification_hash: str
    microarchitecture_hash: str
    stages: list[StageLink] = Field(default_factory=list)
    traceability_schema_version: int = 1
    tool_versions: dict[str, str] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)

    def stage(self, name: str) -> StageLink | None:
        return next((s for s in self.stages if s.stage == name), None)
