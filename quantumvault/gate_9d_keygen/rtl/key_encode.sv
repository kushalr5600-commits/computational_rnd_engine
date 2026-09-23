// QuantumVault Gate 9D — Key Encoding for ML-KEM-768
// FIPS 203 ByteEncode: pack D=12 bit coefficients into bytes (little-endian)

module key_encode #(
    parameter Q_WIDTH = 12,
    parameter Q       = 3329,
    parameter N       = 256,
    parameter K       = 3,
    parameter LOG2_N  = 8,
    parameter D       = 12
)(
    input  wire                  clk,
    input  wire                  rst_n,
    input  wire                  start,
    output reg                   done,

    output wire [LOG2_N+1:0]    coeff_addr,
    input  wire [Q_WIDTH-1:0]   coeff_rdata,
    output reg                   coeff_re,

    output reg  [7:0]           byte_out,
    output reg                   byte_valid,
    input  wire                  byte_ready
);

    localparam S_IDLE = 3'd0;
    localparam S_READ = 3'd1;
    localparam S_PACK = 3'd2;
    localparam S_OUT  = 3'd3;
    localparam S_DONE = 3'd4;

    reg [2:0]  state;
    reg [8:0]  ci;
    reg [1:0]  pi;
    reg [23:0] acc;
    reg [4:0]  bits;
    reg        flushing;

    assign coeff_addr = {pi, ci[LOG2_N-1:0]};
    assign coeff_re = (state == S_READ);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= S_IDLE; done <= 1'b0;
            byte_out <= 0; byte_valid <= 1'b0;
            ci <= 0; pi <= 0; acc <= 0; bits <= 0; flushing <= 0;
        end else begin
            case (state)
                S_IDLE: begin
                    done <= 1'b0; byte_valid <= 1'b0;
                    if (start) begin
                        ci <= 0; pi <= 0;
                        acc <= 0; bits <= 0; flushing <= 0;
                        state <= S_READ;
                    end
                end

                S_READ: begin
                    flushing <= 1'b0;
                    state <= S_PACK;
                end

                S_PACK: begin
                    acc <= acc | ({16'd0, coeff_rdata[D-1:0]} << bits);
                    bits <= bits + D;
                    state <= S_OUT;
                end

                S_OUT: begin
                    if (bits >= 8) begin
                        if (byte_ready) begin
                            byte_out <= acc[7:0];
                            byte_valid <= 1'b1;
                            acc <= acc >> 8;
                            bits <= bits - 8;
                        end
                    end else begin
                        byte_valid <= 1'b0;
                        if (flushing) begin
                            state <= S_DONE;
                        end else begin
                            if (ci == N - 1 && pi == K - 1) begin
                                flushing <= 1'b1;
                                if (bits == 0)
                                    state <= S_DONE;
                            end else begin
                                if (ci == N - 1)
                                    pi <= pi + 1;
                                ci <= (ci == N - 1) ? 0 : ci + 1;
                                state <= S_READ;
                            end
                        end
                    end
                end

                S_DONE: begin
                    byte_valid <= 1'b0;
                    done <= 1'b1;
                    state <= S_IDLE;
                end

                default: state <= S_IDLE;
            endcase
        end
    end

endmodule
