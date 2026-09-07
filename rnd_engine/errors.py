"""Canonical external-tool error model (Phase L — EDA bootstrap).

Every failure of an external EDA executable is classified with one of the
codes below and never swallowed: the stored record preserves exit code,
stdout/stderr, command metadata, tool version, duration, stage, candidate and
artifact hash so downstream gates can hold the exact tool responsible.

Status vocabulary stays the project's honesty vocabulary: a missing tool is
``TOOL_NOT_FOUND``/``BLOCKED``, never ``PASS``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

# Python 3.10 compatibility: ``datetime.UTC`` only exists in 3.11+.
# ``timezone.utc`` and ``datetime.UTC`` are the same object on 3.11+.
UTC = timezone.utc

# Canonical failure codes for external-tool execution (§24 of the bootstrapping
# plan): one stable token per failure class so tool adapters, gates, receipts
# and CI consume identical vocabulary.
TOOL_NOT_FOUND = "TOOL_NOT_FOUND"
TOOL_EXECUTION_FAILED = "TOOL_EXECUTION_FAILED"
TIMEOUT = "TIMEOUT"
SYNTAX_ERROR = "SYNTAX_ERROR"
ELABORATION_ERROR = "ELABORATION_ERROR"
SIMULATION_FAILURE = "SIMULATION_FAILURE"
FORMAL_FAILURE = "FORMAL_FAILURE"
SYNTHESIS_FAILURE = "SYNTHESIS_FAILURE"
PNR_FAILURE = "PNR_FAILURE"
STA_FAILURE = "STA_FAILURE"
POWER_FAILURE = "POWER_FAILURE"
DRC_FAILURE = "DRC_FAILURE"
LVS_FAILURE = "LVS_FAILURE"
PDK_MISSING = "PDK_MISSING"
PDK_INVALID = "PDK_INVALID"
CONFIG_INVALID = "CONFIG_INVALID"
ARTIFACT_INVALID = "ARTIFACT_INVALID"

# Maps the coarse run status produced by edatools onto the fine-grained codes.
_COARSE_TO_CODE: dict[str, str] = {
    "TOOL_NOT_FOUND": TOOL_NOT_FOUND,
    "TIMEOUT": TIMEOUT,
    "FAILED": TOOL_EXECUTION_FAILED,
}


class ExternalToolError(RuntimeError):
    """Raised when an external EDA tool cannot be run or did not succeed.

    Attributes are deliberately the same fields every stage receipt records so
    an error can always be converted losslessly into a receipt line.
    """

    def __init__(
        self,
        code: str,
        tool: str,
        message: str,
        *,
        exit_code: int | None = None,
        stdout: str | None = None,
        stderr: str | None = None,
        command: list[str] | None = None,
        tool_version: str | None = None,
        duration_s: float | None = None,
        stage: str | None = None,
        candidate_id: str | None = None,
        artifact_hash: str | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.tool = tool
        self.message = message
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.command = command or []
        self.tool_version = tool_version
        self.duration_s = duration_s
        self.stage = stage
        self.candidate_id = candidate_id
        self.artifact_hash = artifact_hash
        self.env = {k: v for k, v in (env or {}).items()
                    if "SECRET" not in k.upper() and "TOKEN" not in k.upper()}
        self.timestamp_utc = datetime.now(UTC).isoformat(timespec="seconds")

    @classmethod
    def from_run(
        cls,
        run: Any,
        *,
        stage: str | None = None,
        candidate_id: str | None = None,
        artifact_hash: str | None = None,
    ) -> ExternalToolError:
        """Build an error from a ToolRun, preserving every field verbatim."""
        code = _COARSE_TO_CODE.get(run.status, TOOL_EXECUTION_FAILED)
        return cls(
            code=code,
            tool=run.tool,
            message=f"{run.tool} {run.status.lower()} (exit={run.exit_code})",
            exit_code=run.exit_code,
            stdout=run.stdout,
            stderr=run.stderr,
            command=run.command,
            tool_version=run.tool_version,
            duration_s=run.duration_s,
            stage=stage,
            candidate_id=candidate_id,
            artifact_hash=artifact_hash,
        )

    @classmethod
    def from_config(cls, message: str) -> ExternalToolError:
        return cls(CONFIG_INVALID, "config", message)

    @classmethod
    def from_pdk(cls, message: str) -> ExternalToolError:
        return cls(PDK_MISSING, "pdk", message)

    @classmethod
    def from_artifact(cls, message: str) -> ExternalToolError:
        return cls(ARTIFACT_INVALID, "artifact", message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "tool": self.tool,
            "message": self.message,
            "exit_code": self.exit_code,
            "stdout_tail": (self.stdout or "")[-2000:],
            "stderr_tail": (self.stderr or "")[-2000:],
            "command": self.command,
            "tool_version": self.tool_version,
            "duration_s": self.duration_s,
            "stage": self.stage,
            "candidate_id": self.candidate_id,
            "artifact_hash": self.artifact_hash,
            "env_keys": sorted(self.env),
            "timestamp_utc": self.timestamp_utc,
        }