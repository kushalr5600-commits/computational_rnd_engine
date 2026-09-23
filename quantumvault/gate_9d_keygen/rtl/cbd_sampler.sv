// QuantumVault Gate 9D — CBD(eta=2) Sampler for ML-KEM-768
// FIPS 203 Algorithm 2: Centered Binomial Distribution

module cbd_sampler #(
    parameter Q_WIDTH = 12,
    parameter Q       = 3329,
    parameter N       = 256,
    parameter ETA     = 2
)(
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  start,
    output reg                   done,

    input  wire [7:0]            prf_data,
    input  wire                  prf_valid,
    output wire                  prf_ready,

    output reg  [Q_WIDTH-1:0]   coeff_out,
    output reg  [7:0]           coeff_addr,
    output reg                   coeff_we
);

    localparam BITS_PER = 2 * ETA;

    localparam ST_IDLE = 0;
    localparam ST_FILL = 1;
    localparam ST_CALC = 2;
    localparam ST_OUT  = 3;

    reg [1:0]  st;
    reg [31:0] sr;
    reg [5:0]  cnt;
    reg [7:0]  idx;

    wire need_data;
    assign need_data = (cnt < BITS_PER) && (st == ST_FILL);
    assign prf_ready = need_data;

    wire byte_accepted;
    assign byte_accepted = prf_ready && prf_valid;

    // Combinational CBD computation
    reg [Q_WIDTH-1:0] cbd_val;
    reg [3:0] cbd_x;
    reg [1:0] cbd_a, cbd_b;

    always @(*) begin
        cbd_x = sr[BITS_PER-1:0];
        cbd_a = cbd_x[0] + cbd_x[1];
        cbd_b = cbd_x[2] + cbd_x[3];
        if (cbd_a >= cbd_b)
            cbd_val = {10'd0, cbd_a} - {10'd0, cbd_b};
        else
            cbd_val = Q[Q_WIDTH-1:0] - {10'd0, cbd_b} + {10'd0, cbd_a};
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            st        <= ST_IDLE;
            done      <= 1'b0;
            sr        <= 0;
            cnt       <= 0;
            idx       <= 0;
            coeff_out <= 0;
            coeff_addr <= 0;
            coeff_we  <= 1'b0;
        end else begin
            case (st)
                ST_IDLE: begin
                    done     <= 1'b0;
                    coeff_we <= 1'b0;
                    if (start) begin
                        sr   <= 0;
                        cnt  <= 0;
                        idx  <= 0;
                        st   <= ST_FILL;
                    end
                end

                ST_FILL: begin
                    if (byte_accepted) begin
                        sr  <= sr | ({24'd0, prf_data} << cnt);
                        cnt <= cnt + 8;
                    end
                    if (cnt >= BITS_PER || (byte_accepted && (cnt + 8) >= BITS_PER))
                        st <= ST_CALC;
                end

                ST_CALC: begin
                    coeff_out  <= cbd_val;
                    coeff_addr <= idx;
                    coeff_we   <= 1'b1;
                    st         <= ST_OUT;
                end

                ST_OUT: begin
                    coeff_we <= 1'b0;
                    sr       <= sr >> BITS_PER;
                    cnt      <= cnt - BITS_PER;
                    if (idx == N - 1) begin
                        done <= 1'b1;
                        st   <= ST_IDLE;
                    end else begin
                        idx <= idx + 1;
                        st  <= ST_FILL;
                    end
                end
            endcase
        end
    end

endmodule
