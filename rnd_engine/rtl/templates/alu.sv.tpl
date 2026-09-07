// Parametrized combinational ALU. op codes follow arch_pkg OP_* values.
module alu #(
  parameter int WIDTH = 32
) (
  input  logic [WIDTH-1:0] a,
  input  logic [WIDTH-1:0] b,
  input  logic [3:0]       op,
  output logic [WIDTH-1:0] y
);
  always_comb begin
    case (op)
      4'h1:    y = a + b;
      4'h2:    y = a - b;
      4'h3:    y = a & b;
      4'h4:    y = a | b;
      4'h5:    y = a ^ b;
      default: y = a + b;
    endcase
  end
endmodule