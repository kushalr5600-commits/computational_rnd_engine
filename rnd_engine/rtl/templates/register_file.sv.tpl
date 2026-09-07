// Parametrized RTL register file: W_PORTS synchronous write ports,
// R_PORTS combinational read ports. Last-write-wins on same-address writes.
module register_file #(
  parameter int WIDTH  = 32,
  parameter int DEPTH  = 32,
  parameter int R_PORTS = 2,
  parameter int W_PORTS = 1
) (
  input  logic                        clk,
  input  logic [W_PORTS-1:0] we,
  input  logic [W_PORTS*$clog2(DEPTH)-1:0] waddr,
  input  logic [W_PORTS*WIDTH-1:0] wdata,
  input  logic [R_PORTS*$clog2(DEPTH)-1:0] raddr,
  output logic [R_PORTS*WIDTH-1:0] rdata
);
  logic [DEPTH*WIDTH-1:0] mem;

  always_ff @(posedge clk) begin
    for (int p = 0; p < W_PORTS; p++) begin
      if (we[p]) mem[waddr[p*$clog2(DEPTH) +: $clog2(DEPTH)]] <= wdata[p*WIDTH +: WIDTH];
    end
  end

  always_comb begin
    for (int p = 0; p < R_PORTS; p++) begin
      rdata[p*WIDTH +: WIDTH] = mem[raddr[p*$clog2(DEPTH) +: $clog2(DEPTH)]];
    end
  end
endmodule