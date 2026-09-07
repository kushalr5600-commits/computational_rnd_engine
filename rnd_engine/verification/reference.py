"""Pure-Python reference model of the generated core (Phase E).

Instruction-level, in-order semantics that mirror the generated RTL exactly:

- instruction word ``[op 4b][rs1][rs2][rd]`` with ``LOG_REGS`` bits per reg
- every executed instruction writes ``rd`` EXCEPT ``OP_ST`` and ``OP_HAL`T``
  (the generated ``issue.sv`` clears ``wb_en`` for 4'h7 / 4'hf only) — in
  particular ``OP_NOP`` writes the ALU default ``a + b``, faithfully
- ``OP_LD`` reads a full ISA-width word at ``mem[rs1]``; ``OP_ST`` writes the
  full ``rs2`` word (the memory interface moves whole words)
- register file has no forced zero register (plain ``register_file`` template)
- execution stops retiring after ``OP_HALT``

Ops 4'h8 (VEC) / 4'h9 (MAC) depend on the generated vector / specialized unit
internals and are deliberately **out of reference scope** — tests do not use
them, and this limitation is stated rather than papered over.
"""

from __future__ import annotations

from .model import RefRunResult

OP_NOP = 0x0
OP_ADD = 0x1
OP_SUB = 0x2
OP_AND = 0x3
OP_OR = 0x4
OP_XOR = 0x5
OP_LD = 0x6
OP_ST = 0x7
OP_HALT = 0xF

# Ops with RTL-defined semantics the reference model implements.
REFERENCE_OPS = frozenset({OP_NOP, OP_ADD, OP_SUB, OP_AND, OP_OR, OP_XOR,
                           OP_LD, OP_ST, OP_HALT})
# Ops that never write back (mirrors issue.sv wb_en logic).
_NO_WB = frozenset({OP_ST, OP_HALT})

_ALU = {
    OP_ADD: lambda a, b: a + b,
    OP_SUB: lambda a, b: a - b,
    OP_AND: lambda a, b: a & b,
    OP_OR: lambda a, b: a | b,
    OP_XOR: lambda a, b: a ^ b,
    OP_NOP: lambda a, b: a + b,  # ALU default case, and it DOES write back
}


def encode_insn(op: int, rs1: int, rs2: int, rd: int, log_regs: int) -> str:
    """Encode one instruction word to hex in the generated decode layout."""
    word = (op & 0xF) | (rs1 << 4) | (rs2 << (4 + log_regs)) \
        | (rd << (4 + 2 * log_regs))
    width_bits = 4 + 3 * log_regs
    return f"{word:0{(width_bits + 3) // 4}x}"


class ReferenceModel:
    """Instruction-level golden model of one generated core configuration."""

    def __init__(self, isa_width: int, log_regs: int):
        if isa_width <= 0 or log_regs <= 0:
            raise ValueError("isa_width and log_regs must be positive")
        self.isa_width = isa_width
        self.log_regs = log_regs
        self._mask = (1 << isa_width) - 1
        self._regs = 1 << log_regs

    def run(
        self,
        program: list[str],
        init_memory: dict[int, int] | None = None,
        init_regs: dict[int, int] | None = None,
    ) -> RefRunResult:
        mem = {(int(k, 16) if isinstance(k, str) else int(k)): v & self._mask
               for k, v in (init_memory or {}).items()}
        regs = [0] * self._regs
        for idx, val in (init_regs or {}).items():
            regs[idx] = val & self._mask
        retired = 0
        halted = False
        for word_hex in program:
            if halted:
                break
            word = int(word_hex, 16)
            op = word & 0xF
            if op not in REFERENCE_OPS:
                raise ValueError(
                    f"op 0x{op:x} has no reference semantics (out of scope)"
                )
            rs1 = (word >> 4) & ((1 << self.log_regs) - 1)
            rs2 = (word >> (4 + self.log_regs)) & ((1 << self.log_regs) - 1)
            rd = (word >> (4 + 2 * self.log_regs)) & ((1 << self.log_regs) - 1)
            a, b = regs[rs1], regs[rs2]
            if op == OP_LD:
                regs[rd] = mem.get(a, 0) & self._mask
            elif op == OP_ST:
                mem[a & self._mask] = b
            elif op == OP_HALT:
                halted = True
            else:
                regs[rd] = _ALU[op](a, b) & self._mask
            retired += 1
        return RefRunResult(
            regs={f"x{i}": v for i, v in enumerate(regs) if v},
            memory={f"{a:x}": v for a, v in sorted(mem.items())},
            retired=retired,
            halted=halted,
        )
