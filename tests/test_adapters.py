"""Tests for the EDA adapter architecture (Phase 5).

Uses a fake ToolRun (no real EDA tools exist on this host) and stubbed
registry data to test honest status mapping, receipt binding, and BLOCKED
preflight. No hardware evidence is fabricated: fake runs are explicitly
used to test the *mapping*, not to claim real tool outcomes.
"""

from __future__ import annotations

import pytest

from rnd_engine.adapters import (
    RUN_TO_GATE,
    TOOL_INSTALLED,
    TOOL_MISSING,
    EvidenceCollector,
    StageAdapter,
    ToolRegistry,
)
from rnd_engine.edatools import (
    RUN_FAILED,
    RUN_NOT_FOUND,
    RUN_PASSED,
    RUN_TIMEOUT,
    ToolRun,
)
from rnd_engine.fab_ready import Fidelity, GateStatus


def _run(status: str, tool: str = "yosys") -> ToolRun:
    return ToolRun(
        tool=tool,
        status=status,
        command=[tool],
        exit_code={
            RUN_PASSED: 0,
            RUN_FAILED: 1,
            RUN_TIMEOUT: None,
            RUN_NOT_FOUND: None,
        }[status],
        stdout="out",
        stderr="err",
        error_code="",
        duration_s=0.01,
        tool_version="1.0",
        workdir=None,
    )


def _collector(tc: str = "tc", cfg: str = "cfg") -> EvidenceCollector:
    return EvidenceCollector(ToolRegistry(
        binaries={}, versions={}, toolchain_hash=tc, configuration_hash=cfg))


class TestRunToGateMapping:
    def test_honest_mapping(self):
        assert RUN_TO_GATE[RUN_PASSED] is GateStatus.PASS
        assert RUN_TO_GATE[RUN_FAILED] is GateStatus.FAIL
        assert RUN_TO_GATE[RUN_TIMEOUT] is GateStatus.FAIL
        assert RUN_TO_GATE[RUN_NOT_FOUND] is GateStatus.BLOCKED

    def test_mapping_covers_all_runner_outcomes(self):
        import rnd_engine.edatools as em

        outcome_values = {
            getattr(em, n) for n in dir(em)
            if n.startswith("RUN_") and n.isupper()
        }
        assert outcome_values == {
            "PASSED", "FAILED", "TIMEOUT", "TOOL_NOT_FOUND"}
        assert set(RUN_TO_GATE) == outcome_values


class TestToolRegistry:
    def test_discover_reports_missing_on_toolless_host(self):
        r = ToolRegistry.discover()
        assert len(r.binaries) >= 12
        assert all(v is None for v in r.binaries.values())
        assert r.status("yosys") == TOOL_MISSING
        assert r.all_installed(("yosys",)) is False

    def test_snapshot_deterministic(self):
        a = ToolRegistry.discover().snapshot()
        b = ToolRegistry.discover().snapshot()
        assert a == b
        assert a["toolchain_hash"] == b["toolchain_hash"]

    def test_snapshot_contains_hashes(self):
        snap = ToolRegistry.discover().snapshot()
        assert snap["toolchain_hash"]
        assert snap["configuration_hash"]
        assert "yosys" in snap["tools"]

    def test_registry_with_stubbed_binary(self):
        r = ToolRegistry(
            binaries={"yosys": "C:/fake/yosys.exe"},
            versions={"yosys": "0.30"},
            toolchain_hash="tc",
            configuration_hash="cfg",
        )
        assert r.status("yosys") == TOOL_INSTALLED
        assert r.version("yosys") == "0.30"
        assert r.missing(("yosys", "verilator")) == ["verilator"]


class TestEvidenceCollector:
    def test_passed_run_binds_artifact_hashes(self):
        c = _collector(tc="tc123", cfg="cfg123")
        rec = c.receipt_from_run(
            _run(RUN_PASSED),
            stage="synthesis",
            candidate_id="cand-1",
            fidelity=Fidelity.SYNTHESIS,
            input_hashes={"rtl": "abc"},
            output_hashes={"netlist": "def"},
            metrics={"cells": 42},
        )
        assert rec.status is GateStatus.PASS
        assert rec.tool == "yosys"
        assert rec.toolchain_hash == "tc123"
        assert rec.configuration_hash == "cfg123"
        assert rec.output_hashes == {"netlist": "def"}
        assert rec.metrics == {"cells": 42}

    def test_failed_run_is_fail_with_reason(self):
        rec = _collector().receipt_from_run(_run(RUN_FAILED), stage="lint")
        assert rec.status is GateStatus.FAIL
        assert "FAILED" in rec.failure_reason
        assert rec.provenance["exit_code"] == 1

    def test_timeout_is_fail_not_blocked(self):
        rec = _collector().receipt_from_run(_run(RUN_TIMEOUT), stage="physical")
        assert rec.status is GateStatus.FAIL
        assert "TIMEOUT" in rec.failure_reason

    def test_not_found_is_blocked_not_fail(self):
        rec = _collector().receipt_from_run(_run(RUN_NOT_FOUND), stage="lint")
        assert rec.status is GateStatus.BLOCKED
        assert "TOOL_NOT_FOUND" in rec.failure_reason

    def test_receipt_content_hash_stable(self):
        r1 = _collector().receipt_from_run(_run(RUN_PASSED), stage="lint")
        r2 = _collector().receipt_from_run(_run(RUN_PASSED), stage="lint")
        assert r1.content_hash() == r2.content_hash()

    def test_blocked_receipt_explicit(self):
        rec = _collector().blocked_receipt(
            stage="drc", reason="magic not installed")
        assert rec.status is GateStatus.BLOCKED
        assert rec.failure_reason == "magic not installed"
        assert rec.tool == ""


class TestStageAdapter:
    def test_preflight_blocks_when_tool_missing(self):
        reg = ToolRegistry(
            binaries={}, versions={}, toolchain_hash="tc",
            configuration_hash="cfg")

        class SynthAdapter(StageAdapter):
            stage = "synthesis"
            required_tools = ("yosys", "abc")

        rec = SynthAdapter(reg).execute(candidate_id="cand-9")
        assert rec.status is GateStatus.BLOCKED
        assert "yosys" in rec.failure_reason
        assert "abc" in rec.failure_reason

    def test_execute_real_path_when_tools_present(self):
        reg = ToolRegistry(
            binaries={"yosys": "C:/fake/yosys.exe"},
            versions={"yosys": "0.30"},
            toolchain_hash="tc", configuration_hash="cfg")
        calls: list[dict] = []

        class SynthAdapter(StageAdapter):
            stage = "synthesis"
            required_tools = ("yosys",)

            def _execute(self, **kwargs):
                calls.append(kwargs)
                return self.collector.receipt_from_run(
                    _run(RUN_PASSED), stage=self.stage,
                    candidate_id=kwargs.get("candidate_id", ""))

        rec = SynthAdapter(reg).execute(candidate_id="cand-7")
        assert rec.status is GateStatus.PASS
        assert calls and calls[0]["candidate_id"] == "cand-7"

    def test_base_adapter_is_abstract(self):
        reg = ToolRegistry(
            binaries={}, versions={}, toolchain_hash="tc",
            configuration_hash="cfg")
        with pytest.raises(NotImplementedError):
            StageAdapter(reg)._execute()
