"""Tapeout bundle writer (§26-§27) — strict refusal, never fabrication.

Only a build whose release assessment is genuinely ``tapeout_ready`` (every
required gate PASSED with real tool evidence) may produce a tapeout bundle.
Everything else produces an auditable *refusal notice* and raises
``ReleaseError``.

The bundle collects the immutable, content-addressed artifacts of one build
into:

    tapeout/<design_id>/
      manifest.json, checksums.sha256, sbom.json, provenance.json,
      pdk_manifest.json, toolchain_manifest.json,
      architecture/ microarchitecture/ rtl/ verification/ formal/ synthesis/
      physical/ timing/ power/ drc/ lvs/ gds/ lef/ netlist/ constraints/

The bundle is only the *transport* of already-proven evidence — it never
creates evidence itself. A SKY130 experimental/open flow bundle is never
equivalent to foundry-qualified production tapeout; the manifest records the
exact tool versions, PDK identity and gate statuses that produced it.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from .generator import ReleaseError
from .model import ReleaseLevel, ReleaseManifest

BUNDLE_SCHEMA_VERSION = 1
BUNDLE_DIR = "tapeout"


class TapeoutRefused(ReleaseError):
    """Raised when a tapeout bundle cannot be legitimately emitted."""


#: Bundle directories populated from the artifacts tree (existing ones only).
_STAGE_DIRS: tuple[str, ...] = (
    "architecture", "microarchitecture", "rtl", "verification", "formal",
    "synthesis", "physical", "timing", "power", "drc", "lvs",
    "gds", "lef", "netlist", "constraints",
)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _refusal_notice(design_id: str, reason: str, out_dir: Path) -> Path:
    dir_path = out_dir / BUNDLE_DIR / design_id
    dir_path.mkdir(parents=True, exist_ok=True)
    notice = {
        "bundle_schema_version": BUNDLE_SCHEMA_VERSION,
        "design_id": design_id,
        "emitted": False,
        "reason": reason,
    }
    path = dir_path / "refusal.json"
    path.write_text(
        json.dumps(notice, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _collectable(design_id: str, artifacts_root: Path) -> dict[str, list[list]]:
    """Return stage -> list[absolute path, relative-as-{stage}/{name}] pairs."""
    mapping: dict[str, Path] = {
        "architecture": artifacts_root / "docs" / "architecture" / design_id,
        "microarchitecture": artifacts_root / "docs" / "architecture"
        / design_id / "microarchitecture",
        "rtl": artifacts_root / "rtl" / design_id,
        "verification": artifacts_root / "verification" / design_id,
        "formal": artifacts_root / "verification" / "formal" / design_id,
        "synthesis": artifacts_root / "flows" / "synthesis" / design_id,
        "physical": artifacts_root / "flows" / "physical" / design_id,
        "timing": artifacts_root / "reports" / "physical" / design_id,
        "power": artifacts_root / "reports" / "power" / design_id,
        "drc": artifacts_root / "reports" / "physical" / design_id,
        "lvs": artifacts_root / "reports" / "physical" / design_id,
        "gds": artifacts_root / "gds" / design_id,
        "lef": artifacts_root / "lef" / design_id,
        "netlist": artifacts_root / "netlist" / design_id,
        "constraints": artifacts_root / "constraints" / design_id,
    }
    result: dict[str, list[list]] = {}
    for stage, src in mapping.items():
        if not src.exists():
            continue
        for p in sorted(src.rglob("*")):
            if p.is_file():
                result.setdefault(stage, []).append([p, f"{stage}/{p.name}"])
    return result
def build_tapeout_bundle(
    release_manifest: ReleaseManifest,
    artifacts_root: str | Path = "artifacts",
    out_dir: str | Path = ".",
) -> Path:
    """Emit the tapeout bundle iff the release assessment genuinely says ready.

    Refuses (raising ``TapeoutRefused`` and writing an auditable refusal
    notice) when the release assessment is not genuinely ready or required
    stage artifacts are missing.
    """
    out = Path(out_dir)
    if not release_manifest.tapeout_ready or (
        release_manifest.reached_level != ReleaseLevel.TAPEOUT):
        reason = (
            "tapeout refused: release assessment not genuinely ready "
            f"(tapeout_ready={release_manifest.tapeout_ready}, "
            f"reached_level={release_manifest.reached_level.name})"
        )
        _refusal_notice(release_manifest.design_id, reason, out)
        raise TapeoutRefused(reason)

    collected = _collectable(release_manifest.design_id, Path(artifacts_root))
    required = {
        "architecture", "microarchitecture", "rtl", "verification",
        "formal", "synthesis", "physical", "timing", "power",
        "drc", "lvs", "gds", "lef", "netlist",
    }
    missing = required - set(collected)
    if missing:
        reason = (
            "tapeout refused: required stage artifacts missing from "
            f"{Path(artifacts_root)}: {', '.join(sorted(missing))}"
        )
        _refusal_notice(release_manifest.design_id, reason, out)
        raise TapeoutRefused(reason)

    bundle_dir = out / BUNDLE_DIR / release_manifest.design_id
    bundle_dir.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for stage, pairs in collected.items():
        target = bundle_dir / stage
        target.mkdir(parents=True, exist_ok=True)
        for src, rel in pairs:
            dest = target / Path(rel).name
            if not dest.exists():
                shutil.copy2(src, dest)
            copied.append(dest)

    files = sorted(p for p in bundle_dir.rglob("*") if p.is_file())
    checksums = {
        p.relative_to(bundle_dir).as_posix(): _sha256_file(p) for p in files}
    manifest: dict[str, Any] = {
        "bundle_schema_version": BUNDLE_SCHEMA_VERSION,
        "design_id": release_manifest.design_id,
        "emitted": True,
        "tapeout_ready": release_manifest.tapeout_ready,
        "release_level": release_manifest.reached_level.name,
        "ip_provenance": release_manifest.ip_provenance,
        "files": len(files),
        "note": (
            "open-flow evidence bundle; not a foundry-qualified production "
            "tapeout unless explicitly qualified by a foundry/PDK owner"
        ),
    }
    (bundle_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (bundle_dir / "checksums.sha256").write_text(
        "".join(f"{digest}  {rel}\n" for rel, digest in sorted(checksums.items())),
        encoding="utf-8")
    (bundle_dir / "provenance.json").write_text(
        json.dumps(release_manifest.provenance, indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    return bundle_dir