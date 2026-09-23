module ntt_core #(
    parameter Q_WIDTH      = 12,
    parameter Q            = 3329,
    parameter N            = 256,
    parameter NUM_BUT      = 1,
    parameter LOG2_N       = 8,
    parameter BANKS        = 1
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

    localparam S_IDLE    = 3'd0;
    localparam S_LOAD    = 3'd1;
    localparam S_BREV    = 3'd2;
    localparam S_COMPUTE = 3'd3;
    localparam S_SCALE   = 3'd4;
    localparam S_WRITE   = 3'd5;
    localparam S_DONE    = 3'd6;
    localparam S_FETCH   = 3'd7;

    reg [2:0] state;
    reg [LOG2_N-1:0] stage_counter;
    reg [LOG2_N-1:0] pair_idx;
    reg [8:0]       load_idx;
    reg [8:0]       write_idx;

    reg [Q_WIDTH-1:0] coeff_buf [0:N-1];

    reg  [Q_WIDTH-1:0] bf_a, bf_b, bf_tw;
    wire [Q_WIDTH-1:0] bf_a_out, bf_b_out;
    reg                  bf_valid;
    wire                 bf_done;
    reg                  bf_busy;

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

    function [LOG2_N-1:0] compute_addr_a;
        input [LOG2_N-1:0] stage, pair;
        reg [LOG2_N-1:0] m, base, offset;
        begin
            m = 1 << stage;
            base = (pair / m) * (2 * m);
            offset = pair % m;
            compute_addr_a = base + offset;
        end
    endfunction

    function [LOG2_N-1:0] compute_addr_b;
        input [LOG2_N-1:0] stage, pair;
        reg [LOG2_N-1:0] m, base, offset;
        begin
            m = 1 << stage;
            base = (pair / m) * (2 * m);
            offset = pair % m;
            compute_addr_b = base + m + offset;
        end
    endfunction

    function [9:0] compute_tw_index;
        input [LOG2_N-1:0] stage, pair;
        reg [LOG2_N-1:0] m, pos;
        begin
            m = 1 << stage;
            pos = pair % m;
            compute_tw_index = stage * (N >> 1) + pos;
        end
    endfunction

    ntt_butterfly #(.Q_WIDTH(Q_WIDTH), .Q(Q)) butterfly_inst (
        .clk(clk),
        .rst_n(rst_n),
        .valid(bf_valid),
        .a(bf_a),
        .b(bf_b),
        .tw(bf_tw),
        .a_out(bf_a_out),
        .b_out(bf_b_out),
        .done(bf_done)
    );

    reg [LOG2_N-1:0] si_a, si_b;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state         <= S_IDLE;
            done          <= 0;
            cycles        <= 0;
            bf_valid      <= 0;
            bf_busy       <= 0;
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
                    done  <= 1'b0;
                    cycles <= 0;
                    mem_we <= 1'b0;
                    mem_re <= 1'b0;
                    bf_valid <= 1'b0;
                    bf_busy  <= 1'b0;
                    if (start) begin
                        load_idx <= 0;
                        state <= S_LOAD;
                    end
                end

                S_LOAD: begin
                    mem_re <= 1'b1;
                    mem_addr <= load_idx;
                    if (load_idx > 0) begin
                        coeff_buf[load_idx - 1] = mem_rdata;
                    end
                    if (load_idx == N) begin
                        coeff_buf[N - 1] = mem_rdata;
                        mem_re <= 1'b0;
                        state <= S_BREV;
                        load_idx <= 0;
                    end else begin
                        load_idx <= load_idx + 1;
                    end
                end

                S_BREV: begin
                    if (load_idx < N) begin
                        si_a = bit_reverse(load_idx);
                        if (load_idx < si_a) begin
                            coeff_buf[load_idx] <= coeff_buf[si_a];
                            coeff_buf[si_a] <= coeff_buf[load_idx];
                        end
                        load_idx <= load_idx + 1;
                    end else begin
                        stage_counter <= 0;
                        pair_idx <= 0;
                        bf_busy <= 1'b0;
                        state <= S_COMPUTE;
                    end
                end

                S_COMPUTE: begin
                    cycles <= cycles + 1;

                    if (bf_busy && bf_done) begin
                        si_a = compute_addr_a(stage_counter, pair_idx);
                        si_b = compute_addr_b(stage_counter, pair_idx);
                        coeff_buf[si_a] = bf_a_out;
                        coeff_buf[si_b] = bf_b_out;
                        bf_valid <= 1'b0;
                        bf_busy  <= 1'b0;

                        if (pair_idx == N/2 - 1) begin
                            if (stage_counter == LOG2_N - 1) begin
                                state <= inverse ? S_SCALE : S_WRITE;
                                write_idx <= 0;
                            end else begin
                                stage_counter <= stage_counter + 1;
                                pair_idx <= 0;
                            end
                        end else begin
                            pair_idx <= pair_idx + 1;
                        end
                    end else if (!bf_busy) begin
                        bf_a     <= coeff_buf[compute_addr_a(stage_counter, pair_idx)];
                        bf_b     <= coeff_buf[compute_addr_b(stage_counter, pair_idx)];
                        tw_addr  <= compute_tw_index(stage_counter, pair_idx);
                        if (inverse && stage_counter < 4 && pair_idx < 2)
                            $display("    NTT_START: stage=%0d pair=%0d a=%h b=%h tw_idx=%0d", stage_counter, pair_idx, coeff_buf[compute_addr_a(stage_counter, pair_idx)], coeff_buf[compute_addr_b(stage_counter, pair_idx)], compute_tw_index(stage_counter, pair_idx));
                        state    <= S_FETCH;
                    end
                end

                S_FETCH: begin
                    bf_tw    <= tw_rdata;
                    bf_valid <= 1'b1;
                    bf_busy  <= 1'b1;
                    state    <= S_COMPUTE;
                    if (inverse && stage_counter < 4 && pair_idx < 2)
                        $display("    NTT_FETCH: stage=%0d pair=%0d tw_addr=%0d tw=%h", stage_counter, pair_idx, tw_addr, tw_rdata);
                end

                S_COMPUTE: begin
                    cycles <= cycles + 1;

                    if (bf_busy && bf_done) begin
                        si_a = compute_addr_a(stage_counter, pair_idx);
                        si_b = compute_addr_b(stage_counter, pair_idx);
                        if (inverse && stage_counter < 4 && pair_idx < 2)
                            $display("    NTT_DONE: stage=%0d pair=%0d a_addr=%0d b_addr=%0d a_out=%h b_out=%h", stage_counter, pair_idx, si_a, si_b, bf_a_out, bf_b_out);
                        coeff_buf[si_a] = bf_a_out;
                        coeff_buf[si_b] = bf_b_out;
                        bf_valid <= 1'b0;
                        bf_busy  <= 1'b0;

                        if (pair_idx == N/2 - 1) begin
                            if (stage_counter == LOG2_N - 1) begin
                                state <= inverse ? S_SCALE : S_WRITE;
                                write_idx <= 0;
                            end else begin
                                stage_counter <= stage_counter + 1;
                                pair_idx <= 0;
                            end
                        end else begin
                            pair_idx <= pair_idx + 1;
                        end
                    end else if (!bf_busy) begin
                        bf_a     <= coeff_buf[compute_addr_a(stage_counter, pair_idx)];
                        bf_b     <= coeff_buf[compute_addr_b(stage_counter, pair_idx)];
                        tw_addr  <= compute_tw_index(stage_counter, pair_idx);
                        if (inverse && stage_counter < 4 && pair_idx < 2)
                            $display("    NTT_START: stage=%0d pair=%0d a=%h b=%h tw_idx=%0d", stage_counter, pair_idx, coeff_buf[compute_addr_a(stage_counter, pair_idx)], coeff_buf[compute_addr_b(stage_counter, pair_idx)], compute_tw_index(stage_counter, pair_idx));
                        state    <= S_FETCH;
                    end
                end

                S_SCALE: begin
                    if (write_idx < N) begin
                        if (write_idx < 4)
                            $display("    NTT_SCALE_PRE: idx=%0d before=%h (will become %h)", write_idx, coeff_buf[write_idx], ({{Q_WIDTH{1'b0}}, coeff_buf[write_idx]} * N_INV) % Q);
                        coeff_buf[write_idx] = ({{Q_WIDTH{1'b0}}, coeff_buf[write_idx]} * N_INV) % Q;
                        if (write_idx < 4)
                            $display("    NTT_SCALE_POST: idx=%0d after=%h", write_idx, coeff_buf[write_idx]);
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

    localparam [Q_WIDTH-1:0] N_INV = 12'd3316;

endmodule
