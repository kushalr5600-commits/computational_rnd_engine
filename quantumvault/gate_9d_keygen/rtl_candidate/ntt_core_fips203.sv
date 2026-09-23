// QuantumVault — FIPS 203 NTT Core (Candidate)
// Implements Algorithms 9 (Forward NTT), 10 (Inverse NTT)
//
// Architecture changes from frozen ntt_core.sv:
//   1. 7 butterfly layers (not 8)
//   2. Forward NTT: standard input -> CT layers -> bit-reversed output (natural CT order)
//   3. Inverse NTT: bit-reversed input -> GS layers -> standard output (natural GS order)
//   4. N_INV = 3303 (128^-1 mod 3329)
//   5. Zeta ROM: 128 entries, ZETAS[k] = 17^{bitrev7(k)} mod 3329
//   6. Separate CT (forward) and GS (inverse) butterfly units

module ntt_core_fips203 #(
    parameter Q_WIDTH  = 12,
    parameter Q        = 3329,
    parameter N        = 256,
    parameter LOG2_N   = 8,
    parameter NUM_LAYERS = 7
)(
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  start,
    input  wire                  inverse,
    output reg  [LOG2_N-1:0]    mem_addr,
    output reg  [Q_WIDTH-1:0]   mem_wdata,
    input  wire [Q_WIDTH-1:0]   mem_rdata,
    output reg                   mem_we,
    output reg                   mem_re,
    output reg  [9:0]           tw_addr,
    input  wire [Q_WIDTH-1:0]   tw_rdata,
    output reg                   done,
    output reg  [LOG2_N+4:0]    cycles
);

    localparam [3:0] S_IDLE    = 4'd0;
    localparam [3:0] S_LOAD    = 4'd1;
    localparam [3:0] S_COMPUTE = 4'd2;
    localparam [3:0] S_FETCH   = 4'd3;
    localparam [3:0] S_SCALE   = 4'd4;
    localparam [3:0] S_WRITE   = 4'd5;
    localparam [3:0] S_DONE    = 4'd6;

    reg [3:0] state;
    reg [LOG2_N-1:0] stage_counter;
    reg [LOG2_N-1:0] pair_idx;
    reg [8:0]        load_idx;
    reg [8:0]        write_idx;

    reg [Q_WIDTH-1:0] coeff_buf [0:N-1];

    // CT butterfly (forward NTT)
    reg  [Q_WIDTH-1:0] ct_a, ct_b, ct_tw;
    wire [Q_WIDTH-1:0] ct_a_out, ct_b_out;
    reg                ct_valid;
    wire               ct_done;
    reg                ct_busy;

    // GS butterfly (inverse NTT)
    reg  [Q_WIDTH-1:0] gs_a, gs_b, gs_tw;
    wire [Q_WIDTH-1:0] gs_a_out, gs_b_out;
    reg                gs_valid;
    wire               gs_done;
    reg                gs_busy;

    ntt_butterfly #(.Q_WIDTH(Q_WIDTH), .Q(Q)) ct_bf (
        .clk(clk), .rst_n(rst_n), .valid(ct_valid),
        .a(ct_a), .b(ct_b), .tw(ct_tw),
        .a_out(ct_a_out), .b_out(ct_b_out), .done(ct_done)
    );

    ntt_butterfly_gs #(.Q_WIDTH(Q_WIDTH), .Q(Q)) gs_bf (
        .clk(clk), .rst_n(rst_n), .valid(gs_valid),
        .a(gs_a), .b(gs_b), .tw(gs_tw),
        .a_out(gs_a_out), .b_out(gs_b_out), .done(gs_done)
    );

    // Address computation for FIPS 203 partial NTT
    // Stage s: length = N >> (s+1) = 128 >> s
    // Pair p: a = (p >> (7-s)) * 2*length + (p mod length), b = a + length
    // Equivalent: a = {p bits above (7-s)}, 0, {p bits below (7-s)}
    function [LOG2_N-1:0] compute_addr_a;
        input [2:0] stage;
        input [LOG2_N-1:0] pair;
        reg [LOG2_N-1:0] m, mask;
        begin
            m = N >> (stage + 1);
            mask = m - 1;
            compute_addr_a = ((pair & ~mask) << 1) | (pair & mask);
        end
    endfunction

    function [LOG2_N-1:0] compute_addr_b;
        input [2:0] stage;
        input [LOG2_N-1:0] pair;
        reg [LOG2_N-1:0] m, mask, a;
        begin
            m = N >> (stage + 1);
            mask = m - 1;
            a = ((pair & ~mask) << 1) | (pair & mask);
            compute_addr_b = a + m;
        end
    endfunction

    function [LOG2_N-1:0] bit_reverse;
        input [LOG2_N-1:0] x;
        reg [LOG2_N-1:0] r;
        integer bi_bit;
        begin
            r = 0;
            for (bi_bit = 0; bi_bit < LOG2_N; bi_bit = bi_bit + 1) begin
                r = {r[LOG2_N-2:0], x[0]};
                x = x >> 1;
            end
            bit_reverse = r;
        end
    endfunction

    // Zeta ROM: 128 entries, ZETAS[k] = 17^{bitrev7(k)} mod 3329
    reg [Q_WIDTH-1:0] zeta_rom [0:127];
    initial $readmemh("fips_zetas.hex", zeta_rom);

    // Zeta index computation
    // FIPS 203: all butterflies in a group share one zeta.
    // Forward: zeta_idx = 2^s + (pair_idx >> (7-s)), s=stage_counter
    // Inverse: zeta_idx = (2^(7-s)-1) - (pair_idx >> (s+1)), s=stage_counter
    reg [6:0] zeta_idx;
    reg [Q_WIDTH-1:0] zeta_val;
    reg [6:0] zeta_base, zeta_group;

    always @(*) begin
        if (inverse) begin
            case (stage_counter)
                3'd0: begin zeta_base = 7'd127; zeta_group = {1'b0, pair_idx[6:1]}; end
                3'd1: begin zeta_base = 7'd63;  zeta_group = {2'b0, pair_idx[6:2]}; end
                3'd2: begin zeta_base = 7'd31;  zeta_group = {3'b0, pair_idx[6:3]}; end
                3'd3: begin zeta_base = 7'd15;  zeta_group = {4'b0, pair_idx[6:4]}; end
                3'd4: begin zeta_base = 7'd7;   zeta_group = {5'b0, pair_idx[6:5]}; end
                3'd5: begin zeta_base = 7'd3;   zeta_group = {6'b0, pair_idx[6]};   end
                3'd6: begin zeta_base = 7'd1;   zeta_group = 7'd0;                   end
                default: begin zeta_base = 7'd0; zeta_group = 7'd0; end
            endcase
            zeta_idx = zeta_base - zeta_group;
        end else begin
            case (stage_counter)
                3'd0: begin zeta_base = 7'd1;  zeta_group = 7'd0;                   end
                3'd1: begin zeta_base = 7'd2;  zeta_group = {6'b0, pair_idx[6]};   end
                3'd2: begin zeta_base = 7'd4;  zeta_group = {5'b0, pair_idx[6:5]}; end
                3'd3: begin zeta_base = 7'd8;  zeta_group = {4'b0, pair_idx[6:4]}; end
                3'd4: begin zeta_base = 7'd16; zeta_group = {3'b0, pair_idx[6:3]}; end
                3'd5: begin zeta_base = 7'd32; zeta_group = {2'b0, pair_idx[6:2]}; end
                3'd6: begin zeta_base = 7'd64; zeta_group = {1'b0, pair_idx[6:1]}; end
                default: begin zeta_base = 7'd0; zeta_group = 7'd0; end
            endcase
            zeta_idx = zeta_base + zeta_group;
        end
    end

    always @(*) begin
        zeta_val = zeta_rom[zeta_idx];
    end

    // Forward NTT: stage 0 → length=128, stage 6 → length=2
    // Inverse NTT: stage 0 → length=2, stage 6 → length=128
    wire [2:0] eff_stage = inverse ? (NUM_LAYERS - 1 - stage_counter) : stage_counter;

    // Temporary address registers for S_COMPUTE
    reg [LOG2_N-1:0] si_a, si_b;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state         <= S_IDLE;
            done          <= 0;
            cycles        <= 0;
            ct_valid      <= 0;
            ct_busy       <= 0;
            gs_valid      <= 0;
            gs_busy       <= 0;
            mem_we        <= 0;
            mem_re        <= 0;
            tw_addr       <= 0;
            stage_counter <= 0;
            pair_idx      <= 0;
            load_idx      <= 0;
            write_idx     <= 0;
        end else begin
            case (state)
                S_IDLE: begin
                    cycles <= 0;
                    mem_we <= 1'b0;
                    mem_re <= 1'b0;
                    ct_valid <= 1'b0;
                    ct_busy  <= 1'b0;
                    gs_valid <= 1'b0;
                    gs_busy  <= 1'b0;
                    if (start) begin
                        done <= 1'b0;
                        load_idx <= 0;
                        state <= S_LOAD;
                    end
                end

                S_LOAD: begin
                    mem_re <= 1'b1;
                    mem_addr <= load_idx[LOG2_N-1:0];
                    if (load_idx > 0) begin
                        coeff_buf[load_idx - 1] = mem_rdata;
                    end
                    if (load_idx == N) begin
                        coeff_buf[N - 1] = mem_rdata;
                        mem_re <= 1'b0;
                        // Both forward and inverse go directly to S_COMPUTE
                        // CT naturally produces bit-reversed output
                        // GS naturally consumes bit-reversed input
                        state <= S_COMPUTE;
                        load_idx <= 0;
                        stage_counter <= 0;
                        pair_idx <= 0;
                    end else begin
                        load_idx <= load_idx + 1;
                    end
                end

                S_COMPUTE: begin
                    cycles <= cycles + 1;

                    if (inverse) begin
                        // GS butterfly for inverse NTT
                        if (gs_busy && gs_done) begin
                            si_a = compute_addr_a(eff_stage, pair_idx);
                            si_b = compute_addr_b(eff_stage, pair_idx);
                            coeff_buf[si_a] = gs_a_out;
                            coeff_buf[si_b] = gs_b_out;
                            gs_valid <= 1'b0;
                            gs_busy  <= 1'b0;

                            if (pair_idx == N/2 - 1) begin
                                if (stage_counter == NUM_LAYERS - 1) begin
                                    state <= S_SCALE;
                                    write_idx <= 0;
                                end else begin
                                    stage_counter <= stage_counter + 1;
                                    pair_idx <= 0;
                                end
                            end else begin
                                pair_idx <= pair_idx + 1;
                            end
                        end else if (!gs_busy) begin
                            gs_a    <= coeff_buf[compute_addr_a(eff_stage, pair_idx)];
                            gs_b    <= coeff_buf[compute_addr_b(eff_stage, pair_idx)];
                            gs_tw   <= zeta_val;
                            gs_valid <= 1'b1;
                            gs_busy  <= 1'b1;
                            state    <= S_FETCH;
                        end
                    end else begin
                        // CT butterfly for forward NTT
                        if (ct_busy && ct_done) begin
                            si_a = compute_addr_a(eff_stage, pair_idx);
                            si_b = compute_addr_b(eff_stage, pair_idx);
                            coeff_buf[si_a] = ct_a_out;
                            coeff_buf[si_b] = ct_b_out;
                            ct_valid <= 1'b0;
                            ct_busy  <= 1'b0;

                            if (pair_idx == N/2 - 1) begin
                                if (stage_counter == NUM_LAYERS - 1) begin
                                    // Forward NTT done: bit-reversed output ready in coeff_buf
                                    // Inverse NTT done: scaled standard-order output ready
                                    write_idx <= 0;
                                    state <= inverse ? S_SCALE : S_WRITE;
                                end else begin
                                    stage_counter <= stage_counter + 1;
                                    pair_idx <= 0;
                                end
                            end else begin
                                pair_idx <= pair_idx + 1;
                            end
                        end else if (!ct_busy) begin
                            ct_a    <= coeff_buf[compute_addr_a(eff_stage, pair_idx)];
                            ct_b    <= coeff_buf[compute_addr_b(eff_stage, pair_idx)];
                            ct_tw   <= zeta_val;
                            ct_valid <= 1'b1;
                            ct_busy  <= 1'b1;
                            state    <= S_FETCH;
                        end
                    end
                end

                S_FETCH: begin
                    if (inverse) begin
                        gs_valid <= 1'b1;
                        gs_busy  <= 1'b1;
                    end else begin
                        ct_valid <= 1'b1;
                        ct_busy  <= 1'b1;
                    end
                    state <= S_COMPUTE;
                end

                S_SCALE: begin
                    // N_INV = 3303 for FIPS 203
                    if (write_idx < N) begin
                        coeff_buf[write_idx] = ({{Q_WIDTH{1'b0}}, coeff_buf[write_idx]} * N_INV) % Q;
                        write_idx <= write_idx + 1;
                    end else begin
                        write_idx <= 0;
                        state <= S_WRITE;
                    end
                end

                S_WRITE: begin
                    if (write_idx < N) begin
                        mem_we  <= 1'b1;
                        mem_re  <= 1'b0;
                        mem_addr <= write_idx;
                        mem_wdata <= coeff_buf[write_idx];
                        write_idx <= write_idx + 1;
                    end else begin
                        mem_we <= 1'b0;
                        state <= S_DONE;
                    end
                end

                S_DONE: begin
                    done <= 1'b1;
                    state <= S_IDLE;
                end

                default: state <= S_IDLE;
            endcase
        end
    end

    // FIPS 203: N_INV = 128^{-1} mod 3329 = 3303
    localparam [Q_WIDTH-1:0] N_INV = 12'd3303;

endmodule
