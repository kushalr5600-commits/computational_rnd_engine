"""Phase 6 integration tests: fab-state persistence, EDA adapters, wiring.

Every test respects the honesty invariant: unavailable tools produce BLOCKED
receipts, never PASS; the FabMachine cannot reach FAB_READY without genuine
all-gate-PASS evidence.
"""

from __future__ import annotations

import json
import tempfile

import pytest

from rnd_engine.adapters import (
    RUN_TO_GATE,
    TOOL_MISSING,
    EvidenceCollector,
    ToolRegistry,
)
from rnd_engine.engine import InventionEngine
from rnd_engine.fab_ready import EvidenceReceipt, Fidelity, GateStatus
from rnd_engine.fab_state import (
    FabMachine,
    IllegalTransitionError,
)
from rnd_engine.flow import run_flow
from rnd_engine.models import Design
from rnd_engine.receipt import load_receipt, write_receipt


def _best_design(population: int = 3, generations: int = 1, seed: int = 42) -> Design:
    result = InventionEngine(
        population=population, generations=generations, seed=seed).run()
    design = result["best"]["design"]
    if isinstance(design, dict):
        design = Design(**design)
    return design


@pytest.fixture(scope="module")
def lint_receipt():
    """A real toolless flow receipt for the lint stage only."""
    with tempfile.TemporaryDirectory() as td:
        yield run_flow(_best_design(), stages=("lint",), out_dir=td)


class TestWriteReceiptFabState:
    """fab_state.json companion written by write_receipt."""

    def test_written_alongside_receipt(self, lint_receipt):
        with tempfile.TemporaryDirectory() as td:
            path = write_receipt(lint_receipt, td)
            assert path.name == "receipt.json"
            assert (path.parent / "fab_state.json").exists()

    def test_blocked_flow_stays_discovered(self, lint_receipt):
        with tempfile.TemporaryDirectory() as td:
            path = write_receipt(lint_receipt, td)
            fs = json.loads(path.with_name("fab_state.json").read_text())
            assert fs["candidate_id"] == lint_receipt.candidate_id
            assert fs["current_state"] == "DISCOVERED"
            assert fs["fab_ready"] is False
            assert fs["is_terminal"] is False
            assert "lint" in fs["blocked_stages"]

    def test_deterministic_digest(self, lint_receipt):
        digests = []
        for _ in range(2):
            with tempfile.TemporaryDirectory() as td:
                p = write_receipt(lint_receipt, td)
                digests.append(json.loads(
                    p.with_name("fab_state.json").read_text())["machine_digest"])
        assert digests[0] == digests[1]

    def test_roundtrip_receipt_unchanged(self, lint_receipt):
        with tempfile.TemporaryDirectory() as td:
            path = write_receipt(lint_receipt, td)
            loaded = load_receipt(path)
            assert loaded.receipt_hash() == lint_receipt.receipt_hash()


class TestToolRegistry:
    """Cheap honest discovery (MISSING/INSTALLED, never READY)."""

    def test_discover_all_configured_tools(self):
        reg = ToolRegistry.discover()
        assert reg.binaries, "expected configured tools to be discovered"
        assert reg.toolchain_hash
        assert reg.configuration_hash

    def test_missing_tools_reported_honestly(self):
        reg = ToolRegistry.discover()
        # Host has no EDA binaries; the registry must say so honestly.
        assert reg.status("verilator") == TOOL_MISSING
        assert reg.missing(("verilator", "yosys", "openroad")) == [
            "verilator", "yosys", "openroad"]

    def test_snapshot_deterministic(self):
        assert (ToolRegistry.discover().snapshot()
                == ToolRegistry.discover().snapshot())

    def test_all_installed_false_when_missing(self):
        reg = ToolRegistry.discover()
        assert reg.all_installed(("verilator",)) is False


class TestRunToGateMapping:
    """The fixed honest mapping from runner outcome to gate status."""

    def test_fixed_mapping(self):
        assert RUN_TO_GATE["PASSED"].value == "PASS"
        assert RUN_TO_GATE["FAILED"].value == "FAIL"
        assert RUN_TO_GATE["TIMEOUT"].value == "FAIL"
        assert RUN_TO_GATE["TOOL_NOT_FOUND"].value == "BLOCKED"


class TestEvidenceCollector:
    """ToolRun -> EvidenceReceipt conversion is honest and hash-bound."""

    def _collector(self) -> EvidenceCollector:
        return EvidenceCollector(ToolRegistry.discover())

    def test_blocked_receipt_for_missing_tool(self):
        rec = self._collector().blocked_receipt(
            stage="lint", candidate_id="c1", reason="verilator not found")
        assert rec.status.value == "BLOCKED"
        assert rec.stage == "lint"
        assert rec.failure_reason

    def test_receipt_from_run_not_found_is_blocked(self):
        from rnd_engine.edatools import ToolRun

        run = ToolRun(tool="verilator", status="TOOL_NOT_FOUND",
                      exit_code=None, duration_s=0.0)
        rec = self._collector().receipt_from_run(
            run, stage="lint", candidate_id="c1")
        assert rec.status.value == "BLOCKED"
        assert rec.failure_reason == "tool verilator TOOL_NOT_FOUND"

    def test_receipt_from_run_failed_is_fail(self):
        from rnd_engine.edatools import ToolRun

        run = ToolRun(tool="verilator", status="FAILED",
                      exit_code=1, duration_s=1.5)
        rec = self._collector().receipt_from_run(
            run, stage="lint", candidate_id="c1")
        assert rec.status.value == "FAIL"
        assert "exit 1" in rec.failure_reason

    def test_hashes_bind_receipt_to_artifact(self):
        from rnd_engine.edatools import ToolRun

        run = ToolRun(tool="yosys", status="PASSED",
                      exit_code=0, duration_s=2.0)
        rec = self._collector().receipt_from_run(
            run, stage="synthesis", candidate_id="c1",
            input_hashes={"rtl.v": "a" * 64},
            output_hashes={"netlist.v": "b" * 64},
            metrics={"cell_count": 42},
        )
        assert rec.status.value == "PASS"
        assert rec.input_hashes["rtl.v"] == "a" * 64
        assert rec.output_hashes["netlist.v"] == "b" * 64
        assert rec.metrics["cell_count"] == 42

    def test_toolchain_identity_from_registry(self):
        reg = ToolRegistry.discover()
        rec = self._collector().blocked_receipt(
            stage="drc", candidate_id="c1", reason="no magic")
        assert rec.toolchain_hash == reg.toolchain_hash
        assert rec.configuration_hash == reg.configuration_hash


class TestFabMachineGuards:
    """The state machine never fabricates and never moves backward."""

    def test_zero_receipts_refuse_fab_ready(self):
        machine = FabMachine("c1")
        ok, blocking = machine.declare_fab_ready([])
        assert ok is False
        assert blocking
        assert machine.current_state.value == "DISCOVERED"
        assert machine.is_terminal is False

    def test_surrogate_only_receipts_refuse_fab_ready(self):
        machine = FabMachine("c1")
        recs = [
            EvidenceReceipt(candidate_id="c1", stage=stage,
                            status=GateStatus.PASS, fidelity=Fidelity.SURROGATE)
            for stage in ("lint", "simulation", "synthesis")
        ]
        ok, _ = machine.declare_fab_ready(recs)
        assert ok is False
        assert machine.current_state.value == "DISCOVERED"

    def test_fail_is_terminal(self):
        machine = FabMachine("c1")
        state = machine.apply_stage("lint", "FAIL")
        assert state.value == "FAILED"
        assert machine.is_terminal

    def test_backward_transition_rejected(self):
        machine = FabMachine("c1")
        machine.apply_stage("lint", "PASS")
        with pytest.raises(IllegalTransitionError):
            machine.transition(machine.current_state, "lateral")

    def test_unknown_stage_rejected(self):
        machine = FabMachine("c1")
        with pytest.raises(IllegalTransitionError):
            machine.apply_stage("tofu", "PASS")