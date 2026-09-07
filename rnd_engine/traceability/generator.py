"""Traceability chain (Phase F).

Builds one content-addressed manifest per build that chains every stage:
architecture -> specification -> microarchitecture -> RTL -> verification ->
synthesis. Each link records the stage manifest's SHA-256, so any later change
to any stage breaks the chain visibly instead of silently.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from ..microarchitecture.model import MicroArchitectureSpec
from ..rtl.model import RtlManifest
from ..synthesis.model import SynthesisManifest
from ..verification.model import VerificationManifest
from .model import StageLink, TraceabilityManifest

TRACEABILITY_SCHEMA_VERSION: int = 1


class TraceabilityError(RuntimeError):
    """Raised when the provenance chain cannot be built consistently."""


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_traceability_manifest(
    micro: MicroArchitectureSpec,
    rtl_manifest: RtlManifest,
    verification_manifest: VerificationManifest,
    synthesis_manifest: SynthesisManifest,
    out_dir: str | Path = "artifacts",
) -> TraceabilityManifest:
    """Assemble, validate and persist the per-build provenance chain."""
    if len({m.design_id for m in (micro, rtl_manifest, verification_manifest,
                                  synthesis_manifest)}) != 1:
        raise TraceabilityError("stage manifests disagree on design_id")
    if verification_manifest.rtl_architecture_hash != rtl_manifest.architecture_hash:
        raise TraceabilityError("verification manifest does not match the RTL build hash")
    if synthesis_manifest.rtl_architecture_hash != rtl_manifest.architecture_hash:
        raise TraceabilityError("synthesis manifest does not match the RTL build hash")

    base = Path(out_dir)
    links = [
        StageLink(
            stage="rtl",
            artifact=f"rtl/{micro.design_id}/manifest.json",
            sha256=_file_sha256(base / "rtl" / micro.design_id / "manifest.json"),
            schema_version=rtl_manifest.rtl_schema_version,
        ),
        StageLink(
            stage="verification",
            artifact=f"verification/{micro.design_id}/manifest.json",
            sha256=_file_sha256(base / "verification" / micro.design_id / "manifest.json"),
            schema_version=verification_manifest.verification_schema_version,
            status=verification_manifest.provenance.get("reference_model"),
        ),
        StageLink(
            stage="synthesis",
            artifact=f"reports/synthesis/{micro.design_id}/manifest.json",
            sha256=_file_sha256(
                base / "reports" / "synthesis" / micro.design_id / "manifest.json"),
            schema_version=synthesis_manifest.synthesis_schema_version,
            status=synthesis_manifest.status,
        ),
    ]
    manifest = TraceabilityManifest(
        design_id=micro.design_id,
        architecture_schema_version=micro.architecture_schema_version,
        specification_hash=micro.specification_hash,
        microarchitecture_hash=rtl_manifest.microarchitecture_hash,
        stages=links,
        traceability_schema_version=TRACEABILITY_SCHEMA_VERSION,
        tool_versions=dict(synthesis_manifest.provenance.get("tool_versions", {})),
        provenance={
            **(micro.provenance or {}),
            "rtl_architecture_hash": rtl_manifest.architecture_hash,
            "synthesis_status": synthesis_manifest.status,
        },
    )
    out = base / "traceability" / micro.design_id
    out.mkdir(parents=True, exist_ok=True)
    (out / "manifest.json").write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    return manifest
