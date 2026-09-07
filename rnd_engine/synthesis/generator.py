"""Synthesis abstraction (Phase F, toolless scope).

Deterministic Yosys config + flow generation, and a runner that executes the
flow when the ``yosys`` binary is present. When it is absent the synthesis
gate is honestly **BLOCKED** — never PASS, and no fake area/timing numbers.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from ..microarchitecture.model import MicroArchitectureSpec
from ..rtl.checker import detect_tools
from ..rtl.generator import _build_params
from ..rtl.model import RtlLintIssue, RtlLintReport, RtlManifest
from .model import SynthesisCellStats, SynthesisConfig, SynthesisManifest

SYNTHESIS_SCHEMA_VERSION: int = 1


class SynthesisError(RuntimeError):
    """Raised when a design cannot be prepared for synthesis."""


_WIRE_RE = re.compile(r"Number of wires:\s+(\d+)")
_CELL_RE = re.compile(r"Number of cells:\s+(\d+)")
_CELL_TYPE_RE = re.compile(r"^\s+(\S+)\s+(\d+)$", re.MULTILINE)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _clock_period_ns(params: dict[str, Any]) -> float:
    mhz = int(params.get("CORE_FREQ_MHZ") or 0)
    return round(1000.0 / mhz, 4) if mhz > 0 else 10.0


def _synthesis_config(micro: MicroArchitectureSpec, sources: list[str]) -> SynthesisConfig:
    """Deterministic config: pure function of the microarchitecture + source list."""
    return SynthesisConfig(
        design_id=micro.design_id,
        top_module="top",
        clock_period_ns=_clock_period_ns(_build_params(micro)),
        source_files=list(sources),
        flattening=True,
        provenance={
            "seed": micro.provenance.get("seed"),
        },
    )


def render_yosys_flow(config: SynthesisConfig) -> str:
    """Render the deterministic Yosys script for a config."""
    reads = "\n".join(f"read_verilog -sv {src}" for src in config.source_files)
    flatten = "flatten" if config.flattening else ""
    return f"""# Generated Yosys flow for design {config.design_id} (Phase F).
# Deterministic: pure function of SynthesisConfig. Target period {config.clock_period_ns} ns.
{reads}
synth -top {config.top_module}
{flatten}
opt_clean
stat
write_json {config.design_id}.netlist.json
"""


def _parse_stat_output(output: str) -> SynthesisCellStats:
    """Tolerant parser for the yosys ``stat`` summary block."""
    wires = _WIRE_RE.search(output)
    cells = _CELL_RE.search(output)
    types: dict[str, int] = {}
    in_cells = False
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if line.startswith("Number of cells:"):
            in_cells = True
            continue
        if in_cells:
            m = _CELL_TYPE_RE.match(raw_line)
            if m and m.group(1) not in ("Number", "Chip", "Area"):
                types[m.group(1)] = int(m.group(2))
            elif line == "" or line.startswith("==="):
                in_cells = False
    return SynthesisCellStats(
        number_of_wires=int(wires.group(1)) if wires else None,
        number_of_cells=int(cells.group(1)) if cells else None,
        cell_types=types,
    )

def run_yosys(rtl_dir: Path, flow_text: str, work_dir: Path) -> tuple[str, SynthesisCellStats | None, str | None]:
    """Execute the flow with the installed yosys binary.

    Returns (status, stats, stderr_tail). Never fabricates results.
    """
    work_dir.mkdir(parents=True, exist_ok=True)
    flow_path = work_dir / "flow.ys"
    flow_path.write_text(flow_text, encoding="utf-8")
    proc = subprocess.run(
        ["yosys", "-s", str(flow_path)],
        cwd=rtl_dir,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return "FAILED", None, (proc.stderr or proc.stdout)[-2000:]
    return "PASSED", _parse_stat_output(proc.stdout), None

def synthesize(
    micro: MicroArchitectureSpec,
    rtl_manifest: RtlManifest,
    out_dir: str | Path = "artifacts",
) -> SynthesisManifest:
    """Produce the synthesis config/flow artifacts and run Yosys when available."""
    if not micro.design_id:
        raise SynthesisError("MicroArchitectureSpec has no design_id.")
    if rtl_manifest.design_id != micro.design_id:
        raise SynthesisError(
            f"RTL manifest design {rtl_manifest.design_id} != {micro.design_id}")

    sources = [m.path for m in rtl_manifest.files if m.path.endswith(".sv")]
    config = _synthesis_config(micro, sources)
    flow_text = render_yosys_flow(config)

    base = Path(out_dir)
    cfg_dir = base / "configs" / "synthesis" / micro.design_id
    flow_dir = base / "flows" / "synthesis" / micro.design_id
    reports_dir = base / "reports" / "synthesis" / micro.design_id
    for d in (cfg_dir, flow_dir, reports_dir):
        d.mkdir(parents=True, exist_ok=True)
    cfg_path = cfg_dir / "config.json"
    cfg_path.write_text(
        json.dumps(config.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    (flow_dir / "flow.ys").write_text(flow_text, encoding="utf-8")

    config_hash = _sha256_file(cfg_path)[:32]
    yosys_path = detect_tools().get("yosys")
    tool_versions: dict[str, str] = {}

    if yosys_path is None:
        status, stats, netlist, tool_version = "BLOCKED", None, None, None
        issues = [RtlLintIssue(
            file="-", severity="info", rule="TOOL",
            message="binary 'yosys' not found on PATH; synthesis gate is BLOCKED, "
                    "config.json and flow.ys are generated but never executed")]
    else:
        version = subprocess.run(
            ["yosys", "-V"], capture_output=True, text=True, check=False)
        tool_version = (version.stdout or "").strip().splitlines()[0] if version.stdout else None
        rtl_dir = base / "rtl" / micro.design_id
        status, stats, err = run_yosys(rtl_dir, flow_text, reports_dir / "work")
        netlist = f"{micro.design_id}.netlist.json" if status == "PASSED" else None
        if status == "FAILED" and err:
            (reports_dir / "yosys_stderr.txt").write_text(err, encoding="utf-8")
        issues = [RtlLintIssue(
            file="-", severity="error", rule="SYN-001",
            message="yosys flow failed; see yosys_stderr.txt")] if status == "FAILED" else []
        tool_versions = {"yosys": tool_version or "unknown"}

    report = RtlLintReport(
        status=status, tool="yosys", tool_version=tool_version,
        rules_checked=["SYN-001"], issues=issues,
        summary=({"cells": stats.number_of_cells}
                 if stats and stats.number_of_cells is not None else {}),
    )
    (reports_dir / "yosys.json").write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8")

    manifest = SynthesisManifest(
        design_id=micro.design_id,
        rtl_architecture_hash=rtl_manifest.architecture_hash,
        synthesis_config_hash=config_hash,
        synthesis_schema_version=SYNTHESIS_SCHEMA_VERSION,
        tool="yosys",
        tool_path=yosys_path,
        tool_version=tool_version,
        status=status,
        stats=stats,
        netlist_path=netlist,
        provenance={
            **(micro.provenance or {}),
            "config_path": f"configs/synthesis/{micro.design_id}/config.json",
            "flow_path": f"flows/synthesis/{micro.design_id}/flow.ys",
            "report_path": f"reports/synthesis/{micro.design_id}/yosys.json",
            "tool_versions": tool_versions,
        },
    )
    (reports_dir / "manifest.json").write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    return manifest