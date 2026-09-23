// QuantumVault R0 — NTT butterfly unit
// Cooley-Tukey butterfly: (a + tw*b, a - tw*b) mod q
// Parameterized for ML-KEM (q=3329, 12-bit) or ML-DSA (q=8380417, 23-bit)

module ntt_butterfly #(
    parameter Q_WIDTH = 12,
    parameter Q = 3329
)(
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  valid,
    input  wire [Q_WIDTH-1:0]   a,
    input  wire [Q_WIDTH-1:0]   b,
    input  wire [Q_WIDTH-1:0]   tw,
    output reg  [Q_WIDTH-1:0]   a_out,
    output reg  [Q_WIDTH-1:0]   b_out,
    output reg                   done
);

    reg [1:0] stage;
    reg [Q_WIDTH-1:0] tw_b;
    reg [Q_WIDTH:0] sum, diff;
    reg [Q_WIDTH-1:0] sum_mod, diff_mod;
    reg valid_d;

    wire valid_rise = valid & ~valid_d;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) valid_d <= 0;
        else valid_d <= valid;
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            stage  <= 0;
            done   <= 0;
            a_out  <= 0;
            b_out  <= 0;
            tw_b   <= 0;
            sum    <= 0;
            diff   <= 0;
        end else begin
            case (stage)
                2'd0: begin
                    done <= 1'b0;
                    if (valid_rise) begin
                        tw_b <= ({{Q_WIDTH{1'b0}}, tw} * b) % Q;
                        stage <= 2'd1;
                    end
                end
                2'd1: begin
                    sum  <= a + tw_b;
                    diff <= a + Q - tw_b;
                    stage <= 2'd2;
                end
                2'd2: begin
                    sum_mod  <= (sum >= Q)  ? sum - Q  : sum[Q_WIDTH-1:0];
                    diff_mod <= (diff >= Q) ? diff - Q : diff[Q_WIDTH-1:0];
                    stage <= 2'd3;
                end
                2'd3: begin
                    a_out <= sum_mod;
                    b_out <= diff_mod;
                    done  <= 1'b1;
                    stage <= 2'd0;
                end
            endcase
        end
    end

endmodule
