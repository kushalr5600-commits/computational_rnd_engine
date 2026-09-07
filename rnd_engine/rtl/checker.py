from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from .model import RtlLintIssue, RtlLintReport

# Tools we know how to drive when present. Detection is honest: if the binary is
# missing the entry is None and any gate depending on it reports BLOCKED.
TOOL_BINARIES: dict[str, str] = {
    "verilator": "verilator",
    "iverilog": "iverilog",
    "yosys": "yosys",
}


def detect_tools() -> dict[str, str | None]:
    """Return tool name -> path (or None when the tool is not installed)."""
    return {name: (shutil.which(bin) or None) for name, bin in TOOL_BINARIES.items()}


_COMMENT_RE = re.compile(r"(/\*.*?\*/|//[^\n]*)")


def _strip_comments(text: str) -> str:
    return _COMMENT_RE.sub(" ", text)


def _strip_strings(text: str) -> str:
    # Replace double-quoted strings with '""' placeholders (safe for RTL source).
    return re.sub(r'"(?:[^"\\]|\\.)*"', '""', text)


def _outline(text: str) -> str:
    """Return a normalized, comment/string-stripped source for structural scans."""
    return _strip_strings(_strip_comments(text))


_RULES = [
    "RCHK-001",
    "RCHK-002",
    "RCHK-003",
    "RCHK-004",
    "RCHK-005",
    "RCHK-006",
    "RCHK-007",
    "RCHK-008",
]
STRUCTURAL_RULES = _RULES

# ---------------------------------------------------------------------------
# Pure-Python elaboration: cross-check instantiations against module
# definitions (existence, ports, parameters). Position-preserving stripping
# lets reported line numbers refer to the real source.
# ---------------------------------------------------------------------------

ELABORATION_RULES = ["ELB-001", "ELB-002", "ELB-003", "ELB-004", "ELB-005", "ELB-006"]

_SV_KEYWORDS = frozenset({
    "module", "endmodule", "logic", "bit", "reg", "wire", "always_ff",
    "always_comb", "always_latch", "assign", "parameter", "localparam",
    "input", "output", "inout", "begin", "end", "case", "endcase", "casex",
    "casez", "if", "else", "for", "while", "repeat", "generate",
    "endgenerate", "integer", "genvar", "unique", "priority", "posedge",
    "negedge", "function", "endfunction", "return", "default", "typedef",
    "enum", "struct", "package", "endpackage", "import", "export",
})


def _blank_comments(text: str) -> str:
    """Blank comments/strings to spaces, preserving character positions.

    Unlike ``_outline`` (which collapses runs), this keeps every character
    position — and every newline — aligned with the original source so that
    findings can carry an accurate line number.
    """

    def _blank(m: re.Match[str]) -> str:
        return re.sub(r"[^\n]", " ", m.group(0))

    return re.sub(r'"(?:[^"\\]|\\.)*"|/\*.*?\*/|//[^\n]*', _blank, text, flags=re.DOTALL)


def _match_paren(text: str, open_idx: int) -> int:
    """Return the index of the ')' balancing the '(' at ``open_idx``, or -1."""
    depth = 0
    for i in range(open_idx, len(text)):
        c = text[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i
    return -1


def _split_top_level(s: str) -> list[str]:
    """Split on commas that are not nested inside parentheses."""
    items: list[str] = []
    depth = 0
    cur: list[str] = []
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            items.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    items.append("".join(cur))
    return [i.strip() for i in items if i.strip()]


def structural_check(rtl_dir: str | Path) -> RtlLintReport:
    """Run pure-Python structural static checks over a generated RTL tree.

    These checks are deliberately conservative and *not* a substitute for a real
    lint/elaboration tool. They catch the common synthesizability hazards the
    generator must never emit (initial blocks, delays, unbalanced begin/end,
    latches, missing always_ff on sequential modules).
    """
    root = Path(rtl_dir)
    issues: list[RtlLintIssue] = []
    checked = 0

    sv_files = sorted(p for p in root.rglob("*.sv") if p.is_file())
    for path in sv_files:
        rel = str(path.relative_to(root)).replace("\\", "/")
        text = path.read_text(encoding="utf-8")
        out = _outline(text)
        checked += 1

        # RCHK-001: latches — plain "always @" blocks are not allowed (use
        # always_ff/always_comb). Tolerate a standalone 'always_comb(' token.
        for m in re.finditer(r"\balways\b(?:\s*@)?\s*\(", out):
            line = text.count("\n", 0, m.start()) + 1
            issues.append(
                RtlLintIssue(
                    file=rel, line=line, severity="error", rule="RCHK-001",
                    message="bare 'always' block found; use always_ff / always_comb",
                )
            )

        # RCHK-002: no initial blocks in RTL.
        for m in re.finditer(r"\binitial\b", out):
            line = text.count("\n", 0, m.start()) + 1
            issues.append(
                RtlLintIssue(
                    file=rel, line=line, severity="error", rule="RCHK-002",
                    message="RTL must not contain initial blocks",
                )
            )

        # RCHK-003: no #delay.
        for m in re.finditer(r"#\s*\d", out):
            line = text.count("\n", 0, m.start()) + 1
            issues.append(
                RtlLintIssue(
                    file=rel, line=line, severity="error", rule="RCHK-003",
                    message="RTL must not contain #delays",
                )
            )

        # RCHK-004: balanced module/endmodule.
        n_mod = len(re.findall(r"\bmodule\b", out))
        n_end = len(re.findall(r"\bendmodule\b", out))
        if n_mod != n_end:
            issues.append(
                RtlLintIssue(
                    file=rel, severity="error", rule="RCHK-004",
                    message=f"unbalanced module/endmodule ({n_mod} vs {n_end})",
                )
            )

        # RCHK-005: balanced begin/end.
        n_begin = len(re.findall(r"\bbegin\b", out))
        n_end_kw = len(re.findall(r"\bend\b", out))
        if n_begin != n_end_kw:
            issues.append(
                RtlLintIssue(
                    file=rel, severity="error", rule="RCHK-005",
                    message=f"unbalanced begin/end ({n_begin} vs {n_end_kw})",
                )
            )

        # RCHK-006: every sequential always_ff must use non-blocking (<=).
        if "always_ff" in out:
            body_re = re.findall(r"always_ff\s*@\([^)]*\)\s*(begin.*?end)", out, re.DOTALL)
            for body in body_re:
                if "<=" not in body:
                    issues.append(
                        RtlLintIssue(
                            file=rel, severity="error", rule="RCHK-006",
                            message="always_ff block with no non-blocking (<=) assignment",
                        )
                    )

        # RCHK-007: sequential behavior on a clock must use always_ff, not a
        # bare `always @(posedge clk)` (an inferable-latch/timing hazard). Pure
        # structural wrappers (a top that only instantiates clocked leaf
        # modules) are legitimate and are NOT flagged.
        if re.search(r"always\s*@\s*\(\s*posedge\s+clk", out):
            issues.append(
                RtlLintIssue(
                    file=rel, severity="error", rule="RCHK-007",
                    message="bare 'always @(posedge clk)' block; use always_ff",
                )
            )

        # RCHK-008: no wait/fork/join in RTL.
        if re.search(r"\b(wait|fork|join)\b", out):
            issues.append(
                RtlLintIssue(
                    file=rel, severity="error", rule="RCHK-008",
                    message="RTL must not use wait/fork/join",
                )
            )
    summary = {"files_checked": checked, "issues": len(issues)}
    status = "PASSED" if not issues else "FAILED"
    return RtlLintReport(
        status=status, tool="rnd_engine.rtl.checker",
        rules_checked=list(_RULES), issues=issues, summary=summary,
    )


# Last identifier of a (possibly defaulted) ANSI port item, tolerating
# unpacked array dims after the name: "input logic we [W_PORTS]".
_PORT_ITEM_RE = re.compile(r"([A-Za-z_]\w*)\s*(?:\[[^\]]*\]\s*)*(=[^,]*)?$")

_INSTANCE_RE = None  # replaced by _iter_instances (balanced-paren scanner)


def _iter_instances(src: str):
    """Yield ``(type, inst_name, line, params_body, conn_body)`` per instance.

    Handles both ``mod #(...) inst (...)`` and ``mod inst (...)`` forms. Uses
    balanced-paren scans (not one big regex) so the parameter body is never
    confused with the instance name.
    """
    for m in re.finditer(r"\b([A-Za-z_]\w*)\s*(#\s*\()?", src):
        typ = m.group(1)
        if typ in _SV_KEYWORDS:
            continue
        pos = m.end()
        params_body = ""
        if m.group(2):
            p_open = m.end(2) - 1
            p_close = _match_paren(src, p_open)
            if p_close == -1:
                continue
            params_body = src[p_open + 1 : p_close]
            pos = p_close + 1
        nm = re.match(r"\s*([A-Za-z_]\w*)\s*\(", src[pos:])
        if not nm:
            continue
        inst = nm.group(1)
        if inst in _SV_KEYWORDS:
            continue
        open_idx = pos + nm.end() - 1
        close_idx = _match_paren(src, open_idx)
        if close_idx == -1:
            continue
        line = src.count("\n", 0, m.start()) + 1
        yield typ, inst, line, params_body, src[open_idx + 1 : close_idx]


def _parse_module_header(text: str, pos: int) -> tuple[dict[str, bool], set[str]]:
    """Parse ``{port: has_default}`` and parameter names after 'module <name>'."""
    ports: dict[str, bool] = {}
    params: set[str] = set()
    n = len(text)
    i = pos
    while i < n and text[i].isspace():
        i += 1
    if i < n and text[i] == "#":
        j = text.find("(", i)
        if j == -1:
            return ports, params
        k = _match_paren(text, j)
        if k == -1:
            return ports, params
        for item in _split_top_level(text[j + 1 : k]):
            pm = re.match(r"parameter\s+(?:\w+\s+)?([A-Za-z_]\w*)", item)
            if pm:
                params.add(pm.group(1))
        i = k + 1
        while i < n and text[i].isspace():
            i += 1
    if i < n and text[i] == "(":
        k = _match_paren(text, i)
        if k == -1:
            return ports, params
        for item in _split_top_level(text[i + 1 : k]):
            pm = _PORT_ITEM_RE.search(item)
            if pm:
                ports[pm.group(1)] = pm.group(2) is not None
    return ports, params


def _scan_instance_wiring(
    sources: list[tuple[str, str]],
    definitions: dict[str, str],
    module_ports: dict[str, dict[str, bool]],
    module_params: dict[str, set[str]],
    issues: list[RtlLintIssue],
) -> int:
    """Scan every instantiation for wiring errors; return the instance count."""
    n_instances = 0
    for rel, src in sources:
        for typ, inst, line, params_body, body in _iter_instances(src):
            n_instances += 1

            conns = re.findall(r"\.\s*([A-Za-z_]\w*)\s*\(", body)
            seen: set[str] = set()
            for c in conns:
                if c in seen:
                    issues.append(
                        RtlLintIssue(
                            file=rel, line=line, severity="error",
                            rule="ELB-004",
                            message=(
                                f"instance '{inst}' of '{typ}' connects port "
                                f"'.{c}' more than once"
                            ),
                        )
                    )
                seen.add(c)

            if typ not in definitions:
                issues.append(
                    RtlLintIssue(
                        file=rel, line=line, severity="error", rule="ELB-001",
                        message=(
                            f"instance '{inst}' refers to module '{typ}' "
                            "which is not defined in the RTL tree"
                        ),
                    )
                )
                continue

            ports = module_ports[typ]
            for c in sorted(seen):
                if c not in ports:
                    issues.append(
                        RtlLintIssue(
                            file=rel, line=line, severity="error",
                            rule="ELB-002",
                            message=(
                                f"instance '{inst}' of '{typ}' connects "
                                f"'.{c}' but '{typ}' has no such port"
                            ),
                        )
                    )
            for pname, has_default in sorted(ports.items()):
                if not has_default and pname not in seen:
                    issues.append(
                        RtlLintIssue(
                            file=rel, line=line, severity="error",
                            rule="ELB-003",
                            message=(
                                f"instance '{inst}' of '{typ}' leaves "
                                f"required port '.{pname}' unconnected"
                            ),
                        )
                    )
            for po in sorted(set(re.findall(r"\.\s*([A-Za-z_]\w*)\s*\(", params_body))):
                if po not in module_params[typ]:
                    issues.append(
                        RtlLintIssue(
                            file=rel, line=line, severity="error",
                            rule="ELB-005",
                            message=(
                                f"instance '{inst}' of '{typ}' overrides "
                                f"parameter '.{po}' but '{typ}' has no "
                                "such parameter"
                            ),
                        )
                    )
    return n_instances


def elaboration_check(rtl_dir: str | Path) -> RtlLintReport:
    """Cross-check every instantiation against module definitions in the tree.

    Catches the wiring errors a structural wrapper can introduce: instances of
    modules that do not exist (ELB-001), connections to ports that do not
    exist (ELB-002), required (default-less) ports left unconnected
    (ELB-003), duplicate port connections (ELB-004), overrides of parameters
    that do not exist (ELB-005), and duplicate/missing 'top' definitions
    (ELB-006). Deliberately conservative — not a substitute for a real
    elaboration tool.
    """
    root = Path(rtl_dir)
    issues: list[RtlLintIssue] = []
    sv_files = sorted(p for p in root.rglob("*.sv") if p.is_file())

    sources: list[tuple[str, str]] = []
    definitions: dict[str, str] = {}
    module_ports: dict[str, dict[str, bool]] = {}
    module_params: dict[str, set[str]] = {}

    for path in sv_files:
        rel = str(path.relative_to(root)).replace("\\", "/")
        src = _blank_comments(path.read_text(encoding="utf-8"))
        sources.append((rel, src))
        for m in re.finditer(r"\bmodule\s+([A-Za-z_]\w*)", src):
            name = m.group(1)
            ports, params = _parse_module_header(src, m.end())
            if name in definitions:
                issues.append(
                    RtlLintIssue(
                        file=rel, line=src.count("\n", 0, m.start()) + 1,
                        severity="error", rule="ELB-006",
                        message=(
                            f"duplicate definition of module '{name}' "
                            f"(also defined in {definitions[name]})"
                        ),
                    )
                )
            else:
                definitions[name] = rel
                module_ports[name] = ports
                module_params[name] = params

    n_instances = _scan_instance_wiring(
        sources, definitions, module_ports, module_params, issues
    )

    if "top" not in definitions:
        issues.append(
            RtlLintIssue(
                file="-", severity="error", rule="ELB-006",
                message="no 'top' module found in the RTL tree",
            )
        )

    status = "PASSED" if not issues else "FAILED"
    return RtlLintReport(
        status=status, tool="rnd_engine.rtl.checker",
        rules_checked=list(ELABORATION_RULES), issues=issues,
        summary={
            "files_checked": len(sv_files),
            "modules": len(definitions),
            "instances": n_instances,
            "issues": len(issues),
        },
    )


def run_rtl_lint(rtl_dir: str | Path, tool: str = "verilator") -> RtlLintReport:
    """Run a real lint tool over the generated RTL when available.

    Returns BLOCKED with an explanatory report when the tool is missing.
    """
    available_tools = detect_tools()
    binary = available_tools.get(tool)
    root = Path(rtl_dir)
    sv_files = sorted(str(p) for p in root.rglob("*.sv") if p.is_file())
    if not binary:
        return RtlLintReport(
            status="BLOCKED", tool=tool,
            issues=[
                RtlLintIssue(
                    file="-", severity="info", rule="TOOL",
                    message=(
                        f"binary '{TOOL_BINARIES.get(tool)}' not found on PATH; "
                        "cannot lint — gate is BLOCKED, not PASSED"
                    ),
                )
            ],
            summary={"files": len(sv_files)},
        )
    cmd = [binary]
    if tool == "verilator":
        cmd += ["--lint-only", "--top-module", "top"]
    elif tool == "iverilog":
        cmd = ["iverilog", "-t", "null"]
    cmd += sv_files
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=False)
    combined = (proc.stderr or "") + "\n" + (proc.stdout or "")
    issues: list[RtlLintIssue] = []
    lines = [ln for ln in combined.splitlines() if ln.strip()]
    if proc.returncode != 0:
        for block in lines[:20]:
            issues.append(
                RtlLintIssue(file="-", severity="error", message=block, rule="TOOL")
            )
    return RtlLintReport(
        status="PASSED" if proc.returncode == 0 else "FAILED",
        tool=tool,
        tool_version=lines[0] if lines else None,
        issues=issues,
        summary={"exit_code": proc.returncode, "files": len(sv_files)},
    )


def write_lint_report(report: RtlLintReport, path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )