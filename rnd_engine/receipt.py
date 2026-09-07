"""Immutable evidence receipts (§17-§18 of the bootstrapping plan).

Every evaluation of a candidate against real (or blocked) hardware stages is
persisted as an immutable receipt that binds the candidate's identity AND the
toolchain/PDK/configuration identities to the stage outcomes:

- candidate_id / experiment_id / generation_id / parent_candidate_id /
  parent_artifact_hash identify *which* artifact is being evaluated
- architecture_hash / microarchitecture_hash / rtl_hash / testbench_hash /
  property_hash / netlist_hash / def_hash / gds_hash identify *what* content
  was evaluated
- configuration_hash / toolchain_hash / pdk_hash identify *under what* it was
  evaluated — if any of these changes, the evaluation is a different
  experiment, never silently equivalent (§22)

A stage status is one of PASS / FAIL / BLOCKED / NOT_RUN / PENDING and is
always derived from an actual tool run (or an honest refusal to run). The
receipt never fabricates PASS.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .reproducibility import stable_digest

# Evidence levels, lowest to highest (monotonic promotion, §19).
EVIDENCE_SURROGATE = "SURROGATE"
EVIDENCE_RTL = "RTL"
EVIDENCE_SIMULATION = "SIMULATION"
EVIDENCE_FORMAL = "FORMAL"
EVIDENCE_SYNTHESIS = "SYNTHESIS"
EVIDENCE_PHYSICAL = "PHYSICAL"
EVIDENCE_SIGNOFF = "SIGNOFF"
EVIDENCE_SILICON = "SILICON"

EVIDENCE_LADDER: tuple[str, ...] = (
    EVIDENCE_SURROGATE,
    EVIDENCE_RTL,
    EVIDENCE_SIMULATION,
    EVIDENCE_FORMAL,
    EVIDENCE_SYNTHESIS,
    EVIDENCE_PHYSICAL,
    EVIDENCE_SIGNOFF,
    EVIDENCE_SILICON,
)

STAGE_PASS = "PASS"
STAGE_FAIL = "FAIL"
STAGE_BLOCKED = "BLOCKED"
STAGE_NOT_RUN = "NOT_RUN"
STAGE_PENDING = "PENDING"

RECEIPT_SCHEMA_VERSION = 1


class ToolRunReceipt(BaseModel):
    """One external-tool invocation, captured without loss (§24)."""

    tool: str
    command: list[str] = Field(default_factory=list)
    status: str = "TOOL_NOT_FOUND"
    exit_code: int | None = None
    stdout_tail: str = ""
    stderr_tail: str = ""
    tool_version: str | None = None
    duration_s: float | None = None
    error_code: str | None = None
    workdir: str | None = None
    env_keys: list[str] = Field(default_factory=list)

    @classmethod
    def from_run(cls, run: Any) -> ToolRunReceipt:
        return cls(
            tool=run.tool,
            command=list(run.command),
            status=run.status,
            exit_code=run.exit_code,
            stdout_tail=(run.stdout or "")[-2000:],
            stderr_tail=(run.stderr or "")[-2000:],
            tool_version=run.tool_version,
            duration_s=run.duration_s,
            error_code=run.error_code,
            workdir=run.workdir,
            env_keys=list(run.env_keys),
        )


class StageReceipt(BaseModel):
    """One pipeline stage of one candidate evaluation."""

    stage: str                      # lint / simulation / formal / synthesis /
                                    # physical / sta / power / drc / lvs
    status: str = STAGE_NOT_RUN     # PASS / FAIL / BLOCKED / NOT_RUN / PENDING
    tool_run: ToolRunReceipt | None = None
    error_code: str | None = None
    message: str = ""
    artifact_hash: str | None = None          # stage artifact hash (if any)
    metric_keys: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)  # only real tool output
class FlowReceipt(BaseModel):
    """Canonical evidence receipt for one candidate evaluation (§18)."""

    receipt_schema_version: int = RECEIPT_SCHEMA_VERSION
    candidate_id: str
    experiment_id: str = ""
    generation_id: int = 0
    parent_candidate_id: str = ""
    parent_artifact_hash: str = ""

    architecture_hash: str = ""
    microarchitecture_hash: str = ""
    rtl_hash: str = ""
    testbench_hash: str = ""
    property_hash: str = ""
    netlist_hash: str = ""
    def_hash: str = ""
    gds_hash: str = ""

    configuration_hash: str
    toolchain_hash: str = ""
    pdk_hash: str = ""

    stages: list[StageReceipt] = Field(default_factory=list)
    evidence_level: str = EVIDENCE_SURROGATE
    signoff_tapeout_ready: bool = False
    provenance: dict[str, Any] = Field(default_factory=dict)

    def stage(self, name: str) -> StageReceipt | None:
        return next((s for s in self.stages if s.stage == name), None)

    def stage_status(self, name: str) -> str | None:
        stage = self.stage(name)
        return stage.status if stage else None

    def receipt_hash(self) -> str:
        payload = self.model_dump(mode="json")
        payload.pop("signoff_tapeout_ready", None)
        return stable_digest(payload, length=32)


def evidence_from_stages(stages: list[StageReceipt]) -> str:
    """Derive the honest evidence level from actual stage statuses (§19).

    Monotonic ladder: SURROGATE -> RTL(lint passes) -> SIMULATION -> FORMAL ->
    SYNTHESIS -> PHYSICAL -> SIGNOFF. A stage only elevates the level when it
    AND every lower stage actually PASSED; a BLOCKED stage caps the level at
    the highest rung genuinely PASSED below it, so a surrogate-scoring
    candidate can never claim a hardware rung.
    """
    passed = {s.stage for s in stages if s.status == STAGE_PASS}

    def lower_passed(level: str) -> bool:
        required = _LEVEL_STAGES[level]
        return required <= passed

    for level in reversed(EVIDENCE_LADDER):
        if level == EVIDENCE_SURROGATE:
            return EVIDENCE_SURROGATE
        if level == EVIDENCE_SILICON:
            continue  # only real silicon measurements can set this
        if lower_passed(level):
            return level
    return EVIDENCE_SURROGATE


#: Stage requirements per evidence rung (monotonic, cumulative).
_LEVEL_STAGES: dict[str, frozenset[str]] = {
    EVIDENCE_RTL: frozenset({"lint"}),
    EVIDENCE_SIMULATION: frozenset({"lint", "simulation"}),
    EVIDENCE_FORMAL: frozenset({"lint", "simulation", "formal"}),
    EVIDENCE_SYNTHESIS: frozenset({"lint", "simulation", "formal", "synthesis"}),
    EVIDENCE_PHYSICAL: frozenset({"lint", "simulation", "formal", "synthesis", "physical"}),
    EVIDENCE_SIGNOFF: frozenset({"lint", "simulation", "formal", "synthesis",
                                 "physical", "sta", "power", "drc", "lvs"}),
}


def signoff_ready_from_stages(stages: list[StageReceipt]) -> bool:
    """True only when every hardware gate is genuinely PASS (§27)."""
    required = {"lint", "simulation", "formal", "synthesis", "physical",
                "sta", "power", "drc", "lvs"}
    missing = required - {s.stage for s in stages}
    if missing:
        return False
    return all(s.status == STAGE_PASS for s in stages if s.stage in required)


def write_receipt(receipt: FlowReceipt, out_dir: str | Path) -> Path:
    """Persist the receipt immutably under ``out_dir/receipts/<candidate_id>/``."""
    import json

    target_dir = Path(out_dir) / "receipts" / receipt.candidate_id
    target_dir.mkdir(parents=True, exist_ok=True)
    path = target_dir / "receipt.json"
    payload = receipt.model_dump(mode="json")
    payload["receipt_hash"] = receipt.receipt_hash()
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    # Companion fab-state lifecycle position (Phase 6). Computed from this
    # receipt only; a BLOCKED stage never advances the machine.
    from .fab_state import compute_fab_state

    fab_state = compute_fab_state(receipt)
    (target_dir / "fab_state.json").write_text(
        json.dumps(fab_state, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def load_receipt(path: str | Path) -> FlowReceipt:
    """Load a persisted receipt, ignoring the stored self-hash field."""
    import json

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    payload.pop("receipt_hash", None)
    return FlowReceipt(**payload)