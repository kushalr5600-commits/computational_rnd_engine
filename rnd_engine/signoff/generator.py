"""Signoff orchestration (Phase I).

Aggregates every stage manifest of one build into a single ``SignoffResult``.
Gate statuses are taken verbatim from the stage manifests — this package
never re-judges or softens a result. ``tapeout_ready`` is True only when
every gate is PASSED; with the current toolless flow that is impossible by
construction, which is exactly the point.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..microarchitecture.model import MicroArchitectureSpec
from ..physical.model import PhysicalManifest
from ..rtl.model import RtlManifest
from ..synthesis.model import SynthesisManifest
from ..technology.model import TechnologyManifest
from ..verification.model import VerificationManifest
from .model import (
    GATE_BLOCKED,
    GATE_FAILED,
    GATE_NOT_RUN,
    GATE_PASSED,
    SIGNOFF_SCHEMA_VERSION,
    GateResult,
    MeasuredMetrics,
    SignoffResult,
)

SIGNOFF_TOOLCHAIN_GATES: tuple[str, ...] = (
    "rtl_lint_verilator",
    "rtl_lint_iverilog",
    "simulation",
    "formal",
    "synthesis",
    "pdk_binding",
    "physical_implementation",
    "drc",
    "lvs",
)


class SignoffError(RuntimeError):
    """Raised when signoff cannot be assembled consistently."""


def _gate(name: str, stage: str, status: str, reason: str = "") -> GateResult:
    return GateResult(gate=name, stage=stage, status=status, reason=reason)


def collect_gates(
    rtl_manifest: RtlManifest,
    verification_manifest: VerificationManifest,
    synthesis_manifest: SynthesisManifest,
    technology_manifest: TechnologyManifest,
    physical_manifest: PhysicalManifest,
) -> list[GateResult]:
    """Map every stage manifest onto signoff gates, statuses verbatim."""
    prov = rtl_manifest.provenance
    gates = [
        _gate("rtl_structural", "rtl",
              prov.get("structural_check", GATE_NOT_RUN),
              "" if prov.get("structural_check") == GATE_PASSED
              else "structural check did not pass"),
        _gate("rtl_elaboration", "rtl",
              prov.get("elaboration_check", GATE_NOT_RUN),
              "" if prov.get("elaboration_check") == GATE_PASSED
              else "elaboration check did not pass"),
    ]
    for tool in ("verilator", "iverilog"):
        status = prov.get("lint_tools", {}).get(tool, GATE_NOT_RUN)
        gates.append(_gate(
            f"rtl_lint_{tool}", "rtl", status,
            "" if status == GATE_PASSED
            else f"{tool} not run (binary absent or flow not executed)"))
    ver_prov = verification_manifest.provenance
    for gate in ("reference_model", "simulation", "formal"):
        status = ver_prov.get(gate, GATE_NOT_RUN)
        gates.append(_gate(
            gate, "verification", status,
            "" if status == GATE_PASSED
            else f"{gate} gate not satisfied (toolless flow)"))
    gates.append(_gate(
        "synthesis", "synthesis", synthesis_manifest.status,
        "" if synthesis_manifest.status == GATE_PASSED
        else "yosys flow not executed"))
    gates.append(_gate(
        "pdk_binding", "technology", technology_manifest.status,
        "" if technology_manifest.status == GATE_PASSED
        else str(technology_manifest.provenance.get("reason", "PDK not bound/installed"))))
    phys_status = physical_manifest.status
    gates.append(_gate(
        "physical_implementation", "physical", phys_status,
        "" if phys_status == GATE_PASSED
        else str(physical_manifest.provenance.get("status_reason", "physical stages not run"))))
    for stage in ("drc", "lvs"):
        st = next((s for s in physical_manifest.stages if s.stage == stage), None)
        gates.append(_gate(
            stage, "physical", st.status if st else GATE_NOT_RUN,
            st.reason if st else "stage missing from physical manifest"))
    return gates

def signoff(
    micro: MicroArchitectureSpec,
    rtl_manifest: RtlManifest,
    verification_manifest: VerificationManifest,
    synthesis_manifest: SynthesisManifest,
    technology_manifest: TechnologyManifest,
    physical_manifest: PhysicalManifest,
    out_dir: str | Path = "artifacts",
) -> SignoffResult:
    """Assemble the aggregated signoff for one build and persist it.

    Honesty invariants enforced here (and tested):
    - statuses are copied verbatim from stage manifests;
    - ``tapeout_ready`` is True iff every gate is PASSED;
    - ``measured_metrics`` is only ever populated from a ``MeasuredMetrics``
      object explicitly produced by a tool run — the toolless flow leaves it
      all-None;
    - any manifest from a different design_id is rejected.
    """
    manifests = {
        "rtl": rtl_manifest, "verification": verification_manifest,
        "synthesis": synthesis_manifest, "technology": technology_manifest,
        "physical": physical_manifest,
    }
    for name, manifest in manifests.items():
        if manifest.design_id != micro.design_id:
            raise SignoffError(
                f"{name} manifest design {manifest.design_id} != {micro.design_id}")

    gates = collect_gates(
        rtl_manifest, verification_manifest, synthesis_manifest,
        technology_manifest, physical_manifest)
    blocked = [g.gate for g in gates if g.status in (GATE_BLOCKED, GATE_NOT_RUN, GATE_FAILED)]
    ready = all(g.status == GATE_PASSED for g in gates)

    surrogate = None
    if micro.provenance.get("surrogate_metrics"):
        surrogate = micro.provenance["surrogate_metrics"]

    result = SignoffResult(
        design_id=micro.design_id,
        architecture_schema_version=micro.architecture_schema_version,
        specification_hash=micro.specification_hash,
        rtl_architecture_hash=rtl_manifest.architecture_hash,
        signoff_schema_version=SIGNOFF_SCHEMA_VERSION,
        gates=gates,
        tapeout_ready=ready,
        blocked_gates=blocked,
        surrogate_metrics=surrogate,
        measured_metrics=MeasuredMetrics(),
        provenance={
            **(micro.provenance or {}),
            "toolchain_gates_pending": [g for g in SIGNOFF_TOOLCHAIN_GATES
                                        if g in blocked],
        },
    )
    out = Path(out_dir) / "reports" / "signoff" / micro.design_id
    out.mkdir(parents=True, exist_ok=True)
    (out / "signoff.json").write_text(
        json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    return result