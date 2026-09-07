"""EDA adapter architecture (Phase 5 of the fab-ready integration plan).

Three components, all extending the existing hardened runner in
:mod:`rnd_engine.edatools` (never duplicating it):

- :class:`ToolRegistry` Ã¢â‚¬â€ cheap per-tool discovery (binary + version +
  availability) cached per configuration. Adapters use it to decide honestly
  between RUN and BLOCKED before attempting execution. It does NOT run smoke
  tests; that remains :mod:`rnd_engine.edadoctor`'s job.
- :class:`EvidenceCollector` Ã¢â‚¬â€ converts a :class:`~rnd_engine.edatools.ToolRun`
  plus artifact hashes into a canonical
  :class:`~rnd_engine.fab_ready.EvidenceReceipt`. The status mapping is honest
  and fixed: PASSED->PASS, FAILED->FAIL, TIMEOUT->FAIL (the execution did not
  succeed), TOOL_NOT_FOUND->BLOCKED (environment problem, not a candidate
  failure).
- :class:`StageAdapter` Ã¢â‚¬â€ base class for stage executors (lint, simulation,
  synthesis, ...). Preflight refuses to run (returning a BLOCKED receipt)
  when required tools are missing; subclasses implement ``_execute``.
  Future FPGAAdapter / SiliconAdapter telemetry adapters plug in here (Ã‚Â§28).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from .config import configuration_hash, load_config
from .edatools import (
    RUN_FAILED,
    RUN_NOT_FOUND,
    RUN_PASSED,
    RUN_TIMEOUT,
    ToolRun,
    _resolve_binary,
    resolved_toolchain_hash,
    tool_version,
)
from .fab_ready import EvidenceReceipt, Fidelity, GateStatus

#: Honest mapping from runner outcome to gate status. Never edited per-stage:
#: a tool that did not run is BLOCKED; a tool that ran and failed is FAIL.
RUN_TO_GATE: dict[str, GateStatus] = {
    RUN_PASSED: GateStatus.PASS,
    RUN_FAILED: GateStatus.FAIL,
    RUN_TIMEOUT: GateStatus.FAIL,
    RUN_NOT_FOUND: GateStatus.BLOCKED,
}

TOOL_MISSING = "MISSING"
TOOL_INSTALLED = "INSTALLED"


class ToolRegistry(BaseModel):
    """Cached discovery of the configured toolchain (no smoke tests)."""

    binaries: dict[str, str | None] = Field(default_factory=dict)
    versions: dict[str, str | None] = Field(default_factory=dict)
    toolchain_hash: str = ""
    configuration_hash: str = ""

    @classmethod
    def discover(cls, config: dict[str, Any] | None = None,
                 env: dict[str, str] | None = None) -> ToolRegistry:
        cfg = config or load_config(env=env)
        binaries: dict[str, str | None] = {}
        versions: dict[str, str | None] = {}
        for name in sorted(cfg.get("tools", {})):
            binary = _resolve_binary(name, cfg, env=env)
            binaries[name] = binary
            versions[name] = (
                tool_version(binary, name, env=env) if binary else None)
        return cls(
            binaries=binaries,
            versions=versions,
            toolchain_hash=resolved_toolchain_hash(config=cfg, env=env),
            configuration_hash=configuration_hash(cfg),
        )

    def binary(self, tool: str) -> str | None:
        return self.binaries.get(tool)

    def version(self, tool: str) -> str | None:
        return self.versions.get(tool)

    def status(self, tool: str) -> str:
        """MISSING or INSTALLED Ã¢â‚¬â€ never READY (that requires a smoke test)."""
        return TOOL_INSTALLED if self.binaries.get(tool) else TOOL_MISSING

    def missing(self, tools: tuple[str, ...] | list[str]) -> list[str]:
        return [t for t in tools if self.binaries.get(t) is None]

    def all_installed(self, tools: tuple[str, ...] | list[str]) -> bool:
        return not self.missing(list(tools))

    def snapshot(self) -> dict[str, Any]:
        """Deterministic identity snapshot for manifests and receipts."""
        return {
            "tools": {
                name: {
                    "status": self.status(name),
                    "path": self.binaries.get(name),
                    "version": self.versions.get(name),
                }
                for name in sorted(self.binaries)
            },
            "toolchain_hash": self.toolchain_hash,
            "configuration_hash": self.configuration_hash,
        }

class EvidenceCollector:
    """Converts ToolRun outcomes into canonical EvidenceReceipts (honestly).

    Status mapping is fixed by RUN_TO_GATE and never overridden per stage:
    PASSED->PASS, FAILED->FAIL, TIMEOUT->FAIL, TOOL_NOT_FOUND->BLOCKED.
    Artifact hashes bind the receipt to the exact candidate artifact that was
    executed, guarding against evaluating a different artifact (S17).
    """

    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    def receipt_from_run(
        self,
        run: ToolRun,
        *,
        stage: str,
        candidate_id: str = "",
        fidelity: Fidelity = Fidelity.SURROGATE,
        input_hashes: dict[str, str] | None = None,
        output_hashes: dict[str, str] | None = None,
        metrics: dict[str, Any] | None = None,
        failure_reason: str = "",
    ) -> EvidenceReceipt:
        gate = RUN_TO_GATE[run.status]
        if gate != GateStatus.PASS and not failure_reason:
            failure_reason = (
                f"tool {run.tool} {run.status}"
                + (f" (exit {run.exit_code})" if run.exit_code is not None else ""))
        return EvidenceReceipt(
            candidate_id=candidate_id,
            stage=stage,
            status=gate,
            fidelity=fidelity,
            provider="external_tool",
            tool=run.tool,
            tool_version=run.tool_version or "unknown",
            command=run.command,
            output_hashes=dict(output_hashes or {}),
            input_hashes=dict(input_hashes or {}),
            metrics=dict(metrics or {}),
            toolchain_hash=self.registry.toolchain_hash,
            configuration_hash=self.registry.configuration_hash,
            duration_s=run.duration_s,
            failure_reason=failure_reason,
            provenance={
                "exit_code": run.exit_code,
                "workdir": run.workdir,
                "error_code": run.error_code,
                "stdout_tail": run.stdout[-2000:],
                "stderr_tail": run.stderr[-2000:],
            },
        )

    def blocked_receipt(
        self,
        *,
        stage: str,
        candidate_id: str = "",
        fidelity: Fidelity = Fidelity.SURROGATE,
        reason: str,
    ) -> EvidenceReceipt:
        """An honest BLOCKED receipt for a stage that could not attempt a run."""
        return EvidenceReceipt(
            candidate_id=candidate_id,
            stage=stage,
            status=GateStatus.BLOCKED,
            fidelity=fidelity,
            provider="tool_registry",
            toolchain_hash=self.registry.toolchain_hash,
            configuration_hash=self.registry.configuration_hash,
            failure_reason=reason,
        )


class StageAdapter:
    """Base class for stage executors.

    Preflight is honest by construction: if any required tool is MISSING the
    adapter returns a BLOCKED receipt and never launches a process. Subclasses
    implement ``_execute`` which must build the real command, run it through
    :func:`rnd_engine.edatools.run_external_tool`, and collect outputs with
    :class:`EvidenceCollector`.
    """

    #: pipeline stage name implemented by this adapter
    stage: str = ""
    #: external tools that must be INSTALLED for the stage to attempt a run
    required_tools: tuple[str, ...] = ()

    def __init__(self, registry: ToolRegistry,
                 collector: EvidenceCollector | None = None) -> None:
        self.registry = registry
        self.collector = collector or EvidenceCollector(registry)

    def preflight(self) -> list[str]:
        return self.registry.missing(self.required_tools)

    def execute(
        self,
        candidate_id: str = "",
        fidelity: Fidelity = Fidelity.SURROGATE,
        **kwargs: Any,
    ) -> EvidenceReceipt:
        missing = self.preflight()
        if missing:
            return self.collector.blocked_receipt(
                stage=self.stage,
                candidate_id=candidate_id,
                fidelity=fidelity,
                reason=(
                    f"stage {self.stage} requires missing tools: "
                    + ", ".join(sorted(missing))),
            )
        return self._execute(candidate_id=candidate_id, fidelity=fidelity, **kwargs)

    def _execute(self, **kwargs: Any) -> EvidenceReceipt:
        raise NotImplementedError(
            f"adapter for stage {self.stage!r} must implement _execute")
