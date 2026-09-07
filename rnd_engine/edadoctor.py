"""``rnd-engine eda-doctor`` — real tool discovery + smoke tests (§8, §6).

Honesty rules:

- a tool is reported by what actually happened, not by path lookup alone:
  ``MISSING`` (binary absent) / ``INSTALLED`` (binary present, smoke not yet
  run) / ``SMOKE_TEST_FAILED`` (binary ran but the smoke test failed or timed
  out) / ``READY`` (binary present AND a known-good smoke test passed)
- smoke tests execute *known-good tiny fixtures* through the real tool:
  Verilator lints a tiny module, Icarus compiles+simulates a tiny testbench,
  Yosys reads+synths a tiny design, SymbiYosys runs a minimal proof, OpenROAD
  reports its version, KLayout/Magic/Netgen version probes, etc.
- the PDK probe verifies the expected LEF/Liberty/GDS/SPICE/technology/DRC/LVS
  files under ``PDK_ROOT/<target>`` and computes a deterministic tree hash.
  A declared profile is metadata; only the filesystem probe can say READY.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .config import configuration_hash, load_config, pdk_hash, toolchain_hash
from .edatools import (
    RUN_FAILED,
    RUN_NOT_FOUND,
    RUN_PASSED,
    RUN_TIMEOUT,
    ToolRun,
    _resolve_binary,
    run_external_tool,
    toolchain_fingerprint,
)
from .errors import ExternalToolError

TOOL_STATUS_MISSING = "MISSING"
TOOL_STATUS_INSTALLED = "INSTALLED"
TOOL_STATUS_SMOKE_FAILED = "SMOKE_TEST_FAILED"
TOOL_STATUS_READY = "READY"

PDK_STATUS_MISSING = "MISSING"
PDK_STATUS_INVALID = "INVALID"
PDK_STATUS_READY = "READY"

#: The full set of tools the doctor probes (rtl, formal, synthesis, physical,
#: sta, drc, lvs, plus a VHDL compiler that is out of scope but detected).
DOCTOR_TOOLS: tuple[str, ...] = (
    "verilator", "iverilog", "vvp", "yosys", "abc", "sby", "openroad",
    "opensta", "magic", "netgen", "klayout", "ghdl",
)

#: Per-tool smoke command suffixes (argv after the resolved binary). Each is a
#: *known-good* minimal invocation. Unsupported probes degrade to
#: SMOKE_TEST_FAILED with the captured output — never READY without a passing
#: run.
_SMOKE_COMMANDS: dict[str, list[str]] = {
    "verilator": ["--lint-only", "--top-module", "smoke", "smoke.sv"],
    "iverilog": ["-g2012", "-o", "smoke.vvp", "smoke.sv", "smoke_tb.sv"],
    "vvp": ["-n", "smoke.vvp"],
    "yosys": ["-q", "-p", "read_verilog -sv smoke.sv; synth -top smoke; stat"],
    "abc": ["-c", "print_stats"],
    "sby": ["-f", "smoke.sby"],
    "openroad": ["-version"],
    "opensta": ["-version", "-no_init"],
    "magic": ["-dnull", "-noconsole", "-version"],
    "netgen": ["-batch", "-noconsole", "smoke.tcl"],
    "klayout": ["-v"],
    "ghdl": ["--version"],
}


class ToolStatus(BaseModel):
    """One probed tool, with the honest evidence that produced its status."""

    tool: str
    status: str = TOOL_STATUS_MISSING
    path: str | None = None
    version: str | None = None
    smoke_command: list[str] = Field(default_factory=list)
    smoke_status: str | None = None
    exit_code: int | None = None
    stdout_tail: str = ""
    stderr_tail: str = ""
    duration_s: float | None = None

    def to_row(self) -> dict[str, Any]:
        return {
            "TOOL": self.tool,
            "STATUS": self.status,
            "PATH": self.path,
            "VERSION": self.version or "unknown",
            "SMOKE": self.smoke_status or "-",
        }


class PdkCheck(BaseModel):
    """Filesystem probe of the target PDK (declared profile != installed)."""

    target: str
    root: str | None = None
    installed: bool = False
    valid: bool = False
    status: str = PDK_STATUS_MISSING
    tree_hash: str | None = None
    missing_paths: list[str] = Field(default_factory=list)
    checked_paths: list[str] = Field(default_factory=list)


class DoctorReport(BaseModel):
    """Aggregate eda-doctor output for one resolved configuration."""

    profile: str
    configuration_hash: str
    toolchain_hash: str
    tools: list[ToolStatus] = Field(default_factory=list)
    pdk: PdkCheck
    summary: dict[str, int] = Field(default_factory=dict)

    def tool(self, name: str) -> ToolStatus | None:
        return next((t for t in self.tools if t.tool == name), None)
def _fixture_files() -> dict[str, str]:
    """Known-good tiny fixtures for the smoke tests (byte-identical, versioned)."""
    sv = """module smoke(input logic clk, input logic rst_n, output logic q);
  always_ff @(posedge clk) if (!rst_n) q <= 1'b0; else q <= ~q;
endmodule
"""
    tb = """module smoke_tb;
  logic clk = 0, rst_n = 0, q;
  smoke dut (.clk(clk), .rst_n(rst_n), .q(q));
  always #5 clk = ~clk;
  initial begin
    repeat (3) @(posedge clk);
    rst_n = 1;
    repeat (3) @(posedge clk);
    if (q !== 1'b1) begin $display("SMOKE FAIL"); $finish(1); end
    $display("SMOKE OK");
    $finish(0);
  end
endmodule
"""
    sby = """[options]
mode bmc
depth 4

[engines]
smtbmc

[script]
read_verilog -sv smoke.sv
prep -top smoke

[files]
smoke.sv
"""
    netgen_tcl = """# netgen smoke: probe reports the patchlevel and version banner.
puts "netgen smoke: [info patchlevel]"
"""
    return {
        "smoke.sv": sv,
        "smoke_tb.sv": tb,
        "smoke.sby": sby,
        "smoke.tcl": netgen_tcl,
    }


def _run_smoke(
    tool: str,
    binary: str,
    config: dict[str, Any],
    workdir: Path,
    env: dict[str, str] | None,
) -> ToolRun:
    """Execute one tool's known-good smoke test; returns the honest run."""
    files = _fixture_files()
    for name, content in files.items():
        (workdir / name).write_text(content, encoding="utf-8")

    # The vvp smoke depends on the iverilog build artifact.
    if tool == "vvp" and not (workdir / "smoke.vvp").exists():
        comp = run_external_tool(
            [_resolve_binary("iverilog", config, env=env) or "iverilog",
             "-g2012", "-o", "smoke.vvp", "smoke.sv", "smoke_tb.sv"],
            tool="iverilog", config=config, workdir=workdir, env=env,
        )
        if not comp.passed:
            return comp

    cmd = ["-n", "smoke.vvp"] if tool == "vvp" else _SMOKE_COMMANDS.get(tool, ["--version"])
    return run_external_tool(
        [binary, *cmd],
        tool=tool, config=config, workdir=workdir, env=env,
    )
def _check_pdk(config: dict[str, Any], env: dict[str, str] | None) -> PdkCheck:
    """Probe the configured target PDK on the filesystem (honest, §6)."""
    pdk = config["pdk"]
    target = pdk["target"]
    env_map = dict(env) if env is not None else {}
    root = env_map.get("PDK_ROOT")
    if not root:
        for candidate in ["/usr/local/share/pdk", "/usr/share/pdk"]:
            if Path(candidate).is_dir():
                root = candidate
                break
    if not root:
        return PdkCheck(target=target, status=PDK_STATUS_MISSING,
                        missing_paths=["PDK_ROOT not set"])
    root_path = Path(root)
    target_dir = root_path / target
    if not target_dir.is_dir():
        return PdkCheck(target=target, root=str(root_path),
                        status=PDK_STATUS_MISSING,
                        missing_paths=[f"{target}/"])
    required = [str(p) for p in pdk.get("required_paths", [])]
    missing: list[str] = []
    checked: list[str] = []
    for rel in required:
        candidate = target_dir / rel
        checked.append(rel)
        if not candidate.exists():
            missing.append(rel)
    valid = not missing
    try:
        tree_hash = pdk_hash(target_dir) if valid else None
    except ExternalToolError:
        tree_hash = None
    status = PDK_STATUS_READY if valid else PDK_STATUS_INVALID
    return PdkCheck(
        target=target, root=str(root_path), installed=True, valid=valid,
        status=status, tree_hash=tree_hash, missing_paths=missing,
        checked_paths=checked,
    )


def run_eda_doctor(
    profile: str = "sky130",
    *,
    config_dir: str | Path | None = None,
    env: dict[str, str] | None = None,
    workdir: str | Path | None = None,
) -> DoctorReport:
    """Probe every configured tool and the target PDK; return the report.

    Deterministic output for a given machine: config hash and toolchain hash
    are stable digests; tool statuses derive solely from the filesystem and
    from actual smoke runs.
    """
    config = load_config(profile=profile, config_dir=config_dir, env=env)
    base_dir = Path(workdir) if workdir else Path(
        config.get("artifacts", {}).get("root", "artifacts"))
    smoke_dir = base_dir / "eda-doctor"
    smoke_dir.mkdir(parents=True, exist_ok=True)

    env_map = dict(env) if env is not None else None
    tools: list[ToolStatus] = []
    for name in DOCTOR_TOOLS:
        binary = _resolve_binary(name, config, env=env_map)
        if binary is None:
            tools.append(ToolStatus(tool=name, status=TOOL_STATUS_MISSING))
            continue
        try:
            run = _run_smoke(name, binary, config, smoke_dir, env_map)
        except ExternalToolError as exc:
            tools.append(ToolStatus(
                tool=name, status=TOOL_STATUS_SMOKE_FAILED, path=binary,
                stderr_tail=exc.message,
            ))
            continue
        if run.status == RUN_NOT_FOUND:
            tools.append(ToolStatus(tool=name, status=TOOL_STATUS_MISSING))
        elif run.status == RUN_TIMEOUT:
            tools.append(ToolStatus(
                tool=name, status=TOOL_STATUS_SMOKE_FAILED, path=binary,
                smoke_status=RUN_TIMEOUT,
                stdout_tail=run.stdout[-2000:], stderr_tail=run.stderr[-2000:],
            ))
        elif run.status == RUN_FAILED:
            tools.append(ToolStatus(
                tool=name, status=TOOL_STATUS_SMOKE_FAILED, path=binary,
                smoke_status=RUN_FAILED, exit_code=run.exit_code,
                stdout_tail=run.stdout[-2000:], stderr_tail=run.stderr[-2000:],
                duration_s=run.duration_s,
            ))
        else:
            tools.append(ToolStatus(
                tool=name, status=TOOL_STATUS_READY, path=binary,
                version=run.tool_version, smoke_status=RUN_PASSED,
                exit_code=run.exit_code,
                stdout_tail=run.stdout[-2000:], stderr_tail=run.stderr[-2000:],
                duration_s=run.duration_s,
            ))

    pdk = _check_pdk(config, env_map)
    fp = toolchain_fingerprint(config=config, env=env_map)
    versions = {n: meta["version"] for n, meta in sorted(fp.items())}

    summary: dict[str, int] = {"total": len(tools)}
    for status in (TOOL_STATUS_READY, TOOL_STATUS_MISSING,
                   TOOL_STATUS_SMOKE_FAILED, TOOL_STATUS_INSTALLED):
        summary[status] = sum(1 for t in tools if t.status == status)
    summary["pdk_" + pdk.status] = 1

    return DoctorReport(
        profile=profile,
        configuration_hash=configuration_hash(config),
        toolchain_hash=toolchain_hash(versions),
        tools=tools,
        pdk=pdk,
        summary=summary,
    )


def format_doctor_report(report: DoctorReport) -> str:
    """Render the eda-doctor text table (TOOL/VERSION/PATH/AVAILABILITY/STATUS)."""
    lines = [
        f"EDA DOCTOR  profile={report.profile}",
        f"configuration_hash={report.configuration_hash}",
        f"toolchain_hash={report.toolchain_hash}",
        "",
        f"{'TOOL':<12}{'STATUS':<18}{'VERSION':<24}{'PATH'}",
        "-" * 90,
    ]
    for tool in report.tools:
        lines.append(
            f"{tool.tool:<12}{tool.status:<18}"
            f"{(tool.version or 'unknown')[ : 24]:<24}{(tool.path or '-')}"
        )
        if tool.status == TOOL_STATUS_SMOKE_FAILED:
            lines.append(f"    smoke: exit={tool.exit_code} stderr={tool.stderr_tail[-300:]!r}")
    lines.append("")
    lines.append("PDK")
    lines.append(f"  target={report.pdk.target}")
    lines.append(f"  status={report.pdk.status}")
    lines.append(f"  root={report.pdk.root or '-'}")
    lines.append(f"  tree_hash={report.pdk.tree_hash or '-'}")
    if report.pdk.missing_paths:
        lines.append(f"  missing ({len(report.pdk.missing_paths)}):")
        for path in report.pdk.missing_paths:
            lines.append(f"    - {path}")
    lines.append("")
    lines.append(f"summary: {report.summary}")
    return "\n".join(lines)