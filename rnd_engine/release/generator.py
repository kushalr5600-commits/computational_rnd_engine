"""Release/tapout framework (Phase K, toolless scope, security).

Assesses a build's release level from its stage manifests and either emits a
tapout package (TAPEOUT only, when every gate is genuinely PASSED) or writes a
refusal notice (every other level).  The framework can refuse, but it never
claims.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

# Python 3.10 compatibility: ``datetime.UTC`` only exists in 3.11+.
# ``timezone.utc`` and ``datetime.UTC`` are the same object on 3.11+.
UTC = timezone.utc

from ..microarchitecture import microarchitecture_hash
from ..microarchitecture.model import MicroArchitectureSpec
from ..physical.model import PhysicalManifest
from ..rtl.model import RtlManifest
from ..signoff.model import SignoffResult
from ..specification import (
    SPECIFICATION_SCHEMA_VERSION,
    ArchitectureSpecification,
    specification_hash,
)
from ..synthesis.model import SynthesisManifest
from ..technology.model import TechnologyManifest
from ..verification.model import VerificationManifest
from .model import (
    _LEVEL_GATES,
    RELEASE_SCHEMA_VERSION,
    GateStatus,
    ReleaseLevel,
    ReleaseManifest,
)

GATE_PASS = "PASS"
GATE_BLOCKED = "BLOCKED"
GATE_FAILED = "FAILED"
GATE_NOT_RUN = "NOT_RUN"

_STATUS_MAP: dict[str, str] = {
    "PASSED": GATE_PASS,
    "PASS": GATE_PASS,
    "BLOCKED": GATE_BLOCKED,
    "NOT_RUN": GATE_NOT_RUN,
    "FAILED": GATE_FAILED,
}


class ReleaseError(RuntimeError):
    """Raised when a release package cannot be assembled for a design."""





def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _norm(status: str) -> str:
    """Normalise a stage-manifest status to release vocabulary."""
    return _STATUS_MAP.get(status, status)


def assess_gate(
    name: str, status: str, version: int | None = None,
    reason: str = "",
) -> GateStatus:
    """Build a GateStatus, normalising to release vocabulary."""
    return GateStatus(
        name=name, status=_norm(status),
        gate_schema_version=version, reason=reason,
    )


def _gate_matches(actual: str, expected: str) -> bool:
    """Does a gate's actual normalised status satisfy expected?"""
    if expected == "PASS":
        return actual == GATE_PASS
    if expected == "True":
        return actual == GATE_PASS
    if expected == "False":
        return actual in (GATE_BLOCKED, GATE_FAILED)
    return actual == expected


def _max_reached_level(gate_map: dict[str, str]) -> ReleaseLevel:
    """Highest level whose required gates all match, scanning 0..7 in order."""
    max_level = ReleaseLevel.EXPLORE
    for level in ReleaseLevel:
        required = _LEVEL_GATES.get(level, {})
        if all(
            _gate_matches(gate_map.get(name, GATE_NOT_RUN), expected)
            for name, expected in required.items()
        ):
            max_level = level
        else:
            break
    return max_level



def _evaluate_gates(
    micro: MicroArchitectureSpec,
    specification: ArchitectureSpecification | None,
    rtl_manifest: RtlManifest | None,
    verification_manifest: VerificationManifest | None,
    synthesis_manifest: SynthesisManifest | None,
    physical_manifest: PhysicalManifest | None,
    signoff_result: SignoffResult | None,
) -> list[GateStatus]:
    """Evaluate every gate named in ``_LEVEL_GATES`` from stage manifests."""
    gates: list[GateStatus] = []

    # EXPLORE: surrogate score (always available -- design was searched)
    gates.append(assess_gate("surrogate_score", GATE_PASS,
                             reason="design produced by InventionEngine search"))

    # SPECIFIED: specification + schema version
    if specification is not None:
        gates.append(assess_gate("specification", GATE_PASS))
        schema_ok = (
            specification.specification_schema_version
            == SPECIFICATION_SCHEMA_VERSION
        )
        gates.append(assess_gate(
            "specification_schema",
            GATE_PASS if schema_ok else GATE_FAILED,
            version=specification.specification_schema_version,
            reason="" if schema_ok else "specification schema version mismatch",
        ))
    else:
        gates.append(assess_gate("specification", GATE_NOT_RUN,
                                 reason="no specification built"))
        gates.append(assess_gate("specification_schema", GATE_NOT_RUN,
                                 reason="no specification built"))

    # RTLIZED: structural + elaboration
    if rtl_manifest is not None:
        prov = rtl_manifest.provenance or {}
        gates.append(assess_gate("structural",
                                 prov.get("structural_check", GATE_NOT_RUN)))
        gates.append(assess_gate("elaboration",
                                 prov.get("elaboration_check", GATE_NOT_RUN)))
    else:
        gates.append(assess_gate("structural", GATE_NOT_RUN,
                                 reason="no RTL manifest"))
        gates.append(assess_gate("elaboration", GATE_NOT_RUN,
                                 reason="no RTL manifest"))

    # VERIFIED: reference model
    if verification_manifest is not None:
        ver_prov = verification_manifest.provenance or {}
        gates.append(assess_gate("reference_model",
                                 ver_prov.get("reference_model", GATE_NOT_RUN)))
    else:
        gates.append(assess_gate("reference_model", GATE_NOT_RUN,
                                 reason="no verification manifest"))

    # SYNTHESIZED: synthesis config generated (tool execution BLOCKED)
    if synthesis_manifest is not None and synthesis_manifest.synthesis_config_hash:
        gates.append(assess_gate("synthesis_config", GATE_PASS,
                                 reason="flow generated; tool execution BLOCKED"))
    elif synthesis_manifest is not None:
        gates.append(assess_gate("synthesis_config",
                                 _norm(synthesis_manifest.status),
                                 reason="synthesis not run"))
    else:
        gates.append(assess_gate("synthesis_config", GATE_NOT_RUN,
                                 reason="no synthesis manifest"))

    # PHYSICATED: physical plan generated (tool execution BLOCKED/NOT_RUN)
    if physical_manifest is not None and physical_manifest.config is not None:
        gates.append(assess_gate("physical_plan", GATE_PASS,
                                 reason="plan generated; tool execution BLOCKED"))
    elif physical_manifest is not None:
        gates.append(assess_gate("physical_plan", GATE_NOT_RUN,
                                 reason="no physical config (foundry node or no PDK)"))
    else:
        gates.append(assess_gate("physical_plan", GATE_NOT_RUN,
                                 reason="no physical manifest"))

    # SIGNED_OFF: signoff assembled + tapeout_ready
    if signoff_result is not None:
        gates.append(assess_gate("signoff_orchestration", GATE_PASS,
                                 reason="signoff result assembled"))
        tapeout = GATE_PASS if signoff_result.tapeout_ready else GATE_BLOCKED
        gates.append(assess_gate(
            "tapeout_ready", tapeout,
            reason=("tapeout_ready False in toolless flow"
                   if not signoff_result.tapeout_ready else ""),
        ))
    else:
        gates.append(assess_gate("signoff_orchestration", GATE_NOT_RUN,
                                 reason="no signoff result"))
        gates.append(assess_gate("tapeout_ready", GATE_NOT_RUN,
                                 reason="no signoff result"))

    return gates



def assess_release(
    micro: MicroArchitectureSpec,
    specification: ArchitectureSpecification | None = None,
    rtl_manifest: RtlManifest | None = None,
    verification_manifest: VerificationManifest | None = None,
    synthesis_manifest: SynthesisManifest | None = None,
    technology_manifest: TechnologyManifest | None = None,
    physical_manifest: PhysicalManifest | None = None,
    signoff_result: SignoffResult | None = None,
) -> ReleaseManifest:
    """Assess the release level of a build from its stage manifests.

    Every gate status is derived verbatim from the corresponding manifest's
    honest outcome -- this function never softens or re-judges a result. The
    returned ``ReleaseManifest.reached_level`` is the highest level whose
    required gates all match their expected values; ``tapeout_ready`` is True
    only when the TAPEOUT level's ``tapeout_ready`` gate is PASS.
    """
    design_id = micro.design_id

    # All provided manifests must agree on design_id.
    for name, manifest in (
        ("specification", specification),
        ("rtl", rtl_manifest),
        ("verification", verification_manifest),
        ("synthesis", synthesis_manifest),
        ("technology", technology_manifest),
        ("physical", physical_manifest),
        ("signoff", signoff_result),
    ):
        if manifest is not None and manifest.design_id != design_id:
            raise ReleaseError(
                f"{name} manifest design {manifest.design_id} != {design_id}"
            )

    gates = _evaluate_gates(
        micro, specification, rtl_manifest, verification_manifest,
        synthesis_manifest, physical_manifest, signoff_result,
    )
    gate_map = {g.name: g.status for g in gates}
    reached_level = _max_reached_level(gate_map)
    tapeout_ready = (
        reached_level == ReleaseLevel.TAPEOUT
        and gate_map.get("tapeout_ready") == GATE_PASS
    )

    # Content-addressed IP provenance -- no proprietary PDK content.
    ip_provenance: dict[str, Any] = {
        "design_id": design_id,
        "architecture_schema_version": micro.architecture_schema_version,
        "microarchitecture_hash": microarchitecture_hash(micro),
    }
    if specification is not None:
        ip_provenance["specification_hash"] = specification_hash(specification)
    if rtl_manifest is not None:
        ip_provenance["rtl_architecture_hash"] = rtl_manifest.architecture_hash
    if synthesis_manifest is not None:
        ip_provenance["synthesis_config_hash"] = synthesis_manifest.synthesis_config_hash
    if signoff_result is not None:
        ip_provenance["signoff_hash"] = hashlib.sha256(
            signoff_result.model_dump_json().encode("utf-8")
        ).hexdigest()[:32]

    blocked = [g for g in gates if g.status in (GATE_BLOCKED, GATE_FAILED)]

    return ReleaseManifest(
        design_id=design_id,
        reached_level=reached_level,
        tapeout_ready=tapeout_ready,
        gates=gates,
        release_schema_version=RELEASE_SCHEMA_VERSION,
        ip_provenance=ip_provenance,
        provenance={
            "microarchitecture_hash": ip_provenance["microarchitecture_hash"],
            "reached_level_name": reached_level.name,
            "blocked_gates": [g.name for g in blocked],
            "gates_blocked": len(blocked),
            "gates_total": len(gates),
        },
    )
