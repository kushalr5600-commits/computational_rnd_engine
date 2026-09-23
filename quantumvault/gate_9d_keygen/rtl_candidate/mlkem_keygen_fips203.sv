// QuantumVault Gate 9D — ML-KEM-768 KeyGen Top-Level
// FIPS 203 Algorithm 16: ML-KEM.KeyGen()
//
// Architecture: single shared coefficient memory, time-multiplexed ownership.
// Only one submodule writes to the memory at any time.
// Reads are combinational (multiple ports OK — synthesis infers dual-port RAM).
//
// Memory map (12-bit coefficients, depth 4864):
//   A_BASE=0     A_hat[0..8]   2304 entries  (K*K*N)
//   S_BASE=2304  s_hat[0..2]    768 entries  (K*N)
//   E_BASE=3072  e_hat[0..2]    768 entries  (K*N)
//   T_BASE=3840  t_hat[0..2]    768 entries  (K*N)
//   W_BASE=4608  temp/buffer     256 entries  (N)
//   Total = 4864

module mlkem_keygen_fips203 #(
    parameter Q_WIDTH = 12,
    parameter Q       = 3329,
    parameter N       = 256,
    parameter K       = 3,
    parameter LOG2_N  = 8,
    parameter ETA1    = 2,
    parameter D       = 12
)(
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  start,
    output reg                   done,

    input  wire [255:0]          d_seed,
    input  wire [255:0]          z_seed,

    output reg  [7:0]           ek_byte,
    output reg                   ek_valid,
    input  wire                  ek_ready,
    output reg                   ek_last,

    output reg  [7:0]           dk_byte,
    output reg                   dk_valid,
    input  wire                  dk_ready,
    output reg                   dk_last
);

    // ========================================================================
    // MEMORY MAP
    // ========================================================================
    localparam MAT_N = K * K * N;
    localparam VEC_N = K * N;
    localparam A_BASE = 0;
    localparam S_BASE = MAT_N;
    localparam E_BASE = S_BASE + VEC_N;
    localparam T_BASE = E_BASE + VEC_N;
    localparam W_BASE = T_BASE + VEC_N;
    localparam MEM_DEPTH = W_BASE + N;
    localparam MEM_ADDR_W = 13;

    // ========================================================================
    // SHARED COEFFICIENT MEMORY
    // Reads: combinational (address → data same cycle).
    // Writes: single registered process via wr_* signals.
    // ========================================================================
    reg [Q_WIDTH-1:0] coeff_mem [0:MEM_DEPTH-1];

    reg  [MEM_ADDR_W-1:0] wr_addr;
    reg  [Q_WIDTH-1:0]    wr_data;
    reg                    wr_we;

    always @(posedge clk) begin
        if (wr_we)
            coeff_mem[wr_addr] <= wr_data;
    end

    // ========================================================================
    // MEMORY OWNER
    // ========================================================================
    localparam MO_NONE = 3'd0;
    localparam MO_NTT  = 3'd1;
    localparam MO_BM   = 3'd2;
    localparam MO_CPU  = 3'd3;

    reg [2:0] mem_owner;

    // ========================================================================
    // ADDRESS TRANSLATION REGISTERS
    // ========================================================================
    reg [MEM_ADDR_W-1:0] ntt_base;
    reg [MEM_ADDR_W-1:0] bm_a_base;
    reg [MEM_ADDR_W-1:0] bm_b_base;
    reg [MEM_ADDR_W-1:0] cbd_wr_base;
    reg [MEM_ADDR_W-1:0] ns_wr_base;
    reg [MEM_ADDR_W-1:0] enc_base;

    // Precomputed matmul addresses (avoid multiply in sequential logic)
    reg [MEM_ADDR_W-1:0] mat_a_addr;
    reg [MEM_ADDR_W-1:0] mat_t_addr;
    reg [MEM_ADDR_W-1:0] mat_e_addr;

    // ========================================================================
    // WRITE PORT MULTIPLEXER
    // ========================================================================
    always @(*) begin
        wr_we   = 1'b0;
        wr_addr = 0;
        wr_data = 0;

        case (mem_owner)
            MO_NTT: begin
                wr_we   = ntt_mem_we;
                wr_addr = ntt_base + {5'd0, ntt_mem_addr};
                wr_data = ntt_mem_wdata;
            end
            MO_BM: begin
                wr_we   = bm_we_a;
                wr_addr = bm_a_base + {5'd0, bm_addr_a};
                wr_data = bm_wdata_a;
            end
            MO_CPU: begin
                if (cbd_coeff_we) begin
                    wr_we   = 1'b1;
                    wr_addr = cbd_wr_base + {5'd0, cbd_coeff_addr};
                    wr_data = cbd_coeff_out;
                end else if (ns_coeff_we) begin
                    wr_we   = 1'b1;
                    wr_addr = ns_wr_base + {5'd0, ns_coeff_addr};
                    wr_data = ns_coeff_out;
                end
            end
            default: begin ; end
        endcase
    end

    // ========================================================================
    // READ PORTS — combinational
    // ========================================================================
    wire [Q_WIDTH-1:0] ntt_rdata  = coeff_mem[ntt_base + {5'd0, ntt_mem_addr}];
    wire [Q_WIDTH-1:0] bm_rdata_a = coeff_mem[bm_a_base + {5'd0, bm_addr_a}];
    wire [Q_WIDTH-1:0] bm_rdata_b = coeff_mem[bm_b_base + {5'd0, bm_addr_b}];

    // ========================================================================
    // NTT CORE
    // Timing: start pulse → 257 cycles load → bit-rev → NTT → 257 cycles write → done pulse
    // Memory: 8-bit local addr (0-255), translated via ntt_base
    // ========================================================================
    reg                    ntt_start;
    reg                    ntt_inverse;
    wire                   ntt_done;
    wire [LOG2_N-1:0]      ntt_mem_addr;
    wire [Q_WIDTH-1:0]     ntt_mem_wdata;
    wire                   ntt_mem_we;
    wire                   ntt_mem_re;
    wire [9:0]             ntt_tw_addr;

    ntt_core_fips203 #(.Q_WIDTH(Q_WIDTH), .Q(Q), .N(N), .LOG2_N(LOG2_N), .NUM_LAYERS(7)) u_ntt (
        .clk       (clk),
        .rst_n     (rst_n),
        .start     (ntt_start),
        .inverse   (ntt_inverse),
        .mem_addr  (ntt_mem_addr),
        .mem_wdata (ntt_mem_wdata),
        .mem_rdata (ntt_rdata),
        .mem_we    (ntt_mem_we),
        .mem_re    (ntt_mem_re),
        .tw_addr   (ntt_tw_addr),
        .tw_rdata  (32'd0),
        .done      (ntt_done),
        .cycles    ()
    );

    // ========================================================================
    // BASEMULTIPLY
    // Timing: start pulse → 4 cycles/coeff × 256 = 1024 cycles → done pulse
    // Memory: 8-bit addr for port A (read+write) and port B (read-only)
    // ========================================================================
    reg                    bm_start;
    wire                   bm_done;
    wire [LOG2_N-1:0]      bm_addr_a;
    wire [Q_WIDTH-1:0]     bm_wdata_a;
    wire                   bm_we_a;
    wire                   bm_re_a;
    wire [LOG2_N-1:0]      bm_addr_b;
    wire                   bm_re_b;
    wire [LOG2_N-1:0]      bm_tw_addr;

    basemultiply #(.Q_WIDTH(Q_WIDTH), .Q(Q), .N(N), .LOG2_N(LOG2_N)) u_bm (
        .clk      (clk),
        .rst_n    (rst_n),
        .start    (bm_start),
        .done     (bm_done),
        .addr_a   (bm_addr_a),
        .wdata_a  (bm_wdata_a),
        .rdata_a  (bm_rdata_a),
        .we_a     (bm_we_a),
        .re_a     (bm_re_a),
        .addr_b   (bm_addr_b),
        .rdata_b  (bm_rdata_b),
        .re_b     (bm_re_b),
        .tw_addr  (bm_tw_addr),
        .tw_rdata (tw_rom[bm_tw_addr])
    );

    // ========================================================================
    // KEY_ENCODE
    // Timing: start pulse → reads 768 coeffs (2 cycles each) → streams 1152 bytes
    // Memory: 10-bit addr {pi[1:0], ci[7:0]}, read-only
    // Output: byte_valid/byte_ready handshake, backpressure-aware
    // ========================================================================
    reg                    enc_start;
    wire                   enc_done;
    wire [LOG2_N+1:0]      enc_coeff_addr;
    wire                   enc_coeff_re;
    wire [7:0]             enc_byte_out;
    wire                   enc_byte_valid;
    reg                    enc_byte_ready;

    key_encode #(.Q_WIDTH(Q_WIDTH), .Q(Q), .N(N), .K(K), .LOG2_N(LOG2_N), .D(D)) u_enc (
        .clk         (clk),
        .rst_n       (rst_n),
        .start       (enc_start),
        .done        (enc_done),
        .coeff_addr  (enc_coeff_addr),
        .coeff_rdata (coeff_mem[enc_base + {3'd0, enc_coeff_addr}]),
        .coeff_re    (enc_coeff_re),
        .byte_out    (enc_byte_out),
        .byte_valid  (enc_byte_valid),
        .byte_ready  (enc_byte_ready)
    );

    // ========================================================================
    // SHAKE/SHA3 INSTANCES
    // G: SHAKE-256, 64B out. start pulse → done pulse.
    // H: SHA3-256, 32B out. start pulse → done pulse.
    // XOF: SHAKE-128, 136B out. start pulse → done pulse.
    // PRF: SHAKE-256, 128B out. start pulse → done pulse.
    // ========================================================================
    reg         g_start, g_last;
    reg  [1087:0] g_din;
    reg  [7:0]  g_len;
    wire [511:0] g_out;
    wire        g_done;

    shake_sha3 #(.MODE(3), .RATE_BYTES(72), .D_OUT_BYTES(64)) u_g (
        .clk(clk), .rst_n(rst_n),
        .start(g_start), .last(g_last),
        .data_in(g_din), .byte_len(g_len),
        .hash_out(g_out), .done(g_done), .ready()
    );

    reg         h_start, h_last;
    reg  [1087:0] h_din;
    reg  [7:0]  h_len;
    wire [255:0] h_out;
    wire        h_done;
    wire        h_ready;

    shake_sha3 #(.MODE(2), .RATE_BYTES(136), .D_OUT_BYTES(32)) u_h (
        .clk(clk), .rst_n(rst_n),
        .start(h_start), .last(h_last),
        .data_in(h_din), .byte_len(h_len),
        .hash_out(h_out), .done(h_done), .ready(h_ready)
    );

    reg         xof_start, xof_last;
    reg  [1343:0] xof_din;
    reg  [7:0]  xof_len;
    wire [6719:0] xof_out;
    wire        xof_done;

    shake_sha3 #(.MODE(1), .RATE_BYTES(168), .D_OUT_BYTES(840)) u_xof (
        .clk(clk), .rst_n(rst_n),
        .start(xof_start), .last(xof_last),
        .data_in(xof_din), .byte_len(xof_len),
        .hash_out(xof_out), .done(xof_done), .ready()
    );

    reg         prf_start, prf_last;
    reg  [1087:0] prf_din;
    reg  [7:0]  prf_len;
    wire [1023:0] prf_out;
    wire        prf_done;

    shake_sha3 #(.MODE(1), .RATE_BYTES(136), .D_OUT_BYTES(128)) u_prf (
        .clk(clk), .rst_n(rst_n),
        .start(prf_start), .last(prf_last),
        .data_in(prf_din), .byte_len(prf_len),
        .hash_out(prf_out), .done(prf_done), .ready()
    );

    // ========================================================================
    // NTT_SAMPLE — Parse XOF bytes → rejection-sampled NTT coefficients
    // start pulse → feeds xof bytes via xof_valid/xof_ready → done pulse
    // coeff_we fires 1-cycle per accepted coefficient
    // ========================================================================
    reg                    ns_start;
    wire                   ns_done;
    reg  [7:0]             ns_xof_data;
    reg                    ns_xof_valid;
    wire                   ns_xof_ready;
    wire [Q_WIDTH-1:0]     ns_coeff_out;
    wire [LOG2_N-1:0]      ns_coeff_addr;
    wire                   ns_coeff_we;

    ntt_sample #(.Q_WIDTH(Q_WIDTH), .Q(Q), .N(N), .LOG2_N(LOG2_N)) u_ns (
        .clk       (clk),
        .rst_n     (rst_n),
        .start     (ns_start),
        .done      (ns_done),
        .xof_data  (ns_xof_data),
        .xof_valid (ns_xof_valid),
        .xof_ready (ns_xof_ready),
        .coeff_out (ns_coeff_out),
        .coeff_addr(ns_coeff_addr),
        .coeff_we  (ns_coeff_we)
    );

    // ========================================================================
    // CBD_SAMPLER — PRF bytes → CBD(eta=2) coefficients
    // start pulse → feeds prf bytes via prf_valid/prf_ready → done pulse
    // prf_ready is COMBINATIONAL (high when st==ST_FILL && cnt < BITS_PER)
    // coeff_we fires 1-cycle per accepted coefficient
    // ========================================================================
    reg                    cbd_start;
    wire                   cbd_done;
    reg  [7:0]             cbd_prf_data;
    reg                    cbd_prf_valid;
    wire                   cbd_prf_ready;
    wire [Q_WIDTH-1:0]     cbd_coeff_out;
    wire [7:0]             cbd_coeff_addr;
    wire                   cbd_coeff_we;

    cbd_sampler #(.Q_WIDTH(Q_WIDTH), .Q(Q), .N(N), .ETA(ETA1)) u_cbd (
        .clk       (clk),
        .rst_n     (rst_n),
        .start     (cbd_start),
        .done      (cbd_done),
        .prf_data  (cbd_prf_data),
        .prf_valid (cbd_prf_valid),
        .prf_ready (cbd_prf_ready),
        .coeff_out (cbd_coeff_out),
        .coeff_addr(cbd_coeff_addr),
        .coeff_we  (cbd_coeff_we)
    );

    // ========================================================================
    // DERIVED SEEDS
    // ========================================================================
    reg [255:0] rho, sigma;

    // ========================================================================
    // BYTE BUFFERS — bridge SHAKE streaming → ntt_sample/cbd_sampler
    //
    // xof_ready and prf_ready are COMBINATIONAL.
    // Feed bytes when buf_valid && ready, advance buf_idx.
    // ========================================================================
    reg [7:0]  xof_buf [0:839];
    reg [9:0]  xof_buf_idx;
    reg        xof_buf_valid;
    integer bi;

    reg [7:0]  prf_buf [0:127];
    reg [7:0]  prf_buf_idx;
    reg        prf_buf_valid;

    // ========================================================================
    // EK BUFFER — store ek_pke (1184 bytes) for H computation and dk output
    // ========================================================================
    reg [7:0]  ek_buf [0:1183];
    reg [10:0] ek_buf_idx;
    reg        ek_buf_full;

    // ========================================================================
    // COMBINATIONAL ADDER for accumulation (avoids named blocks in always)
    // ========================================================================
    reg [Q_WIDTH-1:0] acc_read_val;
    reg [Q_WIDTH-1:0] acc_w_val;
    wire [Q_WIDTH:0]  acc_sum = {1'b0, acc_read_val} + {1'b0, acc_w_val};
    wire [Q_WIDTH-1:0] acc_result = (acc_sum >= Q) ? acc_sum[Q_WIDTH-1:0] - Q[Q_WIDTH-1:0]
                                                    : acc_sum[Q_WIDTH-1:0];

    reg [Q_WIDTH-1:0] add_e_read_val;
    reg [Q_WIDTH-1:0] add_e_t_val;
    wire [Q_WIDTH:0]  add_e_sum = {1'b0, add_e_read_val} + {1'b0, add_e_t_val};
    wire [Q_WIDTH-1:0] add_e_result = (add_e_sum >= Q) ? add_e_sum[Q_WIDTH-1:0] - Q[Q_WIDTH-1:0]
                                                        : add_e_sum[Q_WIDTH-1:0];

    // ========================================================================
    // TWIDDLE FACTOR ROM — shared between ntt_core and basemultiply
    // Both use 10-bit addr space. ntt_core uses stage-indexed, basemultiply
    // uses coefficient-indexed. They never run simultaneously.
    // Loaded via $readmemh in testbench.
    // ========================================================================
    reg [Q_WIDTH-1:0] tw_rom [0:1023];
    reg [Q_WIDTH-1:0] tw_rom_inv [0:1023];

    // ========================================================================
    // FSM STATES
    // ========================================================================
    localparam S_IDLE          = 5'd0;
    localparam S_HASH_G        = 5'd1;
    localparam S_GEN_A_XOF     = 5'd2;
    localparam S_GEN_A_SAMP    = 5'd3;
    localparam S_GEN_A_NEXT    = 5'd4;
    localparam S_CBD_S_PRF     = 5'd5;
    localparam S_CBD_S_SAMP    = 5'd6;
    localparam S_CBD_S_NEXT    = 5'd7;
    localparam S_CBD_E_PRF     = 5'd8;
    localparam S_CBD_E_SAMP    = 5'd9;
    localparam S_CBD_E_NEXT    = 5'd10;
    localparam S_NTT_SETUP     = 5'd11;
    localparam S_NTT_RUN       = 5'd12;
    localparam S_NTT_NEXT      = 5'd13;
    localparam S_NTT_WAIT      = 5'd23;  // wait for ntt_done to fall (stale-done handshake)
    localparam S_MM_INIT       = 5'd14;  // copy e[i] → T[i], init accumulator
    localparam S_MM_COPY       = 5'd15;  // copy loop (A→W or e→T)
    localparam S_MM_BM         = 5'd16;  // run basemultiply(W, s[j])
    localparam S_MM_ACC        = 5'd17;  // T[i][k] += W[k] for all k
    localparam S_MM_NEXT_J     = 5'd18;
    localparam S_MM_NEXT_I     = 5'd19;
    localparam S_ENCODE_EK     = 5'd20;
    localparam S_ENCODE_DK     = 5'd21;
    localparam S_EK_RHO         = 5'd22;
    // 5'd23 reused as S_NTT_WAIT (S_DK_OUT was dead code — never assigned)
    localparam S_ZEROIZE       = 5'd24;
    localparam S_DONE          = 5'd25;
    localparam S_DK_ENC_S      = 5'd26;
    localparam S_DK_EK_OUT     = 5'd27;
    localparam S_DK_H_SETUP    = 5'd28;
    localparam S_DK_H_ABSORB  = 5'd29;
    localparam S_DK_H_WAIT    = 5'd30;
    localparam S_DK_H_OUT     = 5'd31;

    reg [4:0] state;

    // ========================================================================
    // ITERATION COUNTERS
    // ========================================================================
    reg [3:0] mat_i, mat_j;
    reg [2:0] vec_i;
    reg [8:0] ci;
    reg [11:0] byte_total;
    reg [7:0]  prf_counter;
    reg [8:0]  copy_ci;
    reg        mm_needs_add_e;
    reg        doing_inv_ntt;  // inverse NTT phase on T after matmul
    reg [3:0]  h_block;      // which 136-byte block for H
    reg [7:0]  h_byte_in_block;

    // ========================================================================
    // MAIN FSM
    // ========================================================================
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= S_IDLE;
            done <= 1'b0;
            ek_valid <= 1'b0; dk_valid <= 1'b0;
            ek_last <= 1'b0; dk_last <= 1'b0;
            g_start <= 1'b0; h_start <= 1'b0;
            xof_start <= 1'b0; prf_start <= 1'b0;
            ntt_start <= 1'b0; ntt_inverse <= 1'b0;
            bm_start <= 1'b0;
            enc_start <= 1'b0; enc_byte_ready <= 1'b0;
            ns_start <= 1'b0; cbd_start <= 1'b0;
            mem_owner <= MO_NONE;
            ntt_base <= 0; bm_a_base <= 0; bm_b_base <= 0;
            cbd_wr_base <= 0; ns_wr_base <= 0; enc_base <= 0;
            mat_a_addr <= 0; mat_t_addr <= 0; mat_e_addr <= 0;
            mat_i <= 0; mat_j <= 0; vec_i <= 0; ci <= 0;
            byte_total <= 0; prf_counter <= 0;
            copy_ci <= 0; mm_needs_add_e <= 0; doing_inv_ntt <= 0;
            xof_buf_idx <= 0; xof_buf_valid <= 0;
            prf_buf_idx <= 0; prf_buf_valid <= 0;
            ek_buf_idx <= 0; ek_buf_full <= 0;
            h_block <= 0; h_byte_in_block <= 0;
            ns_xof_valid <= 1'b0; cbd_prf_valid <= 1'b0;
            ns_xof_data <= 0; cbd_prf_data <= 0;
        end else begin
            // === Deassert single-cycle pulses ===
            g_start <= 1'b0; h_start <= 1'b0;
            xof_start <= 1'b0; prf_start <= 1'b0;
            ntt_start <= 1'b0; bm_start <= 1'b0;
            enc_start <= 1'b0;
            ns_start <= 1'b0; cbd_start <= 1'b0;

            // === XOF buffer → ntt_sample ===
            // Two-phase handshake: present byte, wait for consumption, then advance.
            // Prevents skipping a byte when ntt_sample transitions away from S_READ.
            if (xof_buf_valid && ns_xof_valid && ns_xof_ready) begin
                // Current byte consumed — advance and present next
                if (xof_buf_idx < 10'd839) begin
                    xof_buf_idx  <= xof_buf_idx + 10'd1;
                    ns_xof_data  <= xof_buf[xof_buf_idx + 10'd1];
                    ns_xof_valid <= 1'b1;
                end else begin
                    xof_buf_valid <= 1'b0;
                    ns_xof_valid  <= 1'b0;
                end
            end else if (xof_buf_valid && !ns_xof_valid) begin
                // No byte currently presented — present the current byte
                ns_xof_data  <= xof_buf[xof_buf_idx];
                ns_xof_valid <= 1'b1;
            end

            // === PRF buffer → cbd_sampler ===
            // Protocol: present a byte when CBD is ready and none presented.
            // When CBD accepts (prf_valid && prf_ready), advance and present
            // next byte. Keep prf_valid high until buffer empty — do NOT
            // clear prf_valid just because cbd_prf_ready drops.
            if (prf_buf_valid && cbd_prf_valid && cbd_prf_ready) begin
                // Byte accepted this cycle — advance to next
                if (prf_buf_idx < 8'd127) begin
                    cbd_prf_data  <= prf_buf[prf_buf_idx + 8'd1];
                    prf_buf_idx   <= prf_buf_idx + 8'd1;
                    cbd_prf_valid <= 1'b1;
                end else begin
                    // Last byte consumed
                    prf_buf_valid <= 1'b0;
                    cbd_prf_valid <= 1'b0;
                end
            end else if (prf_buf_valid && !cbd_prf_valid && cbd_prf_ready) begin
                // CBD needs data and none presented — present current byte
                cbd_prf_data  <= prf_buf[prf_buf_idx];
                cbd_prf_valid <= 1'b1;
            end

            case (state)
                // ============================================================
                S_IDLE: begin
                    done <= 1'b0;
                    mem_owner <= MO_NONE;
                    if (start) begin
                        g_din <= {824'd0, 8'd3, d_seed};
                        g_len <= 8'd33;
                        g_start <= 1'b1; g_last <= 1'b1;
                        state <= S_HASH_G;
                    end
                end

                // ============================================================
                S_HASH_G: begin
                    if (g_done) begin
                        rho   <= g_out[255:0];
                        sigma <= g_out[511:256];
                        mat_i <= 0; mat_j <= 0;
                        xof_din <= {1072'd0, 8'd0, 8'd0, g_out[255:0]};
                        xof_len <= 8'd34;
                        xof_start <= 1'b1; xof_last <= 1'b1;
                        state <= S_GEN_A_XOF;
                    end
                end

                // ============================================================
                // MATRIX A GENERATION
                // ============================================================
                S_GEN_A_XOF: begin
                    if (xof_done) begin
                        for (bi = 0; bi < 840; bi = bi + 1)
                            xof_buf[bi] <= xof_out[bi*8 +: 8];
                        xof_buf_idx <= 0;
                        xof_buf_valid <= 1'b1;
                        ns_xof_valid <= 1'b0;
                        ns_wr_base <= mat_a_addr;
                        mem_owner <= MO_CPU;
                        ns_start <= 1'b1;
                        state <= S_GEN_A_SAMP;
                    end else begin
                        // Compute XOF input: FIPS 203 requires rho || j || i (col j, row i)
                        xof_din <= {1072'd0, {4'd0, mat_i}, {4'd0, mat_j}, rho};
                        xof_len <= 8'd34;
                        xof_start <= 1'b1; xof_last <= 1'b1;
                    end
                end

                S_GEN_A_SAMP: begin
                    if (ns_done) begin
                        xof_buf_valid <= 1'b0;
                        ns_xof_valid <= 1'b0;
                        mem_owner <= MO_NONE;
                        state <= S_GEN_A_NEXT;
                    end
                end

                S_GEN_A_NEXT: begin
                    if (mat_j == 4'd2 && mat_i == 4'd2) begin
                        vec_i <= 0; prf_counter <= 0;
                        prf_din <= {824'd0, 8'd0, sigma};
                        prf_len <= 8'd33;
                        prf_start <= 1'b1; prf_last <= 1'b1;
                        state <= S_CBD_S_PRF;
                    end else begin
                        if (mat_j == 4'd2) begin
                            mat_i <= mat_i + 4'd1; mat_j <= 0;
                            mat_a_addr <= mat_a_addr + N;
                        end else begin
                            mat_j <= mat_j + 4'd1;
                            mat_a_addr <= mat_a_addr + N;
                        end
                        state <= S_GEN_A_XOF;
                    end
                end

                // ============================================================
                // CBD SAMPLING — s[0..2], e[0..2]
                // ============================================================
                S_CBD_S_PRF: begin
                    if (prf_done) begin
                        for (bi = 0; bi < 128; bi = bi + 1)
                            prf_buf[bi] <= prf_out[bi*8 +: 8];
                        prf_buf_idx <= 0;
                        prf_buf_valid <= 1'b1;
                        cbd_wr_base <= S_BASE + {5'd0, vec_i, 8'd0};
                        mem_owner <= MO_CPU;
                        cbd_start <= 1'b1;
                        state <= S_CBD_S_SAMP;
                    end
                end

                S_CBD_S_SAMP: begin
                    if (cbd_done) begin
                        prf_buf_valid <= 1'b0;
                        mem_owner <= MO_NONE;
                        state <= S_CBD_S_NEXT;
                    end
                end

                S_CBD_S_NEXT: begin
                    if (vec_i == 3'd2) begin
                        vec_i <= 0; prf_counter <= 8'd3;
                        prf_din <= {824'd0, 8'd3, sigma};
                        prf_len <= 8'd33;
                        prf_start <= 1'b1; prf_last <= 1'b1;
                        state <= S_CBD_E_PRF;
                    end else begin
                        vec_i <= vec_i + 3'd1;
                        prf_counter <= prf_counter + 8'd1;
                        prf_din <= {824'd0, prf_counter + 8'd1, sigma};
                        prf_len <= 8'd33;
                        prf_start <= 1'b1; prf_last <= 1'b1;
                        state <= S_CBD_S_PRF;
                    end
                end

                S_CBD_E_PRF: begin
                    if (prf_done) begin
                        for (bi = 0; bi < 128; bi = bi + 1)
                            prf_buf[bi] <= prf_out[bi*8 +: 8];
                        prf_buf_idx <= 0;
                        prf_buf_valid <= 1'b1;
                        cbd_wr_base <= E_BASE + {5'd0, vec_i, 8'd0};
                        mem_owner <= MO_CPU;
                        cbd_start <= 1'b1;
                        state <= S_CBD_E_SAMP;
                    end
                end

                S_CBD_E_SAMP: begin
                    if (cbd_done) begin
                        prf_buf_valid <= 1'b0;
                        mem_owner <= MO_NONE;
                        state <= S_CBD_E_NEXT;
                    end
                end

                S_CBD_E_NEXT: begin
                    if (vec_i == 3'd2) begin
                        vec_i <= 0;
                        state <= S_NTT_SETUP;
                    end else begin
                        vec_i <= vec_i + 3'd1;
                        prf_counter <= prf_counter + 8'd1;
                        prf_din <= {824'd0, prf_counter + 8'd1, sigma};
                        prf_len <= 8'd33;
                        prf_start <= 1'b1; prf_last <= 1'b1;
                        state <= S_CBD_E_PRF;
                    end
                end

                // ============================================================
                // NTT FORWARD — s[0..2], e[0..2] (6 total)
                // ============================================================
                S_NTT_SETUP: begin
                    if (doing_inv_ntt)
                        ntt_base <= T_BASE + {5'd0, vec_i, 8'd0};
                    else if (vec_i < 3'd3)
                        ntt_base <= S_BASE + {5'd0, vec_i, 8'd0};
                    else
                        ntt_base <= E_BASE + {5'd0, vec_i - 3'd3, 8'd0};
                    mem_owner <= MO_NTT;
                    ntt_inverse <= doing_inv_ntt;
                    ntt_start <= 1'b1;
                    state <= S_NTT_WAIT;
                end

                S_NTT_WAIT: begin
                    // Wait for NTT core to accept start and clear stale done
                    if (!ntt_done)
                        state <= S_NTT_RUN;
                end

                S_NTT_RUN: begin
                    if (ntt_done)
                        state <= S_NTT_NEXT;
                end

                S_NTT_NEXT: begin
                    if (doing_inv_ntt) begin
                        if (vec_i == 3'd2) begin
                            doing_inv_ntt <= 1'b0;
                            mem_owner <= MO_NONE;
                            state <= S_ENCODE_EK;
                        end else begin
                            vec_i <= vec_i + 3'd1;
                            state <= S_NTT_SETUP;
                        end
                    end else if (vec_i == 3'd5) begin
                        mem_owner <= MO_NONE;
                        mat_i <= 0; mat_j <= 0;
                        copy_ci <= 0; mm_needs_add_e <= 1;
                        // Precompute first matmul addresses
                        mat_t_addr <= T_BASE;
                        mat_e_addr <= E_BASE;
                        mat_a_addr <= A_BASE;
                        state <= S_MM_INIT;
                    end else begin
                        vec_i <= vec_i + 3'd1;
                        state <= S_NTT_SETUP;
                    end
                end

                // ============================================================
                // MATRIX-VECTOR MULTIPLY
                // For each i: T[i] = e[i] + sum_j (A[i][j] * s[j])
                //
                // Step 1 (S_MM_INIT): copy e[i] → T[i] as initial accumulator
                // Step 2 (S_MM_COPY): copy A[i][j] → W
                // Step 3 (S_MM_BM):   basemultiply(W, s[j]) → W = A[i][j]*s[j]
                // Step 4 (S_MM_ACC):  for each k: T[i][k] += W[k]
                // Repeat steps 2-4 for each j, then advance i.
                // ============================================================
                S_MM_INIT: begin
                    // Copy e[i][copy_ci] → T[i][copy_ci] to initialize accumulator
                    if (copy_ci < 9'd256) begin
                        coeff_mem[T_BASE + mat_i[1:0] * N + {5'd0, copy_ci}] <=
                            coeff_mem[E_BASE + mat_i[1:0] * N + {5'd0, copy_ci}];
                        copy_ci <= copy_ci + 9'd1;
                    end else begin
                        // e[i] copied to T[i]. Start j-loop.
                        mat_j <= 0;
                        copy_ci <= 0;
                        // Precompute A[i][0] base
                        mat_a_addr <= A_BASE + mat_i[1:0] * (K * N);
                        state <= S_MM_COPY;
                    end
                end

                S_MM_COPY: begin
                    // Copy A[i][j][copy_ci] → W[copy_ci]
                    if (copy_ci < 9'd256) begin
                        coeff_mem[W_BASE + {5'd0, copy_ci}] <=
                            coeff_mem[mat_a_addr + mat_j[1:0] * N + {5'd0, copy_ci}];
                        copy_ci <= copy_ci + 9'd1;
                    end else begin
                        // A[i][j] copied to W. Run basemultiply.
                        bm_a_base <= W_BASE;
                        bm_b_base <= S_BASE + {5'd0, mat_j, 8'd0};
                        mem_owner <= MO_BM;
                        bm_start <= 1'b1;
                        copy_ci <= 0;
                        state <= S_MM_BM;
                    end
                end

                S_MM_BM: begin
                    if (bm_done) begin
                        mem_owner <= MO_NONE;
                        // Accumulate: T[i][k] += W[k]
                        // Read T[i][0] and W[0] to start
                        acc_read_val <= coeff_mem[T_BASE + mat_i[1:0] * N];
                        acc_w_val    <= coeff_mem[W_BASE];
                        copy_ci <= 0;
                        state <= S_MM_ACC;
                    end
                end

                S_MM_ACC: begin
                    // Write accumulated result to T[i][copy_ci]
                    // (acc_sum computed combinationally from acc_read_val + acc_w_val)
                    coeff_mem[T_BASE + mat_i[1:0] * N + {5'd0, copy_ci}] <= acc_result;
                    copy_ci <= copy_ci + 9'd1;
                    // Pre-read next pair for next cycle
                    if (copy_ci < 9'd255) begin
                        acc_read_val <= coeff_mem[T_BASE + mat_i[1:0] * N + {5'd0, copy_ci + 9'd1}];
                        acc_w_val    <= coeff_mem[W_BASE + {5'd0, copy_ci + 9'd1}];
                    end
                    // Done with this j's accumulation?
                    if (copy_ci == 9'd255) begin
                        state <= S_MM_NEXT_J;
                    end
                end

                S_MM_NEXT_J: begin
                    if (mat_j == 4'd2) begin
                        state <= S_MM_NEXT_I;
                    end else begin
                        mat_j <= mat_j + 4'd1;
                        copy_ci <= 0;
                        state <= S_MM_COPY;
                    end
                end

                S_MM_NEXT_I: begin
                    if (mat_i == 4'd2) begin
                        // Matmul done. T[0..2] already holds t_hat in NTT domain.
                        // FIPS 203: ek = ByteEncode_12(t_hat) || rho — no INTT needed.
                        mem_owner <= MO_NONE;
                        state <= S_ENCODE_EK;
                    end else begin
                        mat_i <= mat_i + 4'd1;
                        mat_j <= 0;
                        copy_ci <= 0;
                        mat_t_addr <= T_BASE + (mat_i + 4'd1) * N;
                        mat_e_addr <= E_BASE + (mat_i + 4'd1) * N;
                        mat_a_addr <= A_BASE + (mat_i + 4'd1) * (K * N);
                        state <= S_MM_INIT;
                    end
                end

                // ============================================================
                // KEY ENCODE — ek_pke = Encode(t_hat,12) || rho
                // Encode t_hat (1152 bytes) + rho (32 bytes) = 1184 bytes
                // Stream to ek output AND buffer for dk
                // ============================================================
                S_ENCODE_EK: begin
                    enc_base <= T_BASE;
                    enc_byte_ready <= 1'b1;
                    enc_start <= 1'b1;
                    byte_total <= 0;
                    ek_buf_idx <= 0;
                    ek_buf_full <= 0;
                    state <= S_ENCODE_DK;
                end

                S_ENCODE_DK: begin
                    if (enc_byte_valid && ek_ready) begin
                        // Stream to ek output
                        ek_byte <= enc_byte_out;
                        ek_valid <= 1'b1;
                        // Buffer for H computation and dk
                        ek_buf[ek_buf_idx] <= enc_byte_out;
                        ek_buf_idx <= ek_buf_idx + 11'd1;
                        byte_total <= byte_total + 12'd1;
                    end else begin
                        ek_valid <= 1'b0;
                    end
                    if (enc_done) begin
                        // key_encode finished 1152 bytes. Now start rho phase.
                        ek_valid <= 1'b0; ek_last <= 1'b0;
                        mem_owner <= MO_NONE;
                        enc_byte_ready <= 1'b0;
                        byte_total <= 0;
                        state <= S_EK_RHO;
                    end
                end

                // ============================================================
                // EK: append rho (32 bytes) after encode(t_hat)
                // ============================================================
                S_EK_RHO: begin
                    if (byte_total < 12'd32) begin
                        ek_byte <= rho[byte_total*8 +: 8];
                        ek_valid <= 1'b1;
                        // Also buffer rho for dk computation
                        ek_buf[ek_buf_idx] <= rho[byte_total*8 +: 8];
                        ek_buf_idx <= ek_buf_idx + 11'd1;
                        byte_total <= byte_total + 12'd1;
                        if (byte_total == 12'd31)
                            ek_last <= 1'b1;
                    end else begin
                        ek_valid <= 1'b0; ek_last <= 1'b0;
                        ek_buf_full <= 1'b1;
                        // Start dk: encode s_hat
                        byte_total <= 0;
                        enc_base <= S_BASE;
                        enc_byte_ready <= 1'b1;
                        enc_start <= 1'b1;
                        dk_valid <= 1'b0;
                        state <= S_DK_ENC_S;
                    end
                end

                // ============================================================
                // DK: encode s_hat → dk_pke (1152 bytes)
                // ============================================================
                S_DK_ENC_S: begin
                    if (enc_byte_valid && dk_ready) begin
                        dk_byte <= enc_byte_out;
                        dk_valid <= 1'b1;
                        byte_total <= byte_total + 12'd1;
                    end else begin
                        dk_valid <= 1'b0;
                    end
                    if (enc_done) begin
                        // dk_pke done. Now output ek_pke from buffer.
                        dk_valid <= 1'b0;
                        enc_byte_ready <= 1'b0;
                        ek_buf_idx <= 0;
                        byte_total <= 0;
                        state <= S_DK_EK_OUT;
                    end
                end

                // ============================================================
                // DK: output ek_pke from buffer (1184 bytes)
                // ============================================================
                S_DK_EK_OUT: begin
                    if (dk_ready) begin
                        dk_byte <= ek_buf[ek_buf_idx];
                        dk_valid <= 1'b1;
                        ek_buf_idx <= ek_buf_idx + 11'd1;
                        byte_total <= byte_total + 12'd1;
                        if (byte_total == 12'd1182) begin
                            // Next cycle will be the last byte (1183)
                            // After that, transition to H computation
                        end
                        if (byte_total == 12'd1183) begin
                            byte_total <= 0;
                            h_block <= 0;
                            h_byte_in_block <= 0;
                            h_din <= 0;
                            h_len <= 0;
                            h_start <= 1'b0; h_last <= 1'b0;
                            state <= S_DK_H_SETUP;
                        end
                    end else begin
                        dk_valid <= 1'b0;
                    end
                end

                // ============================================================
                // DK: compute H(ek_pke)
                // Feed ek_buf in 136-byte blocks to SHAKE/SHA3
                // 1184 bytes = 8 full blocks (1088) + 1 partial (96)
                // SHAKE pulses ready for intermediate blocks, done for last
                // ============================================================
                S_DK_H_SETUP: begin
                    dk_valid <= 1'b0;
                    // Build first block from ek_buf[0:135]
                    for (bi = 0; bi < 136; bi = bi + 1)
                        h_din[bi*8 +: 8] <= ek_buf[bi];
                    h_len <= 8'd136;
                    h_start <= 1'b1;
                    h_last <= 1'b0;
                    h_block <= 0;
                    state <= S_DK_H_ABSORB;
                end

                S_DK_H_ABSORB: begin
                    h_start <= 1'b0;
                    if (h_done) begin
                        // H is complete (last block processed)
                        state <= S_DK_H_WAIT;
                    end else if (h_ready) begin
                        h_block <= h_block + 4'd1;
                        if (h_block == 4'd7) begin
                            // Next block is last partial (96 bytes)
                            for (bi = 0; bi < 136; bi = bi + 1)
                                h_din[bi*8 +: 8] <= (1088 + bi < 1184) ? ek_buf[1088 + bi] : 8'd0;
                            h_len <= 8'd96;
                            h_last <= 1'b1;
                            h_start <= 1'b1;
                        end else begin
                            // Full block: block N+1 starts at byte (N+1)*136
                            for (bi = 0; bi < 136; bi = bi + 1)
                                h_din[bi*8 +: 8] <= ek_buf[{(h_block+4'd1), 7'd0} + {(h_block+4'd1), 3'd0} + {4'd0, bi}];
                            h_len <= 8'd136;
                            h_last <= 1'b0;
                            h_start <= 1'b1;
                        end
                    end
                end

                S_DK_H_WAIT: begin
                    // h_done was already seen, H result is in h_out
                    byte_total <= 0;
                    state <= S_DK_H_OUT;
                end

                // ============================================================
                // DK: output H(ek_pke) (32 bytes) + z (32 bytes)
                // ============================================================
                S_DK_H_OUT: begin
                    if (byte_total < 12'd32) begin
                        // Output H result
                        dk_byte <= h_out[byte_total*8 +: 8];
                        dk_valid <= 1'b1;
                    end else if (byte_total < 12'd64) begin
                        // Output z seed
                        dk_byte <= z_seed[(byte_total - 12'd32)*8 +: 8];
                        dk_valid <= 1'b1;
                    end else begin
                        dk_valid <= 1'b0;
                        dk_last <= 1'b1;
                        state <= S_ZEROIZE;
                    end
                    byte_total <= byte_total + 12'd1;
                end

                // ============================================================
                // ZEROIZE
                // ============================================================
                S_ZEROIZE: begin
                    state <= S_DONE;
                end

                // ============================================================
                S_DONE: begin
                    done <= 1'b1;
                    ek_valid <= 1'b0; dk_valid <= 1'b0;
                    ek_last <= 1'b0; dk_last <= 1'b0;
                    mem_owner <= MO_NONE;
                    state <= S_IDLE;
                end

                default: state <= S_IDLE;
            endcase
        end
    end

endmodule