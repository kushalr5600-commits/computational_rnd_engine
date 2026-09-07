"""RTL generation + quality-gate infrastructure.

Phase D: deterministic, synthesizable-property SystemVerilog generation from a
``MicroArchitectureSpec`` plus structural static checks. Real lint/elaboration
requires an external tool (Verilator/Icarus) — when none is present the gate is
honestly reported BLOCKED, never PASS.
"""

from .checker import (
    ELABORATION_RULES,
    STRUCTURAL_RULES,
    RtlLintIssue,
    RtlLintReport,
    detect_tools,
    elaboration_check,
    run_rtl_lint,
    structural_check,
    write_lint_report,
)
from .generator import (
    RTL_SCHEMA_VERSION,
    RtlError,
    generate_rtl,
    rtl_directory,
    rtl_file_hash,
)
from .model import RtlFileMeta, RtlManifest

__all__ = [
    "ELABORATION_RULES",
    "RTL_SCHEMA_VERSION",
    "STRUCTURAL_RULES",
    "RtlError",
    "RtlFileMeta",
    "RtlLintIssue",
    "RtlLintReport",
    "RtlManifest",
    "detect_tools",
    "elaboration_check",
    "generate_rtl",
    "rtl_directory",
    "rtl_file_hash",
    "run_rtl_lint",
    "structural_check",
    "write_lint_report",
]