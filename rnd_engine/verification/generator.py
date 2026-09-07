"""Verification artifact generation + functional gates (Phase E, toolless scope).

Produces, deterministically from the microarchitecture + RTL manifest:

- directed test cases with hand-computed expectations (``tests.json``)
- a SystemVerilog testbench for the generated ``top`` (``tb_top.sv``)
- SVA formal properties (``verification/formal/<id>/properties.sva``)
- gate reports: the reference-model gate actually RUNS here (pure Python);
  simulation and formal gates are honestly **BLOCKED** — no simulator or
  formal engine is installed, and neither gate can ever claim PASS without one.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ..microarchitecture.model import MicroArchitectureSpec
from ..rtl.checker import write_lint_report
from ..rtl.model import RtlLintIssue, RtlLintReport, RtlManifest
from .model import RtlTestCase, VerificationManifest
from .reference import (
    OP_ADD,
    OP_AND,
    OP_HALT,
    OP_LD,
    OP_NOP,
    OP_OR,
    OP_ST,
    OP_SUB,
    OP_XOR,
    ReferenceModel,
    encode_insn,
)

VERIFICATION_SCHEMA_VERSION: int = 1
GENERATOR_VERSION: str = "1.0.0"

REFERENCE_MODEL_RULES = ["REF-001", "REF-002", "REF-003"]


class VerificationError(RuntimeError):
    """Raised when verification artifacts cannot be generated or gates fail."""


# --- directed tests ---------------------------------------------------------

def _directed_tests(params: dict[str, Any]) -> list[RtlTestCase]:
    """Directed programs with literally-written expected final state.

    Every expectation is arithmetic written out by hand at construction time —
    the reference model is *compared against* these numbers, it never produces
    them.
    """
    log = int(params["LOG_REGS"])
    isa = int(params["ISA_WIDTH"])
    mask = (1 << isa) - 1
    tests: list[RtlTestCase] = []

    def t(name: str, desc: str, prog: list[str], exp_regs: dict[int, int],
          exp_mem: dict[int, int] | None = None,
          init_mem: dict[int, int] | None = None,
          retired: int | None = None,
          init_regs: dict[int, int] | None = None) -> None:
        tests.append(RtlTestCase(
            name=name,
            description=desc,
            log_regs=log,
            isa_width=isa,
            program=prog,
            init_memory={f"{a:x}": v for a, v in (init_mem or {}).items()},
            init_regs={str(i): v & mask for i, v in (init_regs or {}).items()},
            expected_regs={f"x{i}": v & mask for i, v in exp_regs.items() if v & mask},
            expected_memory={f"{a:x}": v & mask for a, v in (exp_mem or {}).items()},
            expected_retired=len(prog) if retired is None else retired,
            expected_halted=True,
        ))

    e = lambda op, a, b, d: encode_insn(op, a, b, d, log)

    # REF-001: every ALU op on distinct fixed operands
    t("alu_ops", "ADD/SUB/AND/OR/XOR on fixed operands into r3..r7",
      [e(OP_ADD, 1, 2, 3), e(OP_SUB, 1, 2, 4), e(OP_AND, 1, 2, 5),
       e(OP_OR, 1, 2, 6), e(OP_XOR, 1, 2, 7), e(OP_HALT, 0, 0, 0)],
      {1: 0xA5, 2: 0x3C, 3: 0xA5 + 0x3C, 4: 0xA5 - 0x3C,
       5: 0xA5 & 0x3C, 6: 0xA5 | 0x3C, 7: 0xA5 ^ 0x3C},
      init_regs={1: 0xA5, 2: 0x3C})

    # REF-002: store-then-load round trip. No immediates exist, so r1 is
    # seeded by LD from init memory (word 0 holds 8), then doubled twice -> 32.
    t("mem_roundtrip", "r1=8 via LD; double to 32; ST r1->[0x20]; LD ->r2",
      [e(OP_LD, 0, 0, 1),                       # r1 = mem[0] = 8
       e(OP_ADD, 1, 1, 1), e(OP_ADD, 1, 1, 1),  # r1 = 16, 32
       e(OP_ST, 1, 1, 0),                       # mem[r1=32] = r1 = 32
       e(OP_LD, 1, 0, 2),                       # r2 = mem[32] = 32
       e(OP_HALT, 0, 0, 0)],
      {1: 0x20, 2: 0x20},
      exp_mem={0x20: 0x20},
      init_mem={0: 8},
      init_regs={1: 0x20})

    # REF-003: HALT retires and stops the machine; trailing insn never runs
    t("halt_stops", "HALT retires and freezes; trailing ADD never runs",
      [e(OP_ADD, 1, 1, 2), e(OP_HALT, 0, 0, 0), e(OP_ADD, 2, 2, 3)],
      {1: 0x7, 2: 0xE}, None, None, retired=2, init_regs={1: 0x7})

    # REF-004: NOP writes the ALU default a+b (matches issue.sv wb_en logic)
    t("nop_writes", "NOP writes rd = rs1 + rs2 (ALU default case)",
      [e(OP_NOP, 3, 4, 5), e(OP_HALT, 0, 0, 0)],
      {3: 0x2, 4: 0x3, 5: 0x5}, init_regs={3: 0x2, 4: 0x3})

    # REF-005: arithmetic wraps at ISA width
    t("wrap", f"ADD wraps modulo 2^{isa}",
      [e(OP_ADD, 1, 2, 3), e(OP_HALT, 0, 0, 0)],
      {1: mask, 2: 0x1, 3: (mask + 1) & mask},
      init_regs={1: mask, 2: 0x1})
    return tests

# --- gates ------------------------------------------------------------------

def run_reference_gate(
    tests: list[RtlTestCase],
) -> tuple[RtlLintReport, list[dict[str, Any]]]:
    """Execute every directed test on the reference model; compare to expected."""
    issues: list[RtlLintIssue] = []
    results: list[dict[str, Any]] = []
    for tc in tests:
        model = ReferenceModel(tc.isa_width, tc.log_regs)
        try:
            got = model.run(
                tc.program, tc.init_memory,
                {int(k): v for k, v in tc.init_regs.items()})
        except ValueError as exc:
            issues.append(RtlLintIssue(
                file="-", rule="REF-003", severity="error",
                message=f"test {tc.name}: {exc}"))
            results.append({"test": tc.name, "status": "FAILED", "reason": str(exc)})
            continue
        failures: list[str] = []
        if got.retired != tc.expected_retired:
            failures.append(f"retired {got.retired} != {tc.expected_retired}")
        if got.halted != tc.expected_halted:
            failures.append(f"halted {got.halted} != {tc.expected_halted}")
        for reg, want in tc.expected_regs.items():
            if got.regs.get(reg, 0) != want:
                failures.append(f"{reg}={got.regs.get(reg, 0)} != {want}")
        for addr, want in tc.expected_memory.items():
            if got.memory.get(addr, 0) != want:
                failures.append(f"mem[{addr}]={got.memory.get(addr, 0)} != {want}")
        if failures:
            issues.append(RtlLintIssue(
                file="-", rule="REF-002", severity="error",
                message=f"test {tc.name}: " + "; ".join(failures)))
            results.append({"test": tc.name, "status": "FAILED",
                            "failures": failures})
        else:
            results.append({"test": tc.name, "status": "PASSED"})
    status = "PASSED" if not issues else "FAILED"
    return RtlLintReport(
        status=status, tool="reference-model (pure python)",
        rules_checked=REFERENCE_MODEL_RULES, issues=issues,
        summary={"tests": len(tests),
                 "passed": sum(r["status"] == "PASSED" for r in results)},
    ), results


def _blocked_report(gate: str, reason: str) -> RtlLintReport:
    return RtlLintReport(
        status="BLOCKED", tool=gate,
        issues=[RtlLintIssue(
            file="-", severity="info", rule="TOOL",
            message=f"{reason} — gate is BLOCKED, never PASS")],
    )

# --- artifact rendering -----------------------------------------------------

def _testbench_sva(micro: MicroArchitectureSpec, params: dict[str, Any]) -> tuple[str, str]:
    """Render the (not-runnable-here) testbench + formal property files."""
    did = micro.design_id
    isa = int(params["ISA_WIDTH"])
    slots = int(params["SLOTS"])
    insn_w = int(params["INSN_WIDTH"])
    pc_w = int(params["PC_WIDTH"])
    addr_w = int(params["SRAM_ADDR_W"])
    log = int(params["LOG_REGS"])
    reg = int(params["REG_COUNT"])
    ifd = int(params["IF_DEPTH"])
    lanes = int(params["PARALLEL_LANES"])
    vec = int(params["VECTOR_WIDTH"])
    tb = f"""// Generated simulation testbench for design {did} (Phase E).
`timescale 1ns/1ps
module tb_top;
  parameter int ISA   = {isa};
  parameter int ADDR_W = {addr_w};
  logic clk = 0, rst_n = 0;
  logic mem_resp_valid = 0;
  logic [ISA-1:0] mem_resp_rdata = '0;
  logic mem_req_valid, mem_req_we;
  logic [ADDR_W-1:0] mem_req_addr;
  logic [ISA-1:0] mem_req_wdata;
  logic halt;

  always #5 clk = ~clk;

  top #(.ISA({isa}), .VECTOR({vec}), .SLOTS({slots}), .INSN_W({insn_w}),
        .PC_W({pc_w}), .LOG_R({log}), .REG_C({reg}),
        .ADDR_W({addr_w}), .IF_D({ifd}), .LANES({lanes})) dut (.*);

  // word memory backed by the directed test images
  logic [ISA-1:0] mem [1<<ADDR_W];
  initial begin
    // $readmemh("memory.hex", mem); // supplied by the harness per test
    repeat (4) @(posedge clk);
    rst_n = 1;
  end

  // simple responder: 1-cycle read latency, write-through
  always @(posedge clk) begin
    mem_resp_valid <= 1'b0;
    if (mem_req_valid && !mem_req_we) begin
      mem_resp_rdata <= mem[mem_req_addr];
      mem_resp_valid <= 1'b1;
    end else if (mem_req_valid) begin
      mem[mem_req_addr] <= mem_req_wdata;
    end
  end

  initial begin
    wait (halt);
    repeat (4) @(posedge clk);
    $display("TB: halt observed");
    $finish;
  end
endmodule
"""
    props = f"""// Generated formal properties for design {did} (Phase E).
// BMC wrapper: instantiates the real DUT; clk/rst_n/mem inputs are free.
module formal_properties (
  input logic                clk,
  input logic                rst_n,
  input logic                mem_resp_valid,
  input logic [ISA-1:0]      mem_resp_rdata
);
  localparam int ISA   = {isa};
  localparam int ADDR_W = {addr_w};

  logic mem_req_valid, mem_req_we;
  logic [ADDR_W-1:0]         mem_req_addr;
  logic [ISA-1:0]            mem_req_wdata;
  logic halt;

  top #(.ISA({isa}), .VECTOR({vec}), .SLOTS({slots}), .INSN_W({insn_w}),
        .PC_W({pc_w}), .LOG_R({log}), .REG_C({reg}),
        .ADDR_W({addr_w}), .IF_D({ifd}), .LANES({lanes})) dut (
    .clk(clk), .rst_n(rst_n),
    .mem_resp_valid(mem_resp_valid), .mem_resp_rdata(mem_resp_rdata),
    .mem_req_valid(mem_req_valid), .mem_req_we(mem_req_we),
    .mem_req_addr(mem_req_addr), .mem_req_wdata(mem_req_wdata),
    .halt(halt)
  );

  // Yosys-formal style: immediate assertions clocked by the always block.
  always @(posedge clk) begin
    // P1: reset drives halt low on the cycle after reset release
    p_reset_no_halt: assert (!$past(rst_n) || !halt);
    // P2: no request is issued after halt
    p_quiet_after_halt: assert (!halt || !mem_req_valid);
    // P3: writes are always accompanied by a request
    p_write_needs_req: assert (!mem_req_we || mem_req_valid);
  end
endmodule
"""
    return tb, props

# --- entry point ------------------------------------------------------------

def _rtl_params(micro: MicroArchitectureSpec) -> dict[str, Any]:
    """Recompute the RTL generation params (local import avoids a cycle)."""
    from ..rtl.generator import _build_params

    return _build_params(micro)


def generate_verification(
    micro: MicroArchitectureSpec,
    rtl_manifest: RtlManifest,
    out_dir: str | Path = "artifacts",
) -> VerificationManifest:
    """Deterministically produce Phase E verification artifacts + gate reports."""
    if not micro.design_id:
        raise VerificationError("MicroArchitectureSpec has no design_id.")
    if rtl_manifest.design_id != micro.design_id:
        raise VerificationError(
            f"RTL manifest design {rtl_manifest.design_id} != {micro.design_id}")

    params = _rtl_params(micro)
    tests = _directed_tests(params)
    ref_report, results = run_reference_gate(tests)

    artifacts_dir = Path(out_dir) / "verification" / micro.design_id
    formal_dir = Path(out_dir) / "verification" / "formal" / micro.design_id
    reports_dir = Path(out_dir) / "reports" / "verification" / micro.design_id
    for d in (artifacts_dir, formal_dir, reports_dir):
        d.mkdir(parents=True, exist_ok=True)

    tb, props = _testbench_sva(micro, params)
    tb_path = artifacts_dir / "tb_top.sv"
    tb_path.write_text(tb, encoding="utf-8")
    (formal_dir / "properties.sva").write_text(props, encoding="utf-8")

    tests_payload = {
        "design_id": micro.design_id,
        "rtl_architecture_hash": rtl_manifest.architecture_hash,
        "tests": [tc.model_dump(mode="json") for tc in tests],
        "reference_results": results,
    }
    (artifacts_dir / "tests.json").write_text(
        json.dumps(tests_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    write_lint_report(ref_report, reports_dir / "reference_model.json")
    sim = _blocked_report(
        "simulation",
        "no simulator (verilator/iverilog) installed; tb_top.sv was never run")
    write_lint_report(sim, reports_dir / "simulation.json")
    formal = _blocked_report(
        "formal",
        "no formal engine (SymbiYosys/JasperGold) installed; properties.sva never proven")
    write_lint_report(formal, reports_dir / "formal.json")

    gates = {
        "design_id": micro.design_id,
        "rtl_architecture_hash": rtl_manifest.architecture_hash,
        "gates": {
            "reference_model": {"status": ref_report.status,
                                "rules": REFERENCE_MODEL_RULES},
            "simulation": {"status": sim.status,
                           "status_when_missing": "BLOCKED"},
            "formal": {"status": formal.status,
                       "status_when_missing": "BLOCKED"},
        },
    }
    (reports_dir / "gates.json").write_text(
        json.dumps(gates, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    manifest = VerificationManifest(
        design_id=micro.design_id,
        rtl_architecture_hash=rtl_manifest.architecture_hash,
        verification_schema_version=VERIFICATION_SCHEMA_VERSION,
        generator_version=GENERATOR_VERSION,
        tests=tests,
        provenance={
            **(micro.provenance or {}),
            "reference_model": ref_report.status,
            "simulation": sim.status,
            "formal": formal.status,
            "tb_top_sha256": hashlib.sha256(tb_path.read_bytes()).hexdigest(),
        },
    )
    (artifacts_dir / "manifest.json").write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    return manifest