// Combinational decode: slice the generated instruction word.
// Layout: [op 4b][rs1 logb][rs2 logb][rd logb]
module decode #(
  parameter int SLOTS      = 1,
  parameter int INSN_WIDTH = 16,
  parameter int LOG_REGS   = 4
) (
  input  logic [SLOTS-1:0]                    insn_valid,
  input  logic [SLOTS*INSN_WIDTH-1:0]         insn,
  output logic [SLOTS-1:0]                    valid,
  output logic [SLOTS*(3+1)-1:0] op,
  output logic [SLOTS*LOG_REGS-1:0] rs1,
  output logic [SLOTS*LOG_REGS-1:0] rs2,
  output logic [SLOTS*LOG_REGS-1:0] rd,
  output logic [SLOTS-1:0]                    is_mem,
  output logic [SLOTS-1:0]                    is_halt
);
  genvar s;
  for (s = 0; s < SLOTS; s++) begin : dec_slot
    wire [3:0]           op_w   = insn[s*INSN_WIDTH +: 4];
    wire [LOG_REGS-1:0]  rs1_w  = insn[s*INSN_WIDTH + 4 +: LOG_REGS];
    wire [LOG_REGS-1:0]  rs2_w  = insn[s*INSN_WIDTH + 4 + LOG_REGS +: LOG_REGS];
    wire [LOG_REGS-1:0]  rd_w   = insn[s*INSN_WIDTH + 4 + 2*LOG_REGS +: LOG_REGS];

    assign valid[s]   = insn_valid[s];
    assign op[s*(3+1) +: (3+1)]    = op_w;
    assign rs1[s*LOG_REGS +: LOG_REGS]   = rs1_w;
    assign rs2[s*LOG_REGS +: LOG_REGS]   = rs2_w;
    assign rd[s*LOG_REGS +: LOG_REGS]    = rd_w;
    assign is_mem[s]  = (op_w[3:0] == 4'h6) || (op_w[3:0] == 4'h7); // OP_LD / OP_ST
    assign is_halt[s] = (op_w[3:0] == 4'hf);
  end
endmodule