// QuantumVault R0 — SHAKE/SHA3 sponge (streaming, FIPS 202)
// Supports SHAKE128, SHAKE256, SHA3-256, SHA3-512
// Extended: multi-block squeeze for XOF output > RATE_BYTES
//
// Protocol (handshake):
//   1. Host pulses start=1 for one cycle with data_in valid and last=1 if
//      this is the only / final block.
//   2. Module absorbs, runs permutation, then:
//      - if last was high: squeeze output, pulse done=1
//      - if last was low:  pulse ready=1, wait for next block
//   3. On ready pulse, host must present next block within one cycle
//      and pulse start=1 for one cycle.
//   4. For output > RATE_BYTES: multiple squeeze blocks are produced
//      automatically via internal permutation loop.

module shake_sha3 #(
    parameter MODE        = 1,
    parameter RATE_BYTES  = 136,
    parameter D_OUT_BYTES = 32
)(
    input  wire                     clk,
    input  wire                     rst_n,
    input  wire                     start,
    input  wire                     last,
    input  wire [RATE_BYTES*8-1:0]  data_in,
    input  wire [7:0]               byte_len,
    output reg  [D_OUT_BYTES*8-1:0] hash_out,
    output reg                      done,
    output reg                      ready
);

    reg [1599:0] state;
    reg [1599:0] keccak_in;
    reg          keccak_start;
    wire [1599:0] keccak_out;
    wire         keccak_done;

    keccak_f #(.ROUNDS(24), .FULL_UNROLL(0)) keccak_inst (
        .clk      (clk),
        .rst_n    (rst_n),
        .start    (keccak_start),
        .state_in (keccak_in),
        .state_out(keccak_out),
        .done     (keccak_done)
    );

    wire [7:0] domain_sep = (MODE <= 1) ? 8'h1F : 8'h06;

    localparam S_IDLE     = 4'd0;
    localparam S_ABSORB   = 4'd1;
    localparam S_PERM     = 4'd2;
    localparam S_CAP      = 4'd3;
    localparam S_SQUEEZE  = 4'd4;
    localparam S_DONE     = 4'd5;
     localparam S_PERM_SQ  = 4'd6;
      localparam S_WAIT_PERM = 4'd7;
      localparam S_WAIT     = 4'd8;

    reg [3:0] fsm_state;
    reg       last_reg;
    reg [15:0] squeeze_idx;

    reg [1599:0] padded_block;
    integer bi;

    always @(*) begin
        padded_block = 0;
        for (bi = 0; bi < RATE_BYTES; bi = bi + 1)
            padded_block[bi*8 +: 8] = data_in[bi*8 +: 8];
        if (last) begin
            if (byte_len < RATE_BYTES)
                padded_block[byte_len*8 +: 8] = domain_sep;
            padded_block[RATE_BYTES*8-1 -: 8] = padded_block[RATE_BYTES*8-1 -: 8] | 8'h80;
        end
    end

    integer si;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            fsm_state    <= S_IDLE;
            done         <= 1'b0;
            ready        <= 1'b0;
            keccak_start <= 1'b0;
            state        <= 0;
            last_reg     <= 1'b0;
            squeeze_idx  <= 0;
        end else begin
            case (fsm_state)
                S_IDLE: begin
                    done  <= 1'b0;
                    ready <= 1'b0;
                    squeeze_idx <= 0;
                    if (start) begin
                        state     <= 0;
                        last_reg  <= last;
                        fsm_state <= S_ABSORB;
                    end
                end

                S_ABSORB: begin
                    ready <= 1'b0;
                    last_reg <= last;
                    for (si = 0; si < RATE_BYTES; si = si + 1)
                        state[si*8 +: 8] <= state[si*8 +: 8] ^ padded_block[si*8 +: 8];
                    keccak_in    <= state ^ padded_block;
                    keccak_start <= 1'b1;
                    fsm_state    <= S_PERM;
                end

                S_PERM: begin
                    keccak_start <= 1'b0;
                    if (keccak_done)
                        fsm_state <= S_CAP;
                end

                S_CAP: begin
                    for (si = 0; si < 25; si = si + 1)
                        state[si*64 +: 64] <= keccak_out[si*64 +: 64];
                    if (last_reg) begin
                        fsm_state <= S_SQUEEZE;
                    end else begin
                        ready     <= 1'b1;
                        fsm_state <= S_WAIT;
                    end
                end

                S_WAIT: begin
                    ready <= 1'b0;
                    if (start) begin
                        last_reg  <= last;
                        fsm_state <= S_ABSORB;
                    end
                end

                S_SQUEEZE: begin
                    for (si = 0; si < RATE_BYTES; si = si + 1)
                        if ((squeeze_idx + si) < D_OUT_BYTES)
                            hash_out[(squeeze_idx + si)*8 +: 8] <= state[si*8 +: 8];
                    if (squeeze_idx + RATE_BYTES >= D_OUT_BYTES) begin
                        fsm_state <= S_DONE;
                    end else begin
                        squeeze_idx <= squeeze_idx + RATE_BYTES;
                        keccak_in <= state;
                        keccak_start <= 1'b1;
                        fsm_state <= S_PERM_SQ;
                    end
                end

                S_PERM_SQ: begin
                    keccak_start <= 1'b0;
                    if (keccak_done) begin
                        fsm_state <= S_WAIT_PERM;
                    end
                end

                S_WAIT_PERM: begin
                    for (si = 0; si < 25; si = si + 1)
                        state[si*64 +: 64] <= keccak_out[si*64 +: 64];
                    fsm_state <= S_SQUEEZE;
                end

                S_DONE: begin
                    done  <= 1'b1;
                    ready <= 1'b0;
                    fsm_state <= S_IDLE;
                end

                default: fsm_state <= S_IDLE;
            endcase
        end
    end

endmodule
