`timescale 1ns/1ps
// Scratch debug TB: prints per-cycle pipeline state to find the stall.
module dbg_tb;
  logic clk = 0, rst_n = 0;
  logic mem_resp_valid = 0;
  logic [31:0] mem_resp_rdata = '0;
  logic mem_req_valid, mem_req_we;
  logic [17:0] mem_req_addr;
  logic [31:0] mem_req_wdata;
  logic halt;

  always #5 clk = ~clk;

  top #(.ISA(32), .VECTOR(1024), .SLOTS(4), .INSN_W(25), .PC_W(32),
        .LOG_R(7), .REG_C(128), .ADDR_W(18), .IF_D(8), .LANES(512)) dut (
    .clk(clk), .rst_n(rst_n),
    .mem_resp_valid(mem_resp_valid), .mem_resp_rdata(mem_resp_rdata),
    .mem_req_valid(mem_req_valid), .mem_req_we(mem_req_we),
    .mem_req_addr(mem_req_addr), .mem_req_wdata(mem_req_wdata),
    .halt(halt)
  );

  logic [31:0] mem [1<<18];
  initial begin
    repeat (4) @(posedge clk);
    rst_n = 1;
  end

  always @(posedge clk) begin
    mem_resp_valid <= 1'b0;
    if (mem_req_valid && !mem_req_we) begin
      mem_resp_rdata <= mem[mem_req_addr];
      mem_resp_valid <= 1'b1;
    end else if (mem_req_valid) begin
      mem[mem_req_addr] <= mem_req_wdata;
    end
  end

  int cyc;
  initial begin
    for (cyc = 0; cyc < 400; cyc++) begin
      @(posedge clk);
      $display("DBG %0d pc=%0d halt=%b rst=%b stall=%b admit=%b nadm=%0d head=%0d tail=%0d valid=%08b req=%b we=%b op=%h",
               cyc, dut.pc, halt, rst_n, dut.issue_u.stall_fetch, dut.issue_u.admit,
               dut.issue_u.n_admit, dut.issue_u.head, dut.issue_u.tail,
               dut.issue_u.if_valid, mem_req_valid, mem_req_we, dut.issue_u.head_op);
      if (halt) begin
        $display("DBG HALT OBSERVED at cycle %0d time %0t", cyc, $time);
        repeat (4) @(posedge clk);
        $finish;
      end
    end
    $display("DBG NO HALT after 400 cycles (time %0t)", $time);
    $finish;
  end
endmodule