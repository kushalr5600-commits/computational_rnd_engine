"""Canonical data models for the Fab-Ready hardware generation system.

Unifies and extends the semantics previously spread across
rnd_engine/receipt.py and rnd_engine/fidelity/model.py into one authoritative
model set for the Fab-Ready Design Lifecycle.

All models are immutable, content-addressed (SHA-256), and deterministic.
No evidence is fabricated: status is always PASS/FAIL/BLOCKED/NOT_RUN.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Fidelity(str, Enum):
    """Evidence fidelity levels, weakest to strongest."""
    SURROGATE = "SURROGATE"
    RTL = "RTL"
    SIMULATION = "SIMULATION"
    FORMAL = "FORMAL"
    SYNTHESIS = "SYNTHESIS"
    PHYSICAL = "PHYSICAL"
    SIGNOFF = "SIGNOFF"
    SILICON = "SILICON"


FIDELITY_ORDER: tuple[Fidelity, ...] = (
    Fidelity.SURROGATE, Fidelity.RTL, Fidelity.SIMULATION, Fidelity.FORMAL,
    Fidelity.SYNTHESIS, Fidelity.PHYSICAL, Fidelity.SIGNOFF, Fidelity.SILICON,
)

_FIDELITY_REQUIREMENTS: dict[Fidelity, frozenset[Fidelity]] = {
    Fidelity.SURROGATE: frozenset(),
    Fidelity.RTL: frozenset({Fidelity.SURROGATE}),
    Fidelity.SIMULATION: frozenset({Fidelity.SURROGATE, Fidelity.RTL}),
    Fidelity.FORMAL: frozenset({Fidelity.SURROGATE, Fidelity.RTL, Fidelity.SIMULATION}),
    Fidelity.SYNTHESIS: frozenset({Fidelity.SURROGATE, Fidelity.RTL, Fidelity.SIMULATION, Fidelity.FORMAL}),
    Fidelity.PHYSICAL: frozenset({Fidelity.SURROGATE, Fidelity.RTL, Fidelity.SIMULATION, Fidelity.FORMAL, Fidelity.SYNTHESIS}),
    Fidelity.SIGNOFF: frozenset({Fidelity.SURROGATE, Fidelity.RTL, Fidelity.SIMULATION, Fidelity.FORMAL, Fidelity.SYNTHESIS, Fidelity.PHYSICAL}),
    Fidelity.SILICON: frozenset({Fidelity.SURROGATE, Fidelity.RTL, Fidelity.SIMULATION, Fidelity.FORMAL, Fidelity.SYNTHESIS, Fidelity.PHYSICAL, Fidelity.SIGNOFF}),
}


def fidelity_requires(fidelity: Fidelity) -> frozenset[Fidelity]:
    """Return the set of fidelity levels that must be satisfied."""
    return _FIDELITY_REQUIREMENTS.get(fidelity, frozenset())


class GateStatus(str, Enum):
    """Honest status vocabulary for every fabrication gate."""
    PASS = "PASS"
    FAIL = "FAIL"
    BLOCKED = "BLOCKED"
    NOT_RUN = "NOT_RUN"


class FabState(str, Enum):
    """Explicit lifecycle states for a candidate moving toward FAB_READY."""
    DISCOVERED = "DISCOVERED"
    ARCHITECTURE_DEFINED = "ARCHITECTURE_DEFINED"
    SPECIFIED = "SPECIFIED"
    MICROARCHITECTURE_DEFINED = "MICROARCHITECTURE_DEFINED"
    RTL_GENERATED = "RTL_GENERATED"
    RTL_LINTED = "RTL_LINTED"
    RTL_ELABORATED = "RTL_ELABORATED"
    RTL_SIMULATED = "RTL_SIMULATED"
    FORMALLY_VERIFIED = "FORMALLY_VERIFIED"
    SYNTHESIZED = "SYNTHESIZED"
    TIMING_VERIFIED = "TIMING_VERIFIED"
    POWER_ANALYZED = "POWER_ANALYZED"
    AREA_ANALYZED = "AREA_ANALYZED"
    PLACED = "PLACED"
    ROUTED = "ROUTED"
    DRC_VERIFIED = "DRC_VERIFIED"
    LVS_VERIFIED = "LVS_VERIFIED"
    SIGNOFF_VERIFIED = "SIGNOFF_VERIFIED"
    DOCUMENTED = "DOCUMENTED"
    RELEASE_PACKAGED = "RELEASE_PACKAGED"
    FAB_READY = "FAB_READY"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    NOT_RUN = "NOT_RUN"
    INVALID = "INVALID"


FAB_PROGRESSION: tuple[FabState, ...] = (
    FabState.DISCOVERED, FabState.ARCHITECTURE_DEFINED, FabState.SPECIFIED,
    FabState.MICROARCHITECTURE_DEFINED, FabState.RTL_GENERATED,
    FabState.RTL_LINTED, FabState.RTL_ELABORATED, FabState.RTL_SIMULATED,
    FabState.FORMALLY_VERIFIED, FabState.SYNTHESIZED, FabState.TIMING_VERIFIED,
    FabState.POWER_ANALYZED, FabState.AREA_ANALYZED, FabState.PLACED,
    FabState.ROUTED, FabState.DRC_VERIFIED, FabState.LVS_VERIFIED,
    FabState.SIGNOFF_VERIFIED, FabState.DOCUMENTED, FabState.RELEASE_PACKAGED,
    FabState.FAB_READY,
)


class ToolProvider(BaseModel):
    """Identity of a single tool invocation provider."""
    name: str
    version: str = "unknown"
    path: str = ""
    checksum: str = ""


class ToolchainFingerprint(BaseModel):
    """Stable identity of the complete resolved toolchain."""
    tools: dict[str, ToolProvider] = Field(default_factory=dict)
    environment: dict[str, str] = Field(default_factory=dict)

    def hash(self) -> str:
        from .reproducibility import stable_digest
        payload = {name: tp.model_dump() for name, tp in sorted(self.tools.items())}
        payload["environment"] = dict(sorted(self.environment.items()))
        return stable_digest(payload, length=32)


class EvidenceReceipt(BaseModel):
    """One canonical evidence record for one pipeline stage of one candidate."""
    evidence_id: str = ""
    candidate_id: str = ""
    stage: str = ""
    status: GateStatus = GateStatus.NOT_RUN
    fidelity: Fidelity = Fidelity.SURROGATE
    provider: str = ""
    tool: str = ""
    tool_version: str = "unknown"
    command: list[str] = Field(default_factory=list)
    inputs: list[str] = Field(default_factory=list)
    input_hashes: dict[str, str] = Field(default_factory=dict)
    outputs: list[str] = Field(default_factory=list)
    output_hashes: dict[str, str] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    environment_fingerprint: str = ""
    configuration_hash: str = ""
    toolchain_hash: str = ""
    timestamp: str = ""
    duration_s: float | None = None
    reproducibility_data: dict[str, Any] = Field(default_factory=dict)
    failure_reason: str = ""
    provenance: dict[str, Any] = Field(default_factory=dict)

    def content_hash(self) -> str:
        from .reproducibility import stable_digest
        return stable_digest(self.model_dump(mode="json"), length=32)


class KnowledgeType(str, Enum):
    """Types of knowledge items in the recursive knowledge substrate."""
    VERIFIED_SOLUTION = "verified_solution"
    VERIFIED_TRANSFORMATION = "verified_transformation"
    VERIFIED_PRIMITIVE = "verified_primitive"
    VERIFIED_FAILURE = "verified_failure"
    ARCHITECTURE_PATTERN = "architecture_pattern"
    HARDWARE_PATTERN = "hardware_pattern"
    TOOL_OUTCOME = "tool_outcome"
    EDA_CONSTRAINT = "eda_constraint"
    FAILURE_SIGNATURE = "failure_signature"
    SUCCESSFUL_LINEAGE = "successful_lineage"
    COUNTEREXAMPLE = "counterexample"
    RESOURCE_TRADEOFF = "resource_tradeoff"


class KnowledgeItem(BaseModel):
    """One item in the append-only recursive knowledge substrate."""
    knowledge_id: str = ""
    knowledge_type: KnowledgeType = KnowledgeType.VERIFIED_SOLUTION
    source_candidate: str = ""
    source_evidence: str = ""
    content: dict[str, Any] = Field(default_factory=dict)
    content_hash: str = ""
    fidelity: Fidelity = Fidelity.SURROGATE
    confidence: float = 0.0
    generation: int = 0
    parents: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)


class Primitive(BaseModel):
    """A verified computational primitive for reuse by future candidates."""
    primitive_id: str = ""
    name: str = ""
    definition: dict[str, Any] = Field(default_factory=dict)
    interface: dict[str, Any] = Field(default_factory=dict)
    constraints: dict[str, Any] = Field(default_factory=dict)
    known_uses: list[str] = Field(default_factory=list)
    verified_evidence: list[str] = Field(default_factory=list)
    performance_characteristics: dict[str, Any] = Field(default_factory=dict)
    hardware_characteristics: dict[str, Any] = Field(default_factory=dict)
    lineage: list[str] = Field(default_factory=list)
    content_hash: str = ""


class SearchPolicy(BaseModel):
    """Evolving search policy controlling exploration/exploitation."""
    policy_id: str = ""
    generation: int = 0
    exploration_rate: float = 0.3
    mutation_weights: dict[str, float] = Field(default_factory=dict)
    promotion_budget: dict[str, float] = Field(default_factory=dict)
    architecture_family_weights: dict[str, float] = Field(default_factory=dict)
    diversity_target: float = 0.5
    novelty_pressure: float = 0.3
    primitive_reuse: bool = True
    failure_guided: bool = True
    parents: list[str] = Field(default_factory=list)


class SearchSpaceState(BaseModel):
    """Evolving search space that adapts from accumulated knowledge."""
    space_id: str = ""
    generation: int = 0
    parameter_bounds: dict[str, tuple[float, float]] = Field(default_factory=dict)
    active_families: list[str] = Field(default_factory=lambda: ["generic"])
    banned_regions: list[dict[str, Any]] = Field(default_factory=list)
    recommended_regions: list[dict[str, Any]] = Field(default_factory=list)
    available_primitives: list[str] = Field(default_factory=list)
    family_skew: dict[str, float] = Field(default_factory=dict)
    parents: list[str] = Field(default_factory=list)


class LineageRecord(BaseModel):
    """Complete lineage of a candidate from discovery to final disposition."""
    candidate_id: str = ""
    parent_ids: list[str] = Field(default_factory=list)
    lineage_id: str = ""
    mutations: list[str] = Field(default_factory=list)
    transformations: list[str] = Field(default_factory=list)
    primitives_used: list[str] = Field(default_factory=list)
    knowledge_used: list[str] = Field(default_factory=list)
    search_policy_id: str = ""
    search_space_id: str = ""
    evidence: list[str] = Field(default_factory=list)
    promotion_decisions: list[dict[str, Any]] = Field(default_factory=list)
    failures: list[str] = Field(default_factory=list)
    final_disposition: str = ""
    generation: int = 0


class CandidateSnapshot(BaseModel):
    """Immutable snapshot for consistent evaluation."""
    candidate_id: str = ""
    parent_ids: list[str] = Field(default_factory=list)
    lineage_id: str = ""
    generation: int = 0
    random_seed: int = 42
    architecture_hash: str = ""
    microarchitecture_hash: str = ""
    proposed_files: list[str] = Field(default_factory=list)
    rtl_files: list[str] = Field(default_factory=list)
    configuration: dict[str, Any] = Field(default_factory=dict)
    knowledge_snapshot_id: str = ""
    search_policy_snapshot_id: str = ""
    objective_inputs: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)


class FabReadyRelease(BaseModel):
    """Complete fab-ready design package manifest."""
    release_id: str = ""
    candidate_id: str = ""
    design_name: str = ""
    isa: str = ""
    target_process: str = ""
    target_pdk: str = ""
    fab_state: FabState = FabState.DISCOVERED
    fidelity: Fidelity = Fidelity.SURROGATE
    architecture_summary: dict[str, Any] = Field(default_factory=dict)
    characteristics: dict[str, Any] = Field(default_factory=dict)
    rtl_modules: list[str] = Field(default_factory=list)
    verification_summary: dict[str, Any] = Field(default_factory=dict)
    synthesis_summary: dict[str, Any] = Field(default_factory=dict)
    timing_summary: dict[str, Any] = Field(default_factory=dict)
    power_summary: dict[str, Any] = Field(default_factory=dict)
    area_summary: dict[str, Any] = Field(default_factory=dict)
    physical_summary: dict[str, Any] = Field(default_factory=dict)
    drc_clean: bool | None = None
    lvs_clean: bool | None = None
    signoff_passed: bool | None = None
    toolchain_manifest: dict[str, Any] = Field(default_factory=dict)
    reproducibility_manifest: dict[str, Any] = Field(default_factory=dict)
    checksums: dict[str, str] = Field(default_factory=dict)
    lineage_id: str = ""
    known_limitations: list[str] = Field(default_factory=list)
    fabrication_assumptions: list[str] = Field(default_factory=list)
    staged_ran: list[str] = Field(default_factory=list)
    stages_not_run: list[str] = Field(default_factory=list)
    stages_blocked: list[str] = Field(default_factory=list)
    fab_ready: bool = False
    provenance: dict[str, Any] = Field(default_factory=dict)


def fab_ready_required_gates() -> list[str]:
    """Return the ordered list of gate stages required for FAB_READY."""
    return [
        "rtl_lint", "rtl_elaboration", "simulation", "formal",
        "synthesis", "timing", "power", "area",
        "placement", "routing", "drc", "lvs", "signoff",
    ]


def check_fab_ready(
    receipts: list[EvidenceReceipt],
) -> tuple[bool, list[str]]:
    """Determine FAB_READY status from evidence receipts.

    Returns (is_ready, list_of_blocking_stages).
    Honest: missing tool = BLOCKED = not ready.
    """
    status_map: dict[str, GateStatus] = {r.stage: r.status for r in receipts}
    blocking: list[str] = []
    for gate in fab_ready_required_gates():
        st = status_map.get(gate, GateStatus.NOT_RUN)
        if st != GateStatus.PASS:
            blocking.append(gate)
    return (not blocking, blocking)
