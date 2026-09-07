from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class RtlFileMeta(BaseModel):
    """One generated RTL file with content digest."""

    path: str
    sha256: str


class RtlManifest(BaseModel):
    """Build manifest for a generated RTL release.

    The manifest binds the RTL to the design/spec/microarchitecture it was
    generated from via content hashes — no timestamp-based identity.
    """

    design_id: str
    architecture_schema_version: int
    specification_hash: str
    microarchitecture_hash: str
    rtl_schema_version: int = 1
    generator_version: str = "1.0.0"
    architecture_hash: str = ""
    files: list[RtlFileMeta] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)


class RtlLintIssue(BaseModel):
    """One lint/structural finding with severity + rule id."""

    file: str
    line: int | None = None
    severity: str = "error"
    message: str
    rule: str


class RtlLintReport(BaseModel):
    """Machine-readable lint report.

    Status vocabulary: PASSED / FAILED / BLOCKED / NOT_RUN. A real tool (e.g.
    Verilator) produces the report; a missing tool is BLOCKED, never PASS.
    """

    status: str = "NOT_RUN"
    tool: str = ""
    tool_version: str | None = None
    rules_checked: list[str] = Field(default_factory=list)
    issues: list[RtlLintIssue] = Field(default_factory=list)
    summary: dict[str, int] = Field(default_factory=dict)


def _sub_path(path: str | Path) -> str:
    return str(Path(path))