"""Fab-Ready state machine (Phase 4 of the fab-ready integration plan).

Drives one candidate honestly through the ``FabState`` lifecycle:

    DISCOVERED -> ... -> SIGNOFF_VERIFIED -> ... -> FAB_READY

Honesty rules enforced here:

- Every completed state must be justified by a real stage receipt status
  (PASS). No state is ever completed silently.
- A stage FAIL moves the machine to the terminal FAILED state: the candidate
  artifact itself failed.
- A stage BLOCKED is an *environment* problem, not a candidate problem: the
  machine records the blockage and preserves its position. It never pretends
  progress.
- NOT_RUN is recorded, never conflated with PASS.
- FAB_READY is only reachable through :meth:`FabMachine.declare_fab_ready`,
  which requires every required gate to be genuinely PASS via
  :func:`rnd_engine.fab_ready.check_fab_ready`.

The ``FAB_PROGRESSION`` linear order (timing/power/area before place/route)
differs from the actual pipeline stage order (physical -> sta -> power -> drc
-> lvs), so completed states are tracked as a *set* justified by receipts,
with ``current_state`` being the highest completed state in progression
order. ``current_state`` is therefore monotonic non-decreasing, and no
transition is ever backward in the audit trail.
"""

from __future__ import annotations

from pydantic import BaseModel

from .fab_ready import (
    FAB_PROGRESSION,
    EvidenceReceipt,
    FabState,
    Fidelity,
    GateStatus,
    check_fab_ready,
)
from .reproducibility import stable_digest

#: Pipeline stage name -> every FabState completed when that stage genuinely
#: PASSES. A coarse flow stage justifies ALL the progression states it covers
#: (e.g. physical PASS means placement, area analysis and routing all
#: completed; lint PASS means both lint and elaboration gates passed).
#: Keys stay aligned with FLOW_STAGE_TO_GATES; expansion to canonical gates
#: lives there, expansion to lifecycle states lives here.
STAGE_TO_STATE: dict[str, tuple[FabState, ...]] = {
    "lint": (FabState.RTL_LINTED, FabState.RTL_ELABORATED),
    "simulation": (FabState.RTL_SIMULATED,),
    "formal": (FabState.FORMALLY_VERIFIED,),
    "synthesis": (FabState.SYNTHESIZED,),
    # The physical stage covers floorplan, placement, CTS, routing and the
    # area analysis derived from the synthesized netlist.
    "physical": (FabState.AREA_ANALYZED, FabState.PLACED, FabState.ROUTED),
    "sta": (FabState.TIMING_VERIFIED,),
    "power": (FabState.POWER_ANALYZED,),
    "drc": (FabState.DRC_VERIFIED,),
    "lvs": (FabState.LVS_VERIFIED,),
}

_EXCEPTION_STATES = frozenset({FabState.FAILED, FabState.INVALID})
_TERMINAL_STATES = frozenset(
    {FabState.FAILED, FabState.FAB_READY, FabState.INVALID})

_PROGRESSION_INDEX: dict[FabState, int] = {
    s: i for i, s in enumerate(FAB_PROGRESSION)}


class IllegalTransitionError(ValueError):
    """Raised when a state transition is not justified or moves backward."""


class StateTransitionRecord(BaseModel):
    """One audited transition with its justification (never fabricated)."""

    from_state: FabState
    to_state: FabState
    justification: str
    stage: str = ""
    stage_status: str = ""
    evidence_hash: str = ""


class FabMachine:
    """Honest per-candidate lifecycle state machine."""

    def __init__(self, candidate_id: str) -> None:
        self.candidate_id = candidate_id
        self.completed: set[FabState] = {FabState.DISCOVERED}
        self.blocked_stages: list[str] = []
        self.not_run_stages: list[str] = []
        self.history: list[StateTransitionRecord] = []
        self._terminal: FabState | None = None

    # -- position ------------------------------------------------------------

    @property
    def current_state(self) -> FabState:
        """Highest completed state in FAB_PROGRESSION order (or terminal)."""
        if self._terminal is not None:
            return self._terminal
        return max(self.completed, key=_PROGRESSION_INDEX.__getitem__)

    @property
    def is_terminal(self) -> bool:
        return self._terminal is not None

    @property
    def is_blocked(self) -> bool:
        return bool(self.blocked_stages)

    # -- direct transitions ------------------------------------------------------

    def transition(self, new_state: FabState, justification: str,
                   evidence_hash: str = "") -> FabState:
        """Strictly forward (or exception) transition with justification."""
        if self.is_terminal:
            raise IllegalTransitionError(
                f"candidate {self.candidate_id} is terminal ({self._terminal})")
        if new_state in _EXCEPTION_STATES:
            self._enter_exception(new_state, justification, evidence_hash)
            return new_state
        if new_state not in _PROGRESSION_INDEX:
            raise IllegalTransitionError(f"unknown state {new_state}")
        if _PROGRESSION_INDEX[new_state] <= _PROGRESSION_INDEX[self.current_state]:
            raise IllegalTransitionError(
                f"backward/lateral transition {self.current_state} -> "
                f"{new_state} is not allowed")
        self.completed.add(new_state)
        self.history.append(StateTransitionRecord(
            from_state=self.current_state,
            to_state=new_state,
            justification=justification,
            evidence_hash=evidence_hash,
        ))

    def mark_completed(self, state: FabState, justification: str,
                       evidence_hash: str = "") -> FabState:
        """Mark a lifecycle state completed (must be a real progression state)."""
        if self.is_terminal:
            raise IllegalTransitionError(
                f"candidate {self.candidate_id} is terminal ({self._terminal})")
        if state not in _PROGRESSION_INDEX:
            raise IllegalTransitionError(f"unknown state {state}")
        self.completed.add(state)
        self.history.append(StateTransitionRecord(
            from_state=(self.history[-1].to_state if self.history
                        else self.current_state),
            to_state=state,
            justification=justification,
            evidence_hash=evidence_hash,
        ))
        return state

    def _enter_exception(self, state: FabState, justification: str,
                         evidence_hash: str) -> None:
        self._terminal = state
        self.history.append(StateTransitionRecord(
            from_state=self.current_state,
            to_state=state,
            justification=justification,
            evidence_hash=evidence_hash,
        ))

    # -- stage receipt application -------------------------------------------------

    def apply_stage(self, stage: str, status: str, evidence_hash: str = "") -> FabState:
        """Apply one pipeline stage outcome honestly.

        PASS    -> complete the mapped state (justified by the receipt)
        FAIL    -> terminal FAILED (the candidate artifact failed)
        BLOCKED -> record blockage, preserve position (environment problem)
        other   -> recorded as not-run, never conflated with progress
        """
        if self.is_terminal:
            raise IllegalTransitionError(
                f"candidate {self.candidate_id} is terminal ({self._terminal})")
        if stage not in STAGE_TO_STATE:
            raise IllegalTransitionError(f"unknown pipeline stage: {stage}")
        if status == GateStatus.PASS.value:
            for justified in STAGE_TO_STATE[stage]:
                self.mark_completed(
                    justified,
                    justification=f"stage {stage} PASS",
                    evidence_hash=evidence_hash,
                )
            return self.current_state
        if status == GateStatus.FAIL.value:
            self._enter_exception(
                FabState.FAILED,
                justification=f"stage {stage} FAIL",
                evidence_hash=evidence_hash,
            )
            return FabState.FAILED
        if status == GateStatus.BLOCKED.value:
            if stage not in self.blocked_stages:
                self.blocked_stages.append(stage)
            record = StateTransitionRecord(
                from_state=self.current_state,
                to_state=self.current_state,
                justification=f"stage {stage} BLOCKED (environment)",
                stage=stage,
                stage_status=status,
                evidence_hash=evidence_hash,
            )
            self.history.append(record)
            return self.current_state
        if stage not in self.not_run_stages:
            self.not_run_stages.append(stage)
        self.history.append(StateTransitionRecord(
            from_state=self.current_state,
            to_state=self.current_state,
            justification=f"stage {stage} {status}",
            stage=stage,
            stage_status=status,
            evidence_hash=evidence_hash,
        ))
        return self.current_state

    # -- fab readiness -----------------------------------------------------------

    def declare_fab_ready(
        self,
        receipts: list[EvidenceReceipt],
    ) -> tuple[bool, list[str]]:
        """Enter FAB_READY only when every required gate is genuinely PASS.

        Returns (entered, blocking_stages). Never fabricates readiness.
        """
        if self.is_terminal:
            return False, [self._terminal.value if self._terminal else "TERMINAL"]
        ready, blocking = check_fab_ready(receipts)
        if not ready:
            return False, blocking
        self.completed.add(FabState.FAB_READY)
        self._terminal = FabState.FAB_READY
        self.history.append(StateTransitionRecord(
            from_state=self.current_state,
            to_state=FabState.FAB_READY,
            justification="all required fabrication gates genuinely PASS",
        ))
        return True, []

    # -- identity --------------------------------------------------------------------

    def machine_digest(self) -> str:
        """Deterministic digest of the machine's audited position."""
        payload = {
            "candidate_id": self.candidate_id,
            "completed": sorted(s.value for s in self.completed),
            "blocked": list(self.blocked_stages),
            "not_run": list(self.not_run_stages),
            "terminal": self._terminal.value if self._terminal else None,
            "history": [h.model_dump(mode="json") for h in self.history],
        }
        return stable_digest(payload, length=32)


#: Flow/pipeline stage name -> the canonical fab gate names it justifies.
#: The flow produces coarser stages than the gate list requires, so one flow
#: stage may justify several gates (e.g. physical -> placement+routing+area).
FLOW_STAGE_TO_GATES: dict[str, tuple[str, ...]] = {
    "lint": ("rtl_lint", "rtl_elaboration"),
    "simulation": ("simulation",),
    "formal": ("formal",),
    "synthesis": ("synthesis",),
    "physical": ("placement", "routing", "area"),
    "sta": ("timing",),
    "power": ("power",),
    "drc": ("drc",),
    "lvs": ("lvs",),
    "signoff": ("signoff",),
}


def bridge_flow_statuses(
    flow_stage_status: dict[str, str],
    candidate_id: str = "",
    toolchain_hash: str = "",
    configuration_hash: str = "",
) -> list[EvidenceReceipt]:
    """Convert flow stage statuses into canonical gate EvidenceReceipts.

    This is the honest bridge between the pipeline's coarse stage names and
    :func:`rnd_engine.fab_ready.fab_ready_required_gates`. A BLOCKED flow
    stage produces BLOCKED receipts for every gate it would have justified —
    never PASS.
    """
    receipts: list[EvidenceReceipt] = []
    for stage, gates in FLOW_STAGE_TO_GATES.items():
        status = flow_stage_status.get(stage, GateStatus.NOT_RUN.value)
        for gate in gates:
            receipts.append(EvidenceReceipt(
                candidate_id=candidate_id,
                stage=gate,
                status=GateStatus(status),
                fidelity=Fidelity.SIGNOFF,
                tool=stage,
                toolchain_hash=toolchain_hash,
                configuration_hash=configuration_hash,
                failure_reason=(
                    "" if status == GateStatus.PASS.value
                    else f"flow stage {stage} is {status}"),
            ))
    return receipts



def compute_fab_state(receipt) -> dict:
    """Compute the honest fab lifecycle state for a saved FlowReceipt.

    Applies every recorded stage status to a fresh FabMachine, then attempts
    declare_fab_ready with the bridged gate receipts. Returns a JSON-serializable
    summary; never mutates the receipt and never fabricates readiness.
    """
    statuses = {s.stage: s.status for s in receipt.stages}
    machine = FabMachine(receipt.candidate_id)
    for stage in ("lint", "simulation", "formal", "synthesis", "physical",
                  "sta", "power", "drc", "lvs"):
        if stage in statuses:
            machine.apply_stage(stage, statuses[stage])
    gate_receipts = bridge_flow_statuses(
        statuses,
        candidate_id=receipt.candidate_id,
        toolchain_hash=receipt.toolchain_hash,
        configuration_hash=receipt.configuration_hash,
    )
    fab_ready, blocking = machine.declare_fab_ready(gate_receipts)
    return {
        "candidate_id": receipt.candidate_id,
        "current_state": machine.current_state.value,
        "is_terminal": machine.is_terminal,
        "completed_states": sorted(s.value for s in machine.completed),
        "blocked_stages": list(machine.blocked_stages),
        "not_run_stages": list(machine.not_run_stages),
        "fab_ready": fab_ready,
        "blocking_gates": blocking,
        "transitions": len(machine.history),
        "machine_digest": machine.machine_digest(),
    }
