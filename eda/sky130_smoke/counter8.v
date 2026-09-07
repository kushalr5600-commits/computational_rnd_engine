module counter8 (
  input  wire clk,
  input  wire rstn,
  input  wire en,
  output wire [7:0] q,
  output wire hit
);
  reg [7:0] cnt;
  always @(posedge clk or negedge rstn) begin
    if (!rstn)
      cnt <= 8'd0;
    else if (en)
      cnt <= cnt + 8'd1;
  end
  assign q = cnt;
  assign hit = (cnt == 8'hA5);
endmodule
