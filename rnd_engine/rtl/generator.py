from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ..microarchitecture.model import MicroArchitectureSpec
from ..reproducibility import canonical_json_bytes
from .checker import (
    ELABORATION_RULES,
    STRUCTURAL_RULES,
    elaboration_check,
    run_rtl_lint,
    structural_check,
    write_lint_report,
)
from .model import RtlFileMeta, RtlManifest

RTL_SCHEMA_VERSION: int = 1
GENERATOR_VERSION: str = "1.0.0"

# Template directory lives next to this module.
_TEMPLATE_DIR = Path(__file__).with_name("templates")


# Contract an invalid/missing microarchitecture violates when lowered to RTL.
class RtlError(RuntimeError):
    """Raised when a microarchitecture cannot be deterministically lowered to RTL."""


def _log2_ceil(n: int) -> int:
    """Ceiling log2, floored at 1 so the smallest register file stays addressable."""
    return (n - 1).bit_length() if n > 1 else 1


def _datapaths_by_kind(micro: MicroArchitectureSpec) -> dict[str, Any]:
    by: dict[str, Any] = {}
    for dpath in micro.datapaths.datapaths:
        by.setdefault(dpath.kind, dpath)
    return by


def _build_params(micro: MicroArchitectureSpec) -> dict[str, Any]:
    """Derive every ``$VAR`` substitution for the templates from the spec.

    Deterministic: pure function of ``MicroArchitectureSpec`` fields. All
    values are integers except the identity/cadence strings baked into
    ``arch_pkg``.
    """
    by = _datapaths_by_kind(micro)
    stages = {s.name: s for s in micro.pipeline.stages}
    fetch_stage = micro.pipeline.stages[0]

    isa = by["alu"].width_bits if "alu" in by else int(fetch_stage.width_bits)
    issue = max(1, int(micro.datapaths.issue_width))
    exe = by["alu"].count if "alu" in by else issue
    reg_count = max(1, int(micro.datapaths.register_file_entries))
    log_regs = _log2_ceil(reg_count)
    instr_width = 4 + 3 * log_regs  # [op 4b][rs1][rs2][rd]

    vector = by.get("vector")
    tensor = by.get("tensor")
    specialized = by.get("specialized")
    vector_width = int(vector.width_bits) if vector else isa
    lanes = (
        int(vector.depth)
        if vector and vector.depth
        else (max(1, vector_width // isa) if vector else 1)
    )

    mem_stage = stages.get("memory")
    interconnect = (
        int(mem_stage.width_bits)
        if mem_stage
        else (int(micro.memories.controllers[0].width_bits) if micro.memories.controllers else isa)
    )
    caches = {c.name: c for c in micro.memories.caches}
    l1 = caches.get("l1")
    l2 = caches.get("l2")
    line_b = int(l1.line_bytes) if l1 else 32
    l1_sets = int(l1.sets) if l1 and l1.sets else 1
    l1_ways = int(l1.ways) if l1 and l1.ways else 1
    l2_sets = int(l2.sets) if l2 and l2.sets else 1
    l2_ways = int(l2.ways) if l2 and l2.ways else 1
    channels = int(micro.memories.controllers[0].channels) if micro.memories.controllers else 1

    line_words = max(1, (line_b * 8) // max(1, min(interconnect, isa)))
    sram_words = max(2, (int(l1.capacity_kb) * 1024) // max(1, isa // 8)) if l1 else 2
    sram_addr_w = _log2_ceil(sram_words)

    def _freq_mhz(domain_name: str) -> int:
        dom = next((d for d in micro.clock_reset.domains if d.name == domain_name), None)
        return round(dom.frequency_ghz * 1000) if dom else 0

    core_mhz = _freq_mhz("core")
    mem_mhz = _freq_mhz("memory")

    return {
        "DESIGN_ID": micro.design_id,
        "RTL_SCHEMA_VERSION": RTL_SCHEMA_VERSION,
        "GENERATOR_VERSION": GENERATOR_VERSION,
        "ISA_WIDTH": isa,
        "VECTOR_WIDTH": vector_width,
        "ISSUE_WIDTH": issue,
        "EXECUTION_UNITS": exe,
        "REG_COUNT": reg_count,
        "LOG_REGS": log_regs,
        "SLOTS": issue,
        "INSN_WIDTH": instr_width,
        "PC_WIDTH": 32,
        "IF_DEPTH": max(8, 1 << issue.bit_length()),
        "INTERCONNECT_WIDTH": interconnect,
        "CACHE_LINE_B": line_b,
        "MEM_CHANNELS": channels,
        "PARALLEL_LANES": lanes,
        "TENSOR_UNITS": int(tensor.count) if tensor else 0,
        "SPECIALIZED_UNITS": int(specialized.count) if specialized else 0,
        "L1_SETS": l1_sets,
        "L1_WAYS": l1_ways,
        "L2_SETS": l2_sets,
        "L2_WAYS": l2_ways,
        "LINE_WORDS": line_words,
        "SRAM_WORDS": sram_words,
        "SRAM_ADDR_W": sram_addr_w,
        "CORE_FREQ_MHZ": core_mhz,
        "MEM_FREQ_MHZ": mem_mhz,
    }
def _substitute(text: str, params: dict[str, Any]) -> str:
    for key, value in params.items():
        text = text.replace("$" + key, str(value))
    return text


def _render(name: str, params: dict[str, Any]) -> str:
    """Render one named ``.sv.tpl`` template with ``$VAR`` substitution."""
    path = _TEMPLATE_DIR / f"{name}.sv.tpl"
    if not path.exists():
        raise RtlError(f"Unknown RTL template: {name} (.sv.tpl missing)")
    return _substitute(path.read_text(encoding="utf-8"), params)


def _rom_cases(params: dict[str, Any], rom_words: int = 4) -> str:
    """Deterministic case body for the generated fetch instruction ROM.

    Exercises a short ADD chain ending in HALT so the flow-proving core has a
    bounded, halt-terminating program. Pure function of the params.
    """
    slots = int(params["SLOTS"])
    instr_w = int(params["INSN_WIDTH"])
    log = int(params["LOG_REGS"])
    hex_w = (instr_w + 3) // 4
    regs = 1 << log
    lines = []
    for w in range(rom_words):
        entries = []
        for j in range(slots):
            op = 0xF if (w == rom_words - 1 and j == slots - 1) else 0x1  # HALT / ADD
            rd = (j + w) % regs
            # Canonical decode.sv layout (low->high): [op 4][rs1 log][rs2 log][rd log].
            val = (op & 0xF) | (1 << 4) | (2 << (4 + log)) | (rd << (4 + 2 * log))
            entries.append(f"{instr_w}'h{val:0{hex_w}x}")
        lines.append(f"        {w}: rom_data = {{{', '.join(entries)}}};")
    return "\n".join(lines)
def _build_top(micro: MicroArchitectureSpec, params: dict[str, Any]) -> str:
    """Build the structural ``top.sv`` wiring the generated leaf modules.

    The top owns no sequential logic of its own — it only instantiates the
    clocked leaves (fetch/issue/register_file/units), so it stays RCHK-clean.
    Vector / specialized units are wired only when the architecture calls for
    them.
    """
    by = _datapaths_by_kind(micro)
    isa = int(params["ISA_WIDTH"])
    vec = int(params["VECTOR_WIDTH"])
    slots = int(params["SLOTS"])
    insn_w = int(params["INSN_WIDTH"])
    pc_w = int(params["PC_WIDTH"])
    log = int(params["LOG_REGS"])
    reg = int(params["REG_COUNT"])
    addr_w = int(params["SRAM_ADDR_W"])
    ifd = int(params["IF_DEPTH"])
    lanes = int(params["PARALLEL_LANES"])
    rd_p = 2
    has_vec = "vector" in by
    has_spec = any(k in ("tensor", "specialized") for k in by)

    L = []
    a = L.append
    a("// Generated top-level integration for the flow-proving core.")
    a("// Structural wrapper: no sequential logic of its own; all clocked state")
    a("// lives in the leaf modules (fetch / issue / register_file / units).")
    a("module top #(")
    a(f"  parameter int ISA    = {isa},")
    a(f"  parameter int VECTOR = {vec},")
    a(f"  parameter int SLOTS  = {slots},")
    a(f"  parameter int INSN_W = {insn_w},")
    a(f"  parameter int PC_W   = {pc_w},")
    a(f"  parameter int LOG_R  = {log},")
    a(f"  parameter int REG_C  = {reg},")
    a(f"  parameter int ADDR_W = {addr_w},")
    a(f"  parameter int IF_D   = {ifd},")
    a(f"  parameter int LANES  = {lanes},")
    a(f"  parameter int RD_P   = {rd_p}")
    a(") (")
    a("  input  logic                  clk,")
    a("  input  logic                  rst_n,")
    a("  input  logic                  mem_resp_valid,")
    a("  input  logic [ISA-1:0]        mem_resp_rdata,")
    a("  output logic                  mem_req_valid,")
    a("  output logic                  mem_req_we,")
    a("  output logic [ADDR_W-1:0]     mem_req_addr,")
    a("  output logic [ISA-1:0]        mem_req_wdata,")
    a("  output logic                  halt")
    a(");")
    a("")
    a("  localparam int IF_PORTS = RD_P * SLOTS;")
    a("")
    a("  // ---- fetch ----")
    a("  logic [PC_W-1:0]            pc;")
    a("  logic [SLOTS-1:0]           insn_valid;")
    a("  logic [SLOTS*INSN_W-1:0]    insn;")
    a("  logic                       stall_fetch;")
    a("  logic                       halt_c;")
    a("  fetch #(")
    a("    .SLOTS(SLOTS), .INSN_WIDTH(INSN_W), .PC_WIDTH(PC_W)")
    a("  ) fetch_u (")
    a("    .clk(clk), .rst_n(rst_n), .stall(stall_fetch), .halt(halt_c),")
    a("    .pc(pc), .insn_valid(insn_valid), .insn(insn)")
    a("  );")
    a("")
    a("  // ---- decode ----")
    a("  logic [SLOTS-1:0]            dec_valid;")
    a("  logic [SLOTS*4-1:0]          dec_op;")
    a("  logic [SLOTS*LOG_R-1:0]      dec_rs1, dec_rs2, dec_rd;")
    a("  logic [SLOTS-1:0]            dec_is_mem, dec_is_halt;")
    a("  decode #(")
    a("    .SLOTS(SLOTS), .INSN_WIDTH(INSN_W), .LOG_REGS(LOG_R)")
    a("  ) decode_u (")
    a("    .insn_valid(insn_valid), .insn(insn),")
    a("    .valid(dec_valid), .op(dec_op), .rs1(dec_rs1), .rs2(dec_rs2), .rd(dec_rd),")
    a("    .is_mem(dec_is_mem), .is_halt(dec_is_halt)")
    a("  );")
    a("")
    a("  // ---- issue / retire + register file ----")
    a("  logic [IF_PORTS*ISA-1:0]        rf_rdata;")
    a("  logic [IF_PORTS*LOG_R-1:0]      rf_raddr;")
    a("  logic                      rf_we;")
    a("  logic [LOG_R-1:0]          rf_waddr;")
    a("  logic [ISA-1:0]            rf_wdata;")
    a("  logic                      head_drive_valid;")
    a("  logic [3:0]                head_op;")
    a("  logic [ISA-1:0]            head_opa, head_opb;")
    a("  logic [ISA-1:0]            alu_y, vec_y, mac_acc;")
    a("")
    a("  issue #(")
    a("    .SLOTS(SLOTS), .LOG_REGS(LOG_R), .ISA_WIDTH(ISA), .PC_WIDTH(PC_W),")
    a("    .ADDR_W(ADDR_W), .IF_DEPTH(IF_D), .RD_PORTS(RD_P)")
    a("  ) issue_u (")
    a("    .clk(clk), .rst_n(rst_n),")
    a("    .dec_valid(dec_valid), .dec_op(dec_op), .dec_rs1(dec_rs1), .dec_rs2(dec_rs2), .dec_rd(dec_rd),")
    a("    .dec_pc(pc),")
    a("    .rf_rdata(rf_rdata), .rf_raddr(rf_raddr),")
    a("    .rf_we(rf_we), .rf_waddr(rf_waddr), .rf_wdata(rf_wdata),")
    a("    .mem_resp_valid(mem_resp_valid), .mem_resp_rdata(mem_resp_rdata),")
    a("    .mem_req_valid(mem_req_valid), .mem_req_we(mem_req_we),")
    a("    .mem_req_addr(mem_req_addr), .mem_req_wdata(mem_req_wdata),")
    a("    .alu_y(alu_y), .vec_y(vec_y), .mac_acc(mac_acc),")
    a("    .head_op(head_op), .head_opa(head_opa), .head_opb(head_opb),")
    a("    .head_drive_valid(head_drive_valid),")
    a("    .stall_fetch(stall_fetch), .halt(halt_c)")
    a("  );")
    a("")
    a("  logic [1-1:0] we_1;")
    a("  logic [1*LOG_R-1:0]            waddr_1;")
    a("  logic [1*ISA-1:0]              wdata_1;")
    a("  assign we_1[0]    = rf_we;")
    a("  assign waddr_1[(0)*LOG_R +: LOG_R] = rf_waddr;")
    a("  assign wdata_1[(0)*ISA +: ISA] = rf_wdata;")
    a("  register_file #(")
    a("    .WIDTH(ISA), .DEPTH(REG_C), .R_PORTS(IF_PORTS), .W_PORTS(1)")
    a("  ) register_file_u (")
    a("    .clk(clk), .we(we_1), .waddr(waddr_1), .wdata(wdata_1),")
    a("    .raddr(rf_raddr), .rdata(rf_rdata)")
    a("  );")
    a("")
    a("  // ---- datapath ----")
    a("  alu #(.WIDTH(ISA)) alu_u (")
    a("    .a(head_opa), .b(head_opb), .op(head_op), .y(alu_y)")
    a("  );")
    if has_vec:
        a("  logic [VECTOR-1:0]         vec_y_wide;")
        a("  vector_unit #(.WIDTH(VECTOR), .LANES(LANES)) vector_unit_u (")
        a("    .clk(clk), .rst_n(rst_n), .valid(head_drive_valid),")
        a("    .a(head_opa), .b(head_opb), .op(head_op), .y(vec_y_wide), .done()")
        a("  );")
        a("  assign vec_y = vec_y_wide[ISA-1:0];")
    else:
        a("  assign vec_y = {ISA{1'b0}};")
    if has_spec:
        a("  logic [2*ISA-1:0]          mac_acc_wide;")
        a("  specialized_unit #(.WIDTH(ISA), .TAPS(8)) specialized_unit_u (")
        a("    .clk(clk), .rst_n(rst_n), .valid(head_drive_valid),")
        a("    .a(head_opa), .b(head_opb), .acc(mac_acc_wide), .done()")
        a("  );")
        a("  assign mac_acc = mac_acc_wide[ISA-1:0];")
    else:
        a("  assign mac_acc = {ISA{1'b0}};")
    a("")
    a("  assign halt = halt_c;")
    a("")
    a("endmodule")
    return "\n".join(L) + "\n"
def _module_files(micro: MicroArchitectureSpec, params: dict[str, Any]) -> dict[str, str]:
    """Render the exact module set the design requires, in stable order.

    Vector / specialized (incl. tensor, which flows to the specialized-unit
    path) modules are emitted only when the microarchitecture calls for them —
    nothing is generated that the design does not use.
    """
    by = _datapaths_by_kind(micro)
    files: dict[str, str] = {}
    files["arch_pkg"] = _render("arch_pkg", params)
    files["alu"] = _render("alu", params)
    files["fetch"] = _render("fetch", {**params, "ROM_CASES": _rom_cases(params)})
    files["decode"] = _render("decode", params)
    files["issue"] = _render("issue", params)
    files["register_file"] = _render("register_file", params)
    if "vector" in by:
        files["vector_unit"] = _render("vector_unit", params)
    if any(k in ("tensor", "specialized") for k in by):
        files["specialized_unit"] = _render("specialized_unit", params)
    files["top"] = _build_top(micro, params)
    return files


def _filelist(design_id: str, files: dict[str, str]) -> str:
    lines = [f"// Generated file list for design {design_id}"]
    lines += [f"{name}.sv" for name in files]
    return "\n".join(lines) + "\n"


def _build_architecture_hash(metas: list[RtlFileMeta]) -> str:
    """Content-addressed build digest over the emitted file set."""
    payload = {
        "rtl_schema_version": RTL_SCHEMA_VERSION,
        "files": [{"path": m.path, "sha256": m.sha256} for m in metas],
    }
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()[:32]


def _gates_manifest() -> dict[str, Any]:
    """Static description of the RTL quality gates and their status rules.

    Written to ``verification/lint/gates.json`` alongside every build so the
    gate configuration is inspectable without reading Python source. Gates that
    require an external tool are declared with ``status_when_missing: BLOCKED``
    — the flow never upgrades a missing tool to PASS.
    """
    return {
        "gates": [
            {
                "name": "structural",
                "tool": "rnd_engine.rtl.checker",
                "rules": STRUCTURAL_RULES,
                "runs_without_tool": True,
            },
            {
                "name": "elaboration",
                "tool": "rnd_engine.rtl.checker",
                "rules": ELABORATION_RULES,
                "runs_without_tool": True,
            },
            {
                "name": "lint_verilator",
                "tool": "verilator",
                "runs_without_tool": False,
                "status_when_missing": "BLOCKED",
            },
            {
                "name": "lint_iverilog",
                "tool": "iverilog",
                "runs_without_tool": False,
                "status_when_missing": "BLOCKED",
            },
        ],
        "status_vocabulary": ["PASSED", "FAILED", "BLOCKED", "NOT_RUN"],
    }


def _json_dumps(value: dict[str, Any]) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def rtl_directory(out_dir: str | Path, design_id: str) -> Path:
    """Return the on-disk RTL tree root for a design id."""
    return Path(out_dir) / "rtl" / design_id


def rtl_file_hash(path: str | Path) -> str:
    """Content SHA-256 (full) of one generated RTL file."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def generate_rtl(micro: MicroArchitectureSpec, out_dir: str | Path = "artifacts") -> RtlManifest:
    """Deterministically lower a microarchitecture to synthesizable SystemVerilog.

    Writes the module files, a filelist, the structural lint report and (when a
    lint tool is installed) its report, then returns the ``RtlManifest`` binding
    the RTL to the design/spec/microarchitecture it was generated from. Same
    microarchitecture -> byte-identical RTL tree + identical manifest.
    """
    if not micro.design_id:
        raise RtlError("MicroArchitectureSpec has no design_id.")

    params = _build_params(micro)
    files = _module_files(micro, params)
    rtl_dir = rtl_directory(out_dir, micro.design_id)
    rtl_dir.mkdir(parents=True, exist_ok=True)

    metas: list[RtlFileMeta] = []
    for name, content in files.items():
        path = rtl_dir / f"{name}.sv"
        path.write_text(content, encoding="utf-8")
        metas.append(RtlFileMeta(path=f"{name}.sv", sha256=rtl_file_hash(path)))

    filelist_path = rtl_dir / "filelist.f"
    filelist_path.write_text(_filelist(micro.design_id, files), encoding="utf-8")
    metas.append(RtlFileMeta(path="filelist.f", sha256=rtl_file_hash(filelist_path)))

    # Gate 1: pure-Python structural + elaboration checks (no tool needed).
    structural = structural_check(rtl_dir)
    elaboration = elaboration_check(rtl_dir)
    reports_dir = Path(out_dir) / "reports" / "lint" / micro.design_id
    write_lint_report(structural, reports_dir / "lint_structural.json")
    write_lint_report(elaboration, reports_dir / "lint_elaboration.json")

    # Gate 2: real lint tools — honestly BLOCKED when the binary is missing.
    tool_status: dict[str, str] = {}
    for tool in ("verilator", "iverilog"):
        report = run_rtl_lint(rtl_dir, tool=tool)
        if report.status != "NOT_RUN":
            write_lint_report(report, reports_dir / f"lint_{tool}.json")
            tool_status[tool] = report.status

    # Gate configuration manifest (design-independent, deterministic).
    verification_dir = Path(out_dir) / "verification" / "lint"
    verification_dir.mkdir(parents=True, exist_ok=True)
    (verification_dir / "gates.json").write_text(
        _json_dumps(_gates_manifest()), encoding="utf-8"
    )

    manifest = RtlManifest(
        design_id=micro.design_id,
        architecture_schema_version=micro.architecture_schema_version,
        specification_hash=micro.specification_hash,
        microarchitecture_hash=hashlib.sha256(
            canonical_json_bytes(micro.model_dump(mode="json"))
        ).hexdigest()[:32],
        rtl_schema_version=RTL_SCHEMA_VERSION,
        generator_version=GENERATOR_VERSION,
        architecture_hash=_build_architecture_hash(metas),
        files=metas,
        provenance={
            **(micro.provenance or {}),
            "rtl_schema_version": RTL_SCHEMA_VERSION,
            "structural_check": structural.status,
            "elaboration_check": elaboration.status,
            "lint_tools": tool_status,
        },
    )
    (rtl_dir / "manifest.json").write_text(_json_dumps(manifest.model_dump(mode="json")), encoding="utf-8")
    return manifest