// QuantumVault — Gentleman-Sande (GS) NTT Butterfly
// For FIPS 203 Algorithm 10 (Inverse NTT)
// a_out = a + b (mod q)
// b_out = tw * (b - a) (mod q)

module ntt_butterfly_gs #(
    parameter Q_WIDTH = 12,
    parameter Q       = 3329
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
    reg [Q_WIDTH-1:0] diff_z;
    reg [Q_WIDTH:0] sum_val, diff_val;
    reg [Q_WIDTH-1:0] sum_mod, diff_mod;
    reg valid_d;

    wire valid_rise = valid & ~valid_d;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) valid_d <= 0;
        else valid_d <= valid;
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            stage   <= 0;
            done    <= 0;
            a_out   <= 0;
            b_out   <= 0;
            diff_z  <= 0;
            sum_val <= 0;
            diff_val<= 0;
        end else begin
            case (stage)
                2'd0: begin
                    done <= 1'b0;
                    if (valid_rise) begin
                    // a + b and b - a (mod q) per FIPS 203 Algorithm 10
                    sum_val  <= {1'b0, a} + {1'b0, b};
                    diff_val <= {1'b0, b} + {1'b0, Q} - {1'b0, a};
                        stage <= 2'd1;
                    end
                end
                2'd1: begin
                    sum_mod  <= (sum_val >= Q)  ? sum_val  - Q  : sum_val[Q_WIDTH-1:0];
                    diff_mod <= (diff_val >= Q) ? diff_val - Q : diff_val[Q_WIDTH-1:0];
                    stage <= 2'd2;
                end
                2'd2: begin
                    // tw * (a - b)
                    diff_z <= ({{Q_WIDTH{1'b0}}, tw} * diff_mod) % Q;
                    stage <= 2'd3;
                end
                2'd3: begin
                    a_out <= sum_mod;
                    b_out <= diff_z;
                    done  <= 1'b1;
                    stage <= 2'd0;
                end
            endcase
        end
    end

endmodule
