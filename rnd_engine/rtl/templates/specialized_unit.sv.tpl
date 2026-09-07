// Sequential multiply-accumulate specialized unit. Generated only when the
// microarchitecture calls for specialized units.
module specialized_unit #(
  parameter int WIDTH = 32,
  parameter int TAPS  = 8
) (
  input  logic                clk,
  input  logic                rst_n,
  input  logic                valid,
  input  logic [WIDTH-1:0]    a,
  input  logic [WIDTH-1:0]    b,
  output logic [WIDTH*2-1:0]  acc,
  output logic                done
);
  logic [WIDTH*2-1:0] acc_r;

  always_ff @(posedge clk) begin
    if (!rst_n) begin
      acc_r <= {WIDTH*2{1'b0}};
    end else if (valid) begin
      acc_r <= acc_r + ($signed(a) * $signed(b));
    end
  end

  assign acc  = acc_r;
  assign done = valid;
endmodule