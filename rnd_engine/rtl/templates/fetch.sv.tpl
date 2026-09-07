// Fetch stage with deterministic generated instruction ROM.
module fetch #(
  parameter int SLOTS       = 1,
  parameter int INSN_WIDTH  = 16,
  parameter int PC_WIDTH    = 32,
  parameter int ROM_WORDS   = 8
) (
  input  logic                            clk,
  input  logic                            rst_n,
  input  logic                            stall,
  input  logic                            halt,
  output logic [PC_WIDTH-1:0]             pc,
  output logic [SLOTS-1:0]                insn_valid,
  output logic [SLOTS*INSN_WIDTH-1:0]     insn
);
  logic [PC_WIDTH-1:0] pc_r;

  always_ff @(posedge clk) begin
    if (!rst_n) begin
      pc_r <= {PC_WIDTH{1'b0}};
    end else if (halt) begin
      pc_r <= pc_r;
    end else if (!stall) begin
      pc_r <= pc_r + 1'b1;
    end
  end

  assign pc = pc_r;

  logic [SLOTS*INSN_WIDTH-1:0] rom_data;
  always_comb begin
    case (pc % ROM_WORDS)
$ROM_CASES
      default: rom_data = {SLOTS*INSN_WIDTH{1'b0}};
    endcase
  end

  assign insn       = rom_data;
  assign insn_valid = {SLOTS{1'b1}};
endmodule