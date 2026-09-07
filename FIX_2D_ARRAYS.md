# RTL 2D-ARRAY FIX — EXECUTE NEXT TURN, NO MORE DISCOVERY
#
# GOAL: Replace 2D packed arrays (Yosys-0.38/iverilog incompatible) with flat 1D.
#
# KNOWN SITES (rnd_engine/rtl/generator.py):
#   1. Top-module declarations, lines ~233-234: two `logic [SLOTS-1:0][3:0] dec_*` signals
#   2. Decode module port emission: `output logic [SLOTS-1:0][3:0] op` (and matching we port)
#
# FIX PATTERN:
#   Declaration:  logic [SLOTS-1:0][3:0] X  ->  logic [SLOTS*W-1:0] X   (W=operand width, e.g. 4)
#   Port:         output logic [SLOTS-1:0][3:0] op -> output logic [SLOTS*4-1:0] op
#   Assignment:   X[s] = value  ->  X[s*W +: W]
#   Read:         X[s]  ->  X[s*W +: W]
#   Connection:   .op(op) stays identical (flat both sides)
#
# AFTER EDIT:
#   pytest tests -q            (must stay green, esp. tests/test_rtl.py)
#   regenerate candidate, rerun lint -> simulation -> synthesis in container
#
# STATUS: declaration lines located at 233-234; consumer grep done this turn.
