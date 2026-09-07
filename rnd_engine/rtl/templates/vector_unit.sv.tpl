// Parametrized element-wise vector unit. Generated only when the
// microarchitecture calls for a vector datapath.
module vector_unit #(
  parameter int WIDTH = 256,
  parameter int LANES = 8
) (
  input  logic                clk,
  input  logic                rst_n,
  input  logic                valid,
  input  logic [WIDTH-1:0]    a,
  input  logic [WIDTH-1:0]    b,
  input  logic [3:0]          op,
  output logic [WIDTH-1:0]    y,
  output logic                done
);
  localparam int ELEN = LANES > 0 ? WIDTH / LANES : WIDTH;
  logic [LANES*ELEN-1:0] acc;

  always_ff @(posedge clk) begin
    if (!rst_n) begin
      for (int l = 0; l < LANES; l++) acc[l*ELEN +: ELEN] <= {ELEN{1'b0}};
    end else if (valid) begin
      for (int l = 0; l < LANES; l++) begin
        case (op)
          4'h1: acc[l*ELEN +: ELEN] <= a[l*ELEN +: ELEN] + b[l*ELEN +: ELEN];
          4'h2: acc[l*ELEN +: ELEN] <= a[l*ELEN +: ELEN] - b[l*ELEN +: ELEN];
          4'h3: acc[l*ELEN +: ELEN] <= a[l*ELEN +: ELEN] & b[l*ELEN +: ELEN];
          4'h4: acc[l*ELEN +: ELEN] <= a[l*ELEN +: ELEN] | b[l*ELEN +: ELEN];
          default: acc[l*ELEN +: ELEN] <= a[l*ELEN +: ELEN];
        endcase
      end
    end
  end

  always_comb begin
    for (int l = 0; l < LANES; l++) y[l*ELEN +: ELEN] = acc[l*ELEN +: ELEN];
  end

  assign done = valid;
endmodule