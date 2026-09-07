"""Tests for the fab-ready state machine (Phase 4).

These tests verify the honesty invariants of the lifecycle:

- BLOCKED never advances the machine (environment problem, preserved position)
- PASS advances only the state justified by the receipt
- FAIL terminates the candidate (artifact failure)
- FAB_READY is refused unless every required gate is genuinely PASS
- No transition is ever backward; terminal states are final
"""

from __future__ import annotations

import pytest

from rnd_engine.fab_ready import (
    FAB_PROGRESSION,
    FabState,
    GateStatus,
    fab_ready_required_gates,
)
from rnd_engine.fab_state import (
    FLOW_STAGE_TO_GATES,
    STAGE_TO_STATE,
    FabMachine,
    IllegalTransitionError,
    bridge_flow_statuses,
)

ALL_FLOW_STAGES = [
    "lint", "simulation", "formal", "synthesis",
    "physical", "sta", "power", "drc", "lvs",
]


def _blocked_statuses() -> dict[str, str]:
    return {s: GateStatus.BLOCKED.value for s in ALL_FLOW_STAGES}


def _passed_statuses() -> dict[str, str]:
    return {s: GateStatus.PASS.value for s in ALL_FLOW_STAGES}


class TestStageMapping:
    def test_nine_pipeline_stages_mapped(self) -> None:
        assert set(STAGE_TO_STATE) == set(ALL_FLOW_STAGES)

    def test_flow_to_gate_bridge_covers_all_required_gates(self) -> None:
        from rnd_engine.fab_ready import fab_ready_required_gates

        justified: set[str] = set()
        for gates in FLOW_STAGE_TO_GATES.values():
            justified.update(gates)
        assert justified == set(fab_ready_required_gates())

    def test_physical_stage_justifies_three_gates(self) -> None:
        assert set(FLOW_STAGE_TO_GATES["physical"]) == {"placement", "routing", "area"}

    def test_lint_stage_justifies_lint_and_elaboration(self) -> None:
        assert set(FLOW_STAGE_TO_GATES["lint"]) == {"rtl_lint", "rtl_elaboration"}


class TestBridgeReceipts:
    def test_blocked_stage_produces_blocked_receipts_never_pass(self) -> None:
        receipts = bridge_flow_statuses({"physical": GateStatus.BLOCKED.value})
        phys = [r for r in receipts if r.stage in {"placement", "routing", "area"}]
        assert len(phys) == 3
        assert all(r.status == GateStatus.BLOCKED for r in phys)

    def test_missing_stage_defaults_to_not_run(self) -> None:
        receipts = bridge_flow_statuses({"lint": GateStatus.PASS.value})
        by_stage = {r.stage: r for r in receipts}
        assert by_stage["rtl_lint"].status == GateStatus.PASS
        assert by_stage["rtl_elaboration"].status == GateStatus.PASS
        assert by_stage["simulation"].status == GateStatus.NOT_RUN

    def test_bridge_covers_all_ten_flow_stages(self) -> None:
        # 9 flow stages given; the signoff gate has no flow stage yet, so it
        # defaults honestly to NOT_RUN while the other 12 gates are BLOCKED.
        receipts = bridge_flow_statuses(_blocked_statuses())
        assert len(receipts) == 13  # 2+1+1+1+3+1+1+1+1+1
        assert sum(1 for r in receipts if r.status == GateStatus.BLOCKED) == 12
        signoff = next(r for r in receipts if r.stage == "signoff")
        assert signoff.status == GateStatus.NOT_RUN

    def test_bridge_deterministic(self) -> None:
        h1 = [r.content_hash() for r in bridge_flow_statuses(_blocked_statuses())]
        h2 = [r.content_hash() for r in bridge_flow_statuses(_blocked_statuses())]
        assert h1 == h2

    def test_failure_reason_records_flow_stage(self) -> None:
        receipts = bridge_flow_statuses({"sta": GateStatus.FAIL.value})
        timing = next(r for r in receipts if r.stage == "timing")
        assert timing.status == GateStatus.FAIL
        assert "sta" in timing.failure_reason


class TestBlockedPreservesPosition:
    def test_toolless_flow_stays_discovered(self) -> None:
        m = FabMachine("c1")
        for stage, status in _blocked_statuses().items():
            m.apply_stage(stage, status)
        assert m.current_state == FabState.DISCOVERED
        assert sorted(m.blocked_stages) == sorted(ALL_FLOW_STAGES)
        assert m.not_run_stages == []

    def test_blocked_stage_then_pass_advances(self) -> None:
        m = FabMachine("c2")
        assert m.apply_stage("lint", GateStatus.BLOCKED.value) == FabState.DISCOVERED
        assert m.apply_stage(
            "lint", GateStatus.PASS.value) == FabState.RTL_ELABORATED
        # Blockage is remembered for the audit trail even after recovery.
        assert m.blocked_stages == ["lint"]

    def test_blocked_is_not_terminal(self) -> None:
        m = FabMachine("c3")
        m.apply_stage("lint", GateStatus.BLOCKED.value)
        assert not m.is_terminal
        assert m.is_blocked

    def test_machine_digest_deterministic_and_position_sensitive(self) -> None:
        def build() -> str:
            m = FabMachine("c4")
            m.apply_stage("lint", GateStatus.BLOCKED.value)
            m.apply_stage("lint", GateStatus.PASS.value)
            return m.machine_digest()

        assert build() == build()

        m_other = FabMachine("c4")
        m_other.apply_stage("lint", GateStatus.PASS.value)
        assert m_other.machine_digest() != build()


class TestPassAdvances:
    def test_full_pass_flow_reaches_lvs_verified(self) -> None:
        m = FabMachine("c5")
        for stage in ALL_FLOW_STAGES:
            m.apply_stage(stage, GateStatus.PASS.value)
        assert m.current_state == FabState.LVS_VERIFIED
        assert not m.is_blocked

    def test_partial_pass_tracks_highest_state(self) -> None:
        m = FabMachine("c6")
        m.apply_stage("lint", GateStatus.PASS.value)
        m.apply_stage("simulation", GateStatus.PASS.value)
        assert m.current_state == FabState.RTL_SIMULATED

    def test_out_of_order_pass_still_records(self) -> None:
        m = FabMachine("c7")
        m.apply_stage("synthesis", GateStatus.PASS.value)
        assert m.current_state == FabState.SYNTHESIZED
        m.apply_stage("lint", GateStatus.PASS.value)
        assert FabState.RTL_LINTED in m.completed

        h1 = [r.content_hash() for r in bridge_flow_statuses(_blocked_statuses())]
        h2 = [r.content_hash() for r in bridge_flow_statuses(_blocked_statuses())]
        assert h1 == h2

    def test_failure_reason_records_flow_stage(self) -> None:
        receipts = bridge_flow_statuses({"sta": GateStatus.FAIL.value})
        timing = next(r for r in receipts if r.stage == "timing")
        assert timing.status == GateStatus.FAIL
        assert "sta" in timing.failure_reason


class TestFailTerminates:
    def test_fail_is_terminal(self) -> None:
        m = FabMachine("c8")
        m.apply_stage("lint", GateStatus.PASS.value)
        assert m.apply_stage("simulation", GateStatus.FAIL.value) == FabState.FAILED
        assert m.is_terminal
        assert m.current_state == FabState.FAILED

    def test_no_transition_after_fail(self) -> None:
        m = FabMachine("c9")
        m.apply_stage("lint", GateStatus.FAIL.value)
        with pytest.raises(IllegalTransitionError):
            m.apply_stage("simulation", GateStatus.PASS.value)

    def test_fail_after_progress_records_history(self) -> None:
        m = FabMachine("c10")
        m.apply_stage("lint", GateStatus.PASS.value)
        m.apply_stage("synthesis", GateStatus.FAIL.value)
        justifications = [h.justification for h in m.history]
        assert "stage lint PASS" in justifications
        assert "stage synthesis FAIL" in justifications


class TestTransitionRules:
    def test_backward_transition_rejected(self) -> None:
        m = FabMachine("c11")
        m.apply_stage("lint", GateStatus.PASS.value)
        with pytest.raises(IllegalTransitionError):
            m.transition(FabState.DISCOVERED, "regress")

    def test_lateral_transition_rejected(self) -> None:
        m = FabMachine("c12")
        m.apply_stage("lint", GateStatus.PASS.value)
        with pytest.raises(IllegalTransitionError):
            m.transition(FabState.RTL_LINTED, "same state")

    def test_unknown_state_rejected(self) -> None:
        m = FabMachine("c13")
        with pytest.raises(IllegalTransitionError):
            m.transition("NOT_A_STATE", "bogus")  # type: ignore[arg-type]

    def test_unknown_stage_rejected(self) -> None:
        m = FabMachine("c14")
        with pytest.raises(IllegalTransitionError):
            m.apply_stage("not_a_stage", GateStatus.PASS.value)

    def test_invalid_is_terminal_exception_state(self) -> None:
        m = FabMachine("c15")
        result = m.transition(FabState.INVALID, "artifact corrupt")
        assert result == FabState.INVALID
        assert m.is_terminal


class TestFabReadyGate:
    def test_toolless_flow_refuses_fab_ready(self) -> None:
        m = FabMachine("c16")
        for stage, status in _blocked_statuses().items():
            m.apply_stage(stage, status)
        ok, blocking = m.declare_fab_ready(
            bridge_flow_statuses(_blocked_statuses(), candidate_id="c16"))
        assert ok is False
        assert len(blocking) == 13
        assert not m.is_terminal  # environment problem: position preserved

    def test_all_pass_but_signoff_missing_refuses(self) -> None:
        m = FabMachine("c17")
        for stage in ALL_FLOW_STAGES:
            m.apply_stage(stage, GateStatus.PASS.value)
        ok, blocking = m.declare_fab_ready(
            bridge_flow_statuses(_passed_statuses(), candidate_id="c17"))
        assert ok is False
        assert blocking == ["signoff"]
        assert m.current_state == FabState.LVS_VERIFIED

    def test_full_pass_with_signoff_grants_fab_ready(self) -> None:
        m = FabMachine("c18")
        statuses = _passed_statuses()
        statuses["signoff"] = GateStatus.PASS.value
        for stage in ALL_FLOW_STAGES:
            m.apply_stage(stage, GateStatus.PASS.value)
        ok, blocking = m.declare_fab_ready(
            bridge_flow_statuses(statuses, candidate_id="c18"))
        assert ok is True
        assert blocking == []
        assert m.current_state == FabState.FAB_READY
        assert m.is_terminal

    def test_fab_ready_requires_genuine_pass_not_high_score(self) -> None:
        # A candidate with a perfect surrogate score but no real evidence
        # must never reach FAB_READY.
        m = FabMachine("c19")
        ok, _ = m.declare_fab_ready([])  # no receipts at all
        assert ok is False
        assert m.current_state == FabState.DISCOVERED

    def test_fab_ready_after_fail_refused(self) -> None:
        m = FabMachine("c20")
        m.apply_stage("lint", GateStatus.FAIL.value)
        ok, blocking = m.declare_fab_ready(
            bridge_flow_statuses(_passed_statuses(), candidate_id="c20"))
        assert ok is False
        assert blocking == [FabState.FAILED.value]


class TestGateStageStateEnumeration:
    """Property tests: fabrication gates vs flow stages vs lifecycle states.

    The 9-vs-10-vs-13 reconciliation: run_flow executes 9 pipeline stages;
    FLOW_STAGE_TO_GATES has 10 entries (the 9 + signoff, whose evidence comes
    from the separate signoff() run); those expand to exactly the 13 canonical
    fabrication gates required by check_fab_ready.
    """

    def test_flow_stage_to_gates_covers_required_gates_exactly_once(self):
        required = set(fab_ready_required_gates())
        covered: list[str] = []
        for gates in FLOW_STAGE_TO_GATES.values():
            covered.extend(gates)
        assert set(covered) == required
        assert len(covered) == len(required)  # no gate justified twice

    def test_gate_count_is_thirteen_and_stage_count_is_ten(self):
        assert len(fab_ready_required_gates()) == 13
        assert len(FLOW_STAGE_TO_GATES) == 10  # 9 flow stages + signoff
        assert "signoff" in FLOW_STAGE_TO_GATES

    def test_stage_to_state_keys_align_with_flow_stage_to_gates(self):
        assert set(STAGE_TO_STATE) == set(FLOW_STAGE_TO_GATES) - {"signoff"}

    def test_stage_to_state_values_are_progression_states_in_order(self):
        index = {s: i for i, s in enumerate(FAB_PROGRESSION)}
        for states in STAGE_TO_STATE.values():
            indexes = [index[s] for s in states]
            assert indexes == sorted(indexes)

    def test_lint_pass_completes_lint_and_elaboration(self):
        m = FabMachine("c-lint")
        m.apply_stage("lint", "PASS")
        assert FabState.RTL_LINTED in m.completed
        assert FabState.RTL_ELABORATED in m.completed
        assert m.current_state == FabState.RTL_ELABORATED

    def test_physical_pass_completes_area_placed_routed(self):
        m = FabMachine("c-phys")
        m.apply_stage("physical", "PASS")
        assert FabState.AREA_ANALYZED in m.completed
        assert FabState.PLACED in m.completed
        assert FabState.ROUTED in m.completed
        assert m.current_state == FabState.ROUTED

    def test_completed_never_skips_within_justified_block(self):
        # After all 9 flow stages PASS, every hardware state between
        # RTL_LINTED and LVS_VERIFIED must be completed (no holes).
        m = FabMachine("c-full")
        for stage in STAGE_TO_STATE:
            m.apply_stage(stage, "PASS")
        hardware = [s for s in FAB_PROGRESSION if
                    FAB_PROGRESSION.index(FabState.RTL_LINTED)
                    <= FAB_PROGRESSION.index(s)
                    <= FAB_PROGRESSION.index(FabState.LVS_VERIFIED)]
        assert all(s in m.completed for s in hardware)
        assert m.current_state == FabState.LVS_VERIFIED
