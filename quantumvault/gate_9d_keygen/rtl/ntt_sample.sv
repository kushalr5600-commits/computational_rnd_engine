// QuantumVault Gate 9D — NTT Sample (Parse Algorithm)
// FIPS 203 Algorithm 4: Parse
// Converts XOF (SHAKE-128) output bytes to an NTT-domain polynomial
// Uses rejection sampling: read 3 bytes -> 2 coefficients if < 3329

module ntt_sample #(
    parameter Q_WIDTH = 12,
    parameter Q       = 3329,
    parameter N       = 256,
    parameter LOG2_N  = 8
)(
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  start,
    output reg                   done,

    input  wire [7:0]            xof_data,
    input  wire                  xof_valid,
    output wire                  xof_ready,

    output reg  [Q_WIDTH-1:0]   coeff_out,
    output reg  [LOG2_N-1:0]    coeff_addr,
    output reg                   coeff_we
);

    localparam S_IDLE   = 3'd0;
    localparam S_READ   = 3'd1;
    localparam S_D0     = 3'd2;
    localparam S_D0_W   = 3'd3;
    localparam S_D1     = 3'd4;
    localparam S_D1_W   = 3'd5;
    localparam S_DONE   = 3'd6;

    reg [2:0]  state;
    reg [8:0]  idx;
    reg [1:0]  byte_cnt;
    reg [7:0]  b0, b1, b2;

    wire [11:0] d0_val;
    wire [11:0] d1_val;
    assign d0_val = {4'd0, b0} + {b1[3:0], 8'd0};
    assign d1_val = {8'd0, b1[7:4]} + {b2, 4'd0};

    assign xof_ready = (state == S_READ);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state      <= S_IDLE;
            done       <= 1'b0;
            idx        <= 0;
            byte_cnt   <= 0;
            b0 <= 0; b1 <= 0; b2 <= 0;
            coeff_out  <= 0;
            coeff_addr <= 0;
            coeff_we   <= 1'b0;
        end else begin
            case (state)
                S_IDLE: begin
                    done     <= 1'b0;
                    coeff_we <= 1'b0;
                    if (start) begin
                        idx      <= 0;
                        byte_cnt <= 0;
                        state    <= S_READ;
                    end
                end

                S_READ: begin
                    coeff_we <= 1'b0;
                    if (xof_valid && xof_ready) begin
                        case (byte_cnt)
                            2'd0: b0 <= xof_data;
                            2'd1: b1 <= xof_data;
                            2'd2: b2 <= xof_data;
                        endcase
                        if (byte_cnt == 2'd2) begin
                            byte_cnt <= 0;
                            state    <= S_D0;
                        end else begin
                            byte_cnt <= byte_cnt + 1;
                        end
                    end
                end

                S_D0: begin
                    if (d0_val < Q) begin
                        coeff_out  <= d0_val;
                        coeff_addr <= idx[LOG2_N-1:0];
                        coeff_we   <= 1'b1;
                        state      <= S_D0_W;
                    end else begin
                        state <= S_D1;
                    end
                end

                S_D0_W: begin
                    coeff_we <= 1'b0;
                    if (idx == N - 1) begin
                        state <= S_DONE;
                    end else begin
                        idx   <= idx + 1;
                        state <= S_D1;
                    end
                end

                S_D1: begin
                    if (d1_val < Q) begin
                        coeff_out  <= d1_val;
                        coeff_addr <= idx[LOG2_N-1:0];
                        coeff_we   <= 1'b1;
                        state      <= S_D1_W;
                    end else begin
                        state <= S_READ;
                    end
                end

                S_D1_W: begin
                    coeff_we <= 1'b0;
                    if (idx == N - 1) begin
                        state <= S_DONE;
                    end else begin
                        idx   <= idx + 1;
                        state <= S_READ;
                    end
                end

                S_DONE: begin
                    done  <= 1'b1;
                    state <= S_IDLE;
                end

                default: state <= S_IDLE;
            endcase
        end
    end

endmodule
