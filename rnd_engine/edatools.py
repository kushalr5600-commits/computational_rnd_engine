"""Security-hardened external EDA tool runner (bootstrapping plan §23-§24).

Every EDA executable is launched only through this module. Invariants:

- argument arrays only — never ``shell=True``
- controlled environment: PATH + an explicit allowlist of variables (from the
  flow configuration's ``security.env_allowlist`` plus the documented
  ``*_BIN``/``PDK_ROOT``/``EDA_ROOT``/``PDK`` conventions) — the parent
  environment is never inherited wholesale, so host secrets cannot propagate
- timeout + bounded output capture (configurable; defaults from config)
- absolute path arguments are resolved and checked for containment inside the
  allowed roots (the isolated workdir and the read-only PDK root)
- outcome classification is honest: ``PASSED`` / ``FAILED`` / ``TIMEOUT`` /
  ``TOOL_NOT_FOUND`` map to the canonical error codes in ``rnd_engine.errors``
- version discovery per tool with a conservative fallback to ``unknown``

The runner never fabricates a ``PASS``: a tool that did not run reports
``TOOL_NOT_FOUND``, a tool that timed out reports ``TIMEOUT``, and a non-zero
exit is ``FAILED`` with stdout/stderr captured for the receipt.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from time import time as _monotonic
from typing import Any

from pydantic import BaseModel, Field

from .config import load_config, toolchain_hash
from .errors import (
    TIMEOUT,
    TOOL_EXECUTION_FAILED,
    TOOL_NOT_FOUND,
    ExternalToolError,
)

#: Candidate version-discovery flags per tool, tried in order. Some tools print
#: their version banner to stderr or need a driver flag; a tool whose version
#: cannot be discovered is honestly recorded as "unknown".
VERSION_FLAGS: dict[str, list[list[str]]] = {
    "verilator": [["--version"]],
    "iverilog": [["-V"]],
    "vvp": [["-V"]],
    "yosys": [["-V"]],
    "sby": [["--version"]],
    "openroad": [["-version"], ["--version"]],
    "opensta": [["-version"], ["--version"]],
    "magic": [["-dnull", "-noconsole", "-version"], ["--version"]],
    # netgen 1.5.265: `-v` / `--version` / `-batch` all enter its interactive TUI
    # (endless menu scroll, unbounded stdout) instead of printing a version and
    # exiting. There is no safe one-flag probe for this build, so auto-discovery
    # is disabled; the version is honestly recorded as "unknown".
    "netgen": [],
    # klayout needs batch mode (-b) or -v spins up the Qt GUI (segfault headless).
    "klayout": [["-b", "-v"]],
    "ghdl": [["--version"]],
    "abc": [["-c", "print_stats"], []],
}

#: Outcome codes produced by this runner (mirrored in ``rnd_engine.errors``).
RUN_PASSED = "PASSED"
RUN_FAILED = "FAILED"
RUN_TIMEOUT = "TIMEOUT"
RUN_NOT_FOUND = "TOOL_NOT_FOUND"


class ToolRun(BaseModel):
    """One executed (or refused) external-tool invocation, captured in full."""

    tool: str
    command: list[str] = Field(default_factory=list)
    status: str = RUN_NOT_FOUND  # PASSED / FAILED / TIMEOUT / TOOL_NOT_FOUND
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    tool_version: str | None = None
    duration_s: float | None = None
    error_code: str | None = None
    workdir: str | None = None
    env_keys: list[str] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.status == RUN_PASSED


def _resolve_binary(
    tool_name: str,
    config: dict[str, Any],
    env: dict[str, str] | None = None,
) -> str | None:
    """Resolve a tool's executable from config + documented env overrides."""
    spec = config.get("tools", {}).get(tool_name)
    if not isinstance(spec, dict):
        return None
    source = dict(os.environ) if env is None else dict(env)
    override = source.get(spec.get("env_override", ""))
    candidate = override or spec.get("binary") or tool_name
    found = shutil.which(candidate)
    if found:
        return found
    if Path(candidate).is_absolute() and os.access(candidate, os.X_OK):
        return candidate
    return None
def find_tool(tool_name, config=None, env=None):
    """Return the absolute path of an installed tool, or None (honest miss)."""
    config = config or load_config(env=env)
    return _resolve_binary(tool_name, config, env=env)


def tool_version(binary, tool_name, timeout_s=15.0, env=None):
    """Best-effort version discovery. None (reported as unknown) is honest."""
    for flags in VERSION_FLAGS.get(tool_name, []):
        if not flags:
            return None
        try:
            proc = subprocess.run(
                [binary, *flags],
                capture_output=True,
                text=True,
                timeout=timeout_s,
                env=env,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        text = (proc.stderr or "") + (proc.stdout or "")
        line = next((ln.strip() for ln in text.splitlines() if ln.strip()), None)
        if line:
            return line[:200]
    return None


def _controlled_env(config, env=None, extra=None):
    """Build the subprocess environment: PATH + allowlisted vars only."""
    source = dict(os.environ) if env is None else dict(env)
    allowlist = set(config.get("security", {}).get("env_allowlist", []))
    allowlist.update(
        k for k in source if k.endswith("_BIN") or k in ("PDK_ROOT", "PDK", "EDA_ROOT")
    )
    controlled = {"PATH": source.get("PATH") or "/usr/bin:/bin"}
    for name in allowlist:
        if name in source:
            controlled[name] = source[name]
    if extra:
        for name, value in extra.items():
            controlled[name] = value
    return controlled


def _assert_contained(path, allowed_roots):
    """Reject path traversal: absolute args must live under an allowed root."""
    p = Path(path)
    if not p.is_absolute():
        return  # relative args are resolved inside the tool's cwd (workdir)
    try:
        resolved = p.resolve()
    except OSError as exc:
        raise ExternalToolError(
            TOOL_EXECUTION_FAILED,
            "runner",
            f"cannot resolve path {p}: {exc}",
        ) from exc
    for root in allowed_roots:
        try:
            resolved.relative_to(root.resolve())
            return
        except ValueError:
            continue
    raise ExternalToolError(
        TOOL_EXECUTION_FAILED,
        "runner",
        f"path {resolved} escapes the allowed workdir/PDK roots",
        command=[str(p)],
    )
def run_external_tool(
    command,
    *,
    tool,
    config,
    workdir=None,
    timeout_s=None,
    env=None,
    max_output_bytes=None,
    allowed_roots=None,
    version_flags=None,
) -> ToolRun:
    """Execute one EDA tool securely and capture an honest, bounded receipt.

    Raises ``ExternalToolError`` only for *policy* violations (containment
    escapes). Tool outcomes are never raised — they are returned as
    ``ToolRun`` records so receipts and gates can decide statuses.
    """
    if not command or not all(isinstance(a, str) for a in command):
        raise ExternalToolError(
            TOOL_EXECUTION_FAILED,
            tool,
            "command must be a non-empty list of strings (no shell)",
        )
    binary = command[0]
    if not Path(binary).is_absolute():
        resolved_bin = shutil.which(binary)
        if resolved_bin is None:
            return ToolRun(
                tool=tool,
                command=command,
                status=RUN_NOT_FOUND,
                error_code=TOOL_NOT_FOUND,
            )
        binary = resolved_bin

    security = config.get("security", {})
    timeout_s = timeout_s if timeout_s is not None else float(
        security.get("default_timeout_s", 600))
    max_bytes = max_output_bytes if max_output_bytes is not None else int(
        security.get("max_output_bytes", 1_048_576))

    cwd = Path(workdir) if workdir else Path.cwd()
    cwd.mkdir(parents=True, exist_ok=True)
    roots = [cwd, *(Path(r) for r in (allowed_roots or []))]
    for arg in command[1:]:
        _assert_contained(arg, roots)

    controlled = _controlled_env(config, env=env)
    started = _monotonic()
    try:
        proc = subprocess.run(
            [binary, *command[1:]],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout_s,
            env=controlled,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return ToolRun(
            tool=tool,
            command=command,
            status=RUN_TIMEOUT,
            error_code=TIMEOUT,
            stdout=(exc.stdout or "")[-max_bytes:],
            stderr=(exc.stderr or "")[-max_bytes:],
            duration_s=round(_monotonic() - started, 3),
            workdir=str(cwd),
            env_keys=sorted(controlled),
        )
    except OSError as exc:
        return ToolRun(
            tool=tool,
            command=command,
            status=RUN_FAILED,
            error_code=TOOL_EXECUTION_FAILED,
            stdout="",
            stderr=f"launch failed: {exc}",
            duration_s=round(_monotonic() - started, 3),
            workdir=str(cwd),
            env_keys=sorted(controlled),
        )

    duration = round(_monotonic() - started, 3)
    version = None
    if proc.returncode == 0 and version_flags is not None:
        version = _discover_version(binary, version_flags, controlled)
    status = RUN_PASSED if proc.returncode == 0 else RUN_FAILED
    return ToolRun(
        tool=tool,
        command=command,
        status=status,
        exit_code=proc.returncode,
        stdout=(proc.stdout or "")[-max_bytes:],
        stderr=(proc.stderr or "")[-max_bytes:],
        tool_version=version,
        duration_s=duration,
        error_code=None if status == RUN_PASSED else TOOL_EXECUTION_FAILED,
        workdir=str(cwd),
        env_keys=sorted(controlled),
    )
def _discover_version(binary, flags, env):
    """Try each candidate flag set; return the first non-empty version line."""
    for group in flags:
        try:
            proc = subprocess.run(
                [binary, *group],
                capture_output=True,
                text=True,
                timeout=15.0,
                env=env,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        text = (proc.stderr or "") + (proc.stdout or "")
        line = next((ln.strip() for ln in text.splitlines() if ln.strip()), None)
        if line:
            return line[:200]
    return None


def toolchain_fingerprint(config=None, env=None):
    """Discover the resolved toolchain: name -> {path, version} for installed
    tools only. Missing tools are omitted — they cannot influence the digest of
    a *resolved* toolchain; ``toolchain_hash`` covers the versions that
    actually exist at resolution time (§22)."""
    config = config or load_config(env=env)
    fingerprint = {}
    for name in config.get("tools", {}):
        binary = _resolve_binary(name, config, env=env)
        if binary is None:
            continue
        fingerprint[name] = {
            "path": binary,
            "version": tool_version(binary, name, env=env) or "unknown",
        }
    return fingerprint


def resolved_toolchain_hash(config=None, env=None):
    """Stable identity of the resolved toolchain (installed versions only)."""
    fp = toolchain_fingerprint(config=config, env=env)
    versions = {name: meta["version"] for name, meta in sorted(fp.items())}
    return toolchain_hash(versions)