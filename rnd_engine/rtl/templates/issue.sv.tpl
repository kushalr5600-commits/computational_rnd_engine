// Issue + in-order retirement. Holds an IF_DEPTH ring of in-flight
// instructions, stalls on RAW hazards against all older entries and on a
// blocked oldest (memory) instruction, and retires the head in order.
module issue #(
  parameter int SLOTS     = 1,
  parameter int LOG_REGS  = 4,
  parameter int ISA_WIDTH = 32,
  parameter int PC_WIDTH  = 32,
  parameter int ADDR_W    = 14,
  parameter int IF_DEPTH  = 8,
  parameter int RD_PORTS  = 2
) (
  input  logic                                clk,
  input  logic                                rst_n,
  // decoded packet
  input  logic [SLOTS-1:0]                    dec_valid,
  input  logic [SLOTS*(3+1)-1:0] dec_op,
  input  logic [SLOTS*LOG_REGS-1:0] dec_rs1,
  input  logic [SLOTS*LOG_REGS-1:0] dec_rs2,
  input  logic [SLOTS*LOG_REGS-1:0] dec_rd,
  input  logic [PC_WIDTH-1:0]                 dec_pc,
  // register file read data (2 ports per slot)
  input  logic [RD_PORTS*SLOTS*ISA_WIDTH-1:0] rf_rdata,
  output logic [RD_PORTS*SLOTS*LOG_REGS-1:0] rf_raddr,
  // register file write (in-order retire, 1 port)
  output logic                                rf_we,
  output logic [LOG_REGS-1:0]                 rf_waddr,
  output logic [ISA_WIDTH-1:0]                rf_wdata,
  // memory response / request
  input  logic                                mem_resp_valid,
  input  logic [ISA_WIDTH-1:0]                mem_resp_rdata,
  output logic                                mem_req_valid,
  output logic                                mem_req_we,
  output logic [ADDR_W-1:0]                   mem_req_addr,
  output logic [ISA_WIDTH-1:0]                mem_req_wdata,
  // datapath results (execute / vector / specialized)
  input  logic [ISA_WIDTH-1:0]                alu_y,
  input  logic [ISA_WIDTH-1:0]                vec_y,
  input  logic [ISA_WIDTH-1:0]                mac_acc,
  output logic [3:0]                          head_op,
  output logic [ISA_WIDTH-1:0]                head_opa,
  output logic [ISA_WIDTH-1:0]                head_opb,
  output logic                                head_drive_valid,
  // flow control
  output logic                                stall_fetch,
  output logic                                halt
);
  localparam int LOG_IF = $clog2(IF_DEPTH);

  logic [IF_DEPTH*(3+1)-1:0] if_op;
  logic [IF_DEPTH*LOG_REGS-1:0] if_rd;
  logic [IF_DEPTH*ISA_WIDTH-1:0] if_opa;
  logic [IF_DEPTH*ISA_WIDTH-1:0] if_opb;
  logic [IF_DEPTH*ISA_WIDTH-1:0] if_rd_data;
  logic [IF_DEPTH-1:0] if_valid;
  logic [IF_DEPTH-1:0] if_mem;
  logic [IF_DEPTH-1:0] if_mem_we;
  logic [IF_DEPTH-1:0] if_mem_done;
  logic [LOG_IF-1:0]              head;
  logic [LOG_IF-1:0]              tail;
  logic [LOG_IF-1:0]              tidx;
  logic                           halt_r;

  logic [LOG_IF-1:0]              head_plus1;
  logic [7:0]                     num_valid;
  logic [7:0]                     free_after;
  logic                           head_occ;
  logic                           head_done;
  logic [$clog2(SLOTS+1)-1:0]     n_admit;
  logic                           admit;
  logic [SLOTS-1:0]               slot_raw_hazard;

  assign head_plus1 = (head == IF_DEPTH-1) ? {LOG_IF{1'b0}} : (head + 1);
  assign head_occ   = if_valid[head];
  assign head_done  = head_occ && (!if_mem[head] || if_mem_done[head]);
  assign head_drive_valid = head_occ;
  assign head_op          = if_op[head*(3+1) +: (3+1)];
  assign head_opa         = if_opa[head*ISA_WIDTH +: ISA_WIDTH];
  assign head_opb         = if_opb[head*ISA_WIDTH +: ISA_WIDTH];
  logic [ISA_WIDTH-1:0]       head_rd_data;
  assign head_rd_data     = if_rd_data[head*ISA_WIDTH +: ISA_WIDTH];
  logic [ADDR_W-1:0]          head_opa_addr;
  assign head_opa_addr    = head_opa[ADDR_W-1:0];

  // register-file read address mapping: slot s uses ports 2s (rs1) and 2s+1 (rs2)
  always_comb begin
    for (int p = 0; p < RD_PORTS*SLOTS; p++) begin
      if ((p % 2) == 0) rf_raddr[p*LOG_REGS +: LOG_REGS] = dec_rs1[(p/2)*LOG_REGS +: LOG_REGS];
      else              rf_raddr[p*LOG_REGS +: LOG_REGS] = dec_rs2[(p/2)*LOG_REGS +: LOG_REGS];
    end
  end

  always_comb begin
    num_valid = 0;
    for (int e = 0; e < IF_DEPTH; e++) begin
      if (if_valid[e]) num_valid = num_valid + 1;
    end
    free_after = IF_DEPTH - num_valid;
    if (head_occ && head_done) free_after = free_after + 1;
  end

  // per-slot RAW hazard against every older in-flight entry and against
  // earlier slots in the same packet (in-order issue/retire => reads happen
  // before any older writeback, so any match forces a stall).
  always_comb begin
    for (int k = 0; k < SLOTS; k++) begin
      slot_raw_hazard[k] = 1'b0;
      for (int e = 0; e < IF_DEPTH; e++) begin
        if (if_valid[e] && (if_rd[e*LOG_REGS +: LOG_REGS] == dec_rs1[k*LOG_REGS +: LOG_REGS] || if_rd[e*LOG_REGS +: LOG_REGS] == dec_rs2[k*LOG_REGS +: LOG_REGS])) begin
          slot_raw_hazard[k] = 1'b1;
        end
      end
    end
    for (int j = 0; j < SLOTS; j++) begin
      for (int k = 0; k < SLOTS; k++) begin
        if (k > j && (dec_rd[j*LOG_REGS +: LOG_REGS] == dec_rs1[k*LOG_REGS +: LOG_REGS] || dec_rd[j*LOG_REGS +: LOG_REGS] == dec_rs2[k*LOG_REGS +: LOG_REGS])) slot_raw_hazard[k] = 1'b1;
      end
    end
  end

  always_comb begin
    n_admit = SLOTS;
    admit   = 1'b1;
    stall_fetch = 1'b0;
    halt    = halt_r;
    if (halt_r) begin
      n_admit = 0;
      admit   = 1'b0;
      stall_fetch = 1'b1;
    end else if (head_occ && !head_done) begin
      n_admit = 0;
      admit   = 1'b0;
      stall_fetch = 1'b1;
    end else begin
      if (free_after < SLOTS) n_admit = free_after;
      for (int k = 0; k < SLOTS; k++) begin
        if (k < n_admit && slot_raw_hazard[k]) n_admit = k;
      end
      if (n_admit == 0) begin
        admit = 1'b0;
        stall_fetch = 1'b1;
      end
    end
  end

  // writeback data selection for the retiring head
  logic [ISA_WIDTH-1:0] wb_data;
  logic                 wb_en;
  always_comb begin
    wb_data = alu_y;
    wb_en   = 1'b0;
    if (head_occ && head_done) begin
      if (if_mem[head] && !if_mem_we[head]) begin
        wb_data = head_rd_data;                       // OP_LD
      end else if (head_op == 4'h8) begin
        wb_data = vec_y;                          // OP_VEC
      end else if (head_op == 4'h9) begin
        wb_data = mac_acc;                        // OP_MAC
      end else begin
        wb_data = alu_y;
      end
      if (head_op != 4'h7 && head_op != 4'hf) wb_en = 1'b1; // not ST/HALT
    end
  end

  // memory request: one outstanding request at a time, driven by the head
  logic mem_pending_r;
  always_comb begin
    mem_req_valid = 1'b0;
    mem_req_we    = 1'b0;
    mem_req_addr  = {ADDR_W{1'b0}};
    mem_req_wdata = {ISA_WIDTH{1'b0}};
    if (head_occ && if_mem[head] && !if_mem_done[head] && !mem_pending_r && !halt_r) begin
      mem_req_valid = 1'b1;
      mem_req_we    = if_mem_we[head];
      mem_req_addr  = head_opa_addr;
      mem_req_wdata = head_opb;
    end
  end

  // writeback + ring pointer / state update
  assign rf_we    = wb_en;
  assign rf_waddr = if_rd[head*LOG_REGS +: LOG_REGS];
  assign rf_wdata = wb_data;

  always_ff @(posedge clk) begin
    if (!rst_n) begin
      head          <= {LOG_IF{1'b0}};
      tail          <= {LOG_IF{1'b0}};
      halt_r        <= 1'b0;
      mem_pending_r <= 1'b0;
      for (int e = 0; e < IF_DEPTH; e++) begin
        if_valid[e]    <= 1'b0;
        if_mem_done[e] <= 1'b0;
      end
    end else begin
      // (1) memory response marks the oldest memory op complete
      if (mem_req_valid) begin
        mem_pending_r <= 1'b1;
      end
      if (mem_resp_valid) begin
        if_mem_done[head] <= 1'b1;
        mem_pending_r     <= 1'b0;
      end
      // (2) in-order retire of the head
      if (head_occ && head_done) begin
        if (if_op[head*(3+1) +: (3+1)] == 4'hf) begin
          halt_r <= 1'b1;                       // OP_HALT
        end
        if_valid[head] <= 1'b0;
        head           <= head_plus1;
      end
      // (3) admission of up to n_admit decoded slots at the tail
      if (admit) begin
        int idx;
        for (int k = 0; k < SLOTS; k++) begin
          if (k < n_admit) begin
            idx = tail + k;
            if (idx >= IF_DEPTH) idx = idx - IF_DEPTH;
            if_valid[idx]    <= 1'b1;
            if_op[idx*(3+1) +: (3+1)]       <= dec_op[k*(3+1) +: (3+1)];
            if_rd[idx*LOG_REGS +: LOG_REGS]       <= dec_rd[k*LOG_REGS +: LOG_REGS];
            if_opa[idx*ISA_WIDTH +: ISA_WIDTH]      <= rf_rdata[(2*k)*ISA_WIDTH +: ISA_WIDTH];
            if_opb[idx*ISA_WIDTH +: ISA_WIDTH]      <= rf_rdata[(2*k+1)*ISA_WIDTH +: ISA_WIDTH];
            if_rd_data[idx*ISA_WIDTH +: ISA_WIDTH]  <= {ISA_WIDTH{1'b0}};
            if_mem[idx]      <= (dec_op[k*(3+1) +: (3+1)] == 4'h6) || (dec_op[k*(3+1) +: (3+1)] == 4'h7);
            if_mem_we[idx]   <= (dec_op[k*(3+1) +: (3+1)] == 4'h7);
            if_mem_done[idx] <= 1'b0;
          end
        end
        tidx = tail + n_admit;
        if (tidx >= IF_DEPTH) begin
          tidx = tidx - IF_DEPTH;
        end
        tail <= tidx;
      end
    end
  end
endmodule