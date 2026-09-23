// QuantumVault Gate 9C — BaseCaseMultiply
// FIPS 203 MultiplyNTTs: schoolbook multiply in groups of 4
// c[4i]   = (a0*b0 + zeta * a1*b1) mod q
// c[4i+1] = (a1*b0 + a0*b1) mod q
// c[4i+2] = (a2*b2 - zeta * a3*b3) mod q   (neg_zeta = q - zeta)
// c[4i+3] = (a3*b2 + a2*b3) mod q
// zeta = ZETAS[64 + i] for group i, gamma=17, bit-reversed

module basemultiply #(
    parameter Q_WIDTH = 12,
    parameter Q       = 3329,
    parameter N       = 256,
    parameter LOG2_N  = 8
)(
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  start,
    output reg                   done,

    output reg  [LOG2_N-1:0]    addr_a,
    output reg  [Q_WIDTH-1:0]   wdata_a,
    input  wire [Q_WIDTH-1:0]   rdata_a,
    output reg                   we_a,
    output reg                   re_a,

    output reg  [LOG2_N-1:0]    addr_b,
    input  wire [Q_WIDTH-1:0]   rdata_b,
    output reg                   re_b,

    output reg  [LOG2_N-1:0]    tw_addr,
    input  wire [Q_WIDTH-1:0]   tw_rdata
);

    localparam S_IDLE  = 4'd0;
    localparam S_RD0   = 4'd1;
    localparam S_RD1   = 4'd2;
    localparam S_RD2   = 4'd3;
    localparam S_RD3   = 4'd4;
    localparam S_COMP  = 4'd5;
    localparam S_WR0   = 4'd6;
    localparam S_WR1   = 4'd7;
    localparam S_WR2   = 4'd8;
    localparam S_WR3   = 4'd9;

    reg [3:0]  state;
    reg [5:0]  group;
    reg [Q_WIDTH-1:0] a0, a1, a2, a3;
    reg [Q_WIDTH-1:0] b0, b1, b2, b3;
    reg [Q_WIDTH-1:0] zeta, neg_zeta;
    reg [Q_WIDTH-1:0] c0_r, c1_r, c2_r, c3_r;

    // ---- Internal ZETAS[64..127] lookup (twiddle ROM doesn't store these) ----
    reg [Q_WIDTH-1:0] zeta_lookup, neg_zeta_lookup;
    always @(*) begin
        case (group)
            6'd 0: begin zeta_lookup = 12'd  17; neg_zeta_lookup = 12'd3312; end
            6'd 1: begin zeta_lookup = 12'd2761; neg_zeta_lookup = 12'd 568; end
            6'd 2: begin zeta_lookup = 12'd 583; neg_zeta_lookup = 12'd2746; end
            6'd 3: begin zeta_lookup = 12'd2649; neg_zeta_lookup = 12'd 680; end
            6'd 4: begin zeta_lookup = 12'd1637; neg_zeta_lookup = 12'd1692; end
            6'd 5: begin zeta_lookup = 12'd 723; neg_zeta_lookup = 12'd2606; end
            6'd 6: begin zeta_lookup = 12'd2288; neg_zeta_lookup = 12'd1041; end
            6'd 7: begin zeta_lookup = 12'd1100; neg_zeta_lookup = 12'd2229; end
            6'd 8: begin zeta_lookup = 12'd1409; neg_zeta_lookup = 12'd1920; end
            6'd 9: begin zeta_lookup = 12'd2662; neg_zeta_lookup = 12'd 667; end
            6'd10: begin zeta_lookup = 12'd3281; neg_zeta_lookup = 12'd  48; end
            6'd11: begin zeta_lookup = 12'd 233; neg_zeta_lookup = 12'd3096; end
            6'd12: begin zeta_lookup = 12'd 756; neg_zeta_lookup = 12'd2573; end
            6'd13: begin zeta_lookup = 12'd2156; neg_zeta_lookup = 12'd1173; end
            6'd14: begin zeta_lookup = 12'd3015; neg_zeta_lookup = 12'd 314; end
            6'd15: begin zeta_lookup = 12'd3050; neg_zeta_lookup = 12'd 279; end
            6'd16: begin zeta_lookup = 12'd1703; neg_zeta_lookup = 12'd1626; end
            6'd17: begin zeta_lookup = 12'd1651; neg_zeta_lookup = 12'd1678; end
            6'd18: begin zeta_lookup = 12'd2789; neg_zeta_lookup = 12'd 540; end
            6'd19: begin zeta_lookup = 12'd1789; neg_zeta_lookup = 12'd1540; end
            6'd20: begin zeta_lookup = 12'd1847; neg_zeta_lookup = 12'd1482; end
            6'd21: begin zeta_lookup = 12'd 952; neg_zeta_lookup = 12'd2377; end
            6'd22: begin zeta_lookup = 12'd1461; neg_zeta_lookup = 12'd1868; end
            6'd23: begin zeta_lookup = 12'd2687; neg_zeta_lookup = 12'd 642; end
            6'd24: begin zeta_lookup = 12'd 939; neg_zeta_lookup = 12'd2390; end
            6'd25: begin zeta_lookup = 12'd2308; neg_zeta_lookup = 12'd1021; end
            6'd26: begin zeta_lookup = 12'd2437; neg_zeta_lookup = 12'd 892; end
            6'd27: begin zeta_lookup = 12'd2388; neg_zeta_lookup = 12'd 941; end
            6'd28: begin zeta_lookup = 12'd 733; neg_zeta_lookup = 12'd2596; end
            6'd29: begin zeta_lookup = 12'd2337; neg_zeta_lookup = 12'd 992; end
            6'd30: begin zeta_lookup = 12'd 268; neg_zeta_lookup = 12'd3061; end
            6'd31: begin zeta_lookup = 12'd 641; neg_zeta_lookup = 12'd2688; end
            6'd32: begin zeta_lookup = 12'd1584; neg_zeta_lookup = 12'd1745; end
            6'd33: begin zeta_lookup = 12'd2298; neg_zeta_lookup = 12'd1031; end
            6'd34: begin zeta_lookup = 12'd2037; neg_zeta_lookup = 12'd1292; end
            6'd35: begin zeta_lookup = 12'd3220; neg_zeta_lookup = 12'd 109; end
            6'd36: begin zeta_lookup = 12'd 375; neg_zeta_lookup = 12'd2954; end
            6'd37: begin zeta_lookup = 12'd2549; neg_zeta_lookup = 12'd 780; end
            6'd38: begin zeta_lookup = 12'd2090; neg_zeta_lookup = 12'd1239; end
            6'd39: begin zeta_lookup = 12'd1645; neg_zeta_lookup = 12'd1684; end
            6'd40: begin zeta_lookup = 12'd1063; neg_zeta_lookup = 12'd2266; end
            6'd41: begin zeta_lookup = 12'd 319; neg_zeta_lookup = 12'd3010; end
            6'd42: begin zeta_lookup = 12'd2773; neg_zeta_lookup = 12'd 556; end
            6'd43: begin zeta_lookup = 12'd 757; neg_zeta_lookup = 12'd2572; end
            6'd44: begin zeta_lookup = 12'd2099; neg_zeta_lookup = 12'd1230; end
            6'd45: begin zeta_lookup = 12'd 561; neg_zeta_lookup = 12'd2768; end
            6'd46: begin zeta_lookup = 12'd2466; neg_zeta_lookup = 12'd 863; end
            6'd47: begin zeta_lookup = 12'd2594; neg_zeta_lookup = 12'd 735; end
            6'd48: begin zeta_lookup = 12'd2804; neg_zeta_lookup = 12'd 525; end
            6'd49: begin zeta_lookup = 12'd1092; neg_zeta_lookup = 12'd2237; end
            6'd50: begin zeta_lookup = 12'd 403; neg_zeta_lookup = 12'd2926; end
            6'd51: begin zeta_lookup = 12'd1026; neg_zeta_lookup = 12'd2303; end
            6'd52: begin zeta_lookup = 12'd1143; neg_zeta_lookup = 12'd2186; end
            6'd53: begin zeta_lookup = 12'd2150; neg_zeta_lookup = 12'd1179; end
            6'd54: begin zeta_lookup = 12'd2775; neg_zeta_lookup = 12'd 554; end
            6'd55: begin zeta_lookup = 12'd 886; neg_zeta_lookup = 12'd2443; end
            6'd56: begin zeta_lookup = 12'd1722; neg_zeta_lookup = 12'd1607; end
            6'd57: begin zeta_lookup = 12'd1212; neg_zeta_lookup = 12'd2117; end
            6'd58: begin zeta_lookup = 12'd1874; neg_zeta_lookup = 12'd1455; end
            6'd59: begin zeta_lookup = 12'd1029; neg_zeta_lookup = 12'd2300; end
            6'd60: begin zeta_lookup = 12'd2110; neg_zeta_lookup = 12'd1219; end
            6'd61: begin zeta_lookup = 12'd2935; neg_zeta_lookup = 12'd 394; end
            6'd62: begin zeta_lookup = 12'd 885; neg_zeta_lookup = 12'd2444; end
            6'd63: begin zeta_lookup = 12'd2154; neg_zeta_lookup = 12'd1175; end
        endcase
    end

    // ---- Combinational multiplies ----
    wire [Q_WIDTH-1:0] p00, p01, p_zp01;
    wire [Q_WIDTH-1:0] p10, p11;
    wire [Q_WIDTH-1:0] p20, p21, p_np21;
    wire [Q_WIDTH-1:0] p30, p31;

    mod_q_mul #(.Q_WIDTH(Q_WIDTH), .Q(Q)) mul00 (.a(a0), .b(b0), .result(p00));
    mod_q_mul #(.Q_WIDTH(Q_WIDTH), .Q(Q)) mul01 (.a(a1), .b(b1), .result(p01));
    mod_q_mul #(.Q_WIDTH(Q_WIDTH), .Q(Q)) mul_zp01 (.a(zeta), .b(p01), .result(p_zp01));

    mod_q_mul #(.Q_WIDTH(Q_WIDTH), .Q(Q)) mul10 (.a(a1), .b(b0), .result(p10));
    mod_q_mul #(.Q_WIDTH(Q_WIDTH), .Q(Q)) mul11 (.a(a0), .b(b1), .result(p11));

    mod_q_mul #(.Q_WIDTH(Q_WIDTH), .Q(Q)) mul20 (.a(a2), .b(b2), .result(p20));
    mod_q_mul #(.Q_WIDTH(Q_WIDTH), .Q(Q)) mul21 (.a(a3), .b(b3), .result(p21));
    mod_q_mul #(.Q_WIDTH(Q_WIDTH), .Q(Q)) mul_np21 (.a(neg_zeta), .b(p21), .result(p_np21));

    mod_q_mul #(.Q_WIDTH(Q_WIDTH), .Q(Q)) mul30 (.a(a3), .b(b2), .result(p30));
    mod_q_mul #(.Q_WIDTH(Q_WIDTH), .Q(Q)) mul31 (.a(a2), .b(b3), .result(p31));

    // ---- Combinational modular addition ----
    wire [Q_WIDTH:0] sum_c0 = {1'b0, p00} + {1'b0, p_zp01};
    wire [Q_WIDTH-1:0] c0 = (sum_c0 >= Q) ? sum_c0[Q_WIDTH-1:0] - Q[Q_WIDTH-1:0]
                                            : sum_c0[Q_WIDTH-1:0];

    wire [Q_WIDTH:0] sum_c1 = {1'b0, p10} + {1'b0, p11};
    wire [Q_WIDTH-1:0] c1 = (sum_c1 >= Q) ? sum_c1[Q_WIDTH-1:0] - Q[Q_WIDTH-1:0]
                                            : sum_c1[Q_WIDTH-1:0];

    wire [Q_WIDTH:0] sum_c2 = {1'b0, p20} + {1'b0, p_np21};
    wire [Q_WIDTH-1:0] c2 = (sum_c2 >= Q) ? sum_c2[Q_WIDTH-1:0] - Q[Q_WIDTH-1:0]
                                            : sum_c2[Q_WIDTH-1:0];

    wire [Q_WIDTH:0] sum_c3 = {1'b0, p30} + {1'b0, p31};
    wire [Q_WIDTH-1:0] c3 = (sum_c3 >= Q) ? sum_c3[Q_WIDTH-1:0] - Q[Q_WIDTH-1:0]
                                            : sum_c3[Q_WIDTH-1:0];

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state   <= S_IDLE;
            done    <= 1'b0;
            group   <= 0;
            addr_a  <= 0;
            wdata_a <= 0;
            we_a    <= 1'b0;
            re_a    <= 1'b0;
            addr_b  <= 0;
            re_b    <= 1'b0;
            tw_addr <= 0;
            a0 <= 0; a1 <= 0; a2 <= 0; a3 <= 0;
            b0 <= 0; b1 <= 0; b2 <= 0; b3 <= 0;
            zeta <= 0; neg_zeta <= 0;
            c0_r <= 0; c1_r <= 0; c2_r <= 0; c3_r <= 0;
        end else begin
            case (state)
                S_IDLE: begin
                    done  <= 1'b0;
                    we_a  <= 1'b0;
                    re_a  <= 1'b0;
                    re_b  <= 1'b0;
                    tw_addr <= 0;
                    if (start) begin
                        group <= 0;
                        addr_a <= 0;
                        re_a   <= 1'b1;
                        addr_b <= 0;
                        re_b   <= 1'b1;
                        state  <= S_RD0;
                    end
                end

                S_RD0: begin
                    re_a <= 1'b0;
                    re_b <= 1'b0;
                    a0 <= rdata_a;
                    b0 <= rdata_b;
                    zeta <= zeta_lookup;
                    neg_zeta <= neg_zeta_lookup;
                    addr_a <= {group, 2'b00} + 8'd1;
                    re_a   <= 1'b1;
                    addr_b <= {group, 2'b00} + 8'd1;
                    re_b   <= 1'b1;
                    state  <= S_RD1;
                end

                S_RD1: begin
                    re_a <= 1'b0;
                    re_b <= 1'b0;
                    a1 <= rdata_a;
                    b1 <= rdata_b;
                    addr_a <= {group, 2'b00} + 8'd2;
                    re_a   <= 1'b1;
                    addr_b <= {group, 2'b00} + 8'd2;
                    re_b   <= 1'b1;
                    state  <= S_RD2;
                end

                S_RD2: begin
                    re_a <= 1'b0;
                    re_b <= 1'b0;
                    a2 <= rdata_a;
                    b2 <= rdata_b;
                    addr_a <= {group, 2'b00} + 8'd3;
                    re_a   <= 1'b1;
                    addr_b <= {group, 2'b00} + 8'd3;
                    re_b   <= 1'b1;
                    state  <= S_RD3;
                end

                S_RD3: begin
                    re_a <= 1'b0;
                    re_b <= 1'b0;
                    a3 <= rdata_a;
                    b3 <= rdata_b;
                    state <= S_COMP;
                end

                S_COMP: begin
                    c0_r <= c0;
                    c1_r <= c1;
                    c2_r <= c2;
                    c3_r <= c3;
                    addr_a  <= {group, 2'b00};
                    wdata_a <= c0;
                    we_a    <= 1'b1;
                    state   <= S_WR0;
                end

                S_WR0: begin
                    we_a    <= 1'b0;
                    addr_a  <= {group, 2'b00} + 8'd1;
                    wdata_a <= c1_r;
                    we_a    <= 1'b1;
                    state   <= S_WR1;
                end

                S_WR1: begin
                    we_a    <= 1'b0;
                    addr_a  <= {group, 2'b00} + 8'd2;
                    wdata_a <= c2_r;
                    we_a    <= 1'b1;
                    state   <= S_WR2;
                end

                S_WR2: begin
                    we_a    <= 1'b0;
                    addr_a  <= {group, 2'b00} + 8'd3;
                    wdata_a <= c3_r;
                    we_a    <= 1'b1;
                    state   <= S_WR3;
                end

                S_WR3: begin
                    we_a <= 1'b0;
                    if (group == 6'd63) begin
                        state <= S_IDLE;
                        done  <= 1'b1;
                    end else begin
                        group <= group + 1;
                        addr_a  <= {group + 6'd1, 2'b00};
                        re_a    <= 1'b1;
                        addr_b  <= {group + 6'd1, 2'b00};
                        re_b    <= 1'b1;
                        state   <= S_RD0;
                    end
                end

                default: state <= S_IDLE;
            endcase
        end
    end

endmodule
