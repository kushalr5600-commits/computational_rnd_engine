// QuantumVault Gate 9C — Modular coefficient multiply
// Combinational (a * b) mod q for ML-KEM q=3329
// Barrett reduction, single-cycle

module mod_q_mul #(
    parameter Q_WIDTH = 12,
    parameter Q       = 3329
)(
    input  wire [Q_WIDTH-1:0]   a,
    input  wire [Q_WIDTH-1:0]   b,
    output wire [Q_WIDTH-1:0]   result
);

    wire [2*Q_WIDTH-1:0] full_product = a * b;

    // Barrett reduction for Q=3329, Q_WIDTH=12
    // MU must be wide enough: t can be up to 24 bits, MU up to 13 bits
    // t * MU needs 24+13=37 bits to avoid overflow
    localparam [31:0] MU = 32'd5038;  // floor(2^24 / 3329)

    wire [31:0] full_ext = {8'd0, full_product};  // extend to 32 bits
    wire [31:0] t32     = full_ext >> (Q_WIDTH - 1);  // floor(x / 2^11)
    wire [31:0] q_hat32 = (t32 * MU) >> (Q_WIDTH + 1); // floor(t * mu / 2^13)
    wire [31:0] r1_32   = full_ext - q_hat32 * Q;
    wire        ge_q1   = (r1_32 >= Q);
    wire [31:0] r2_32   = ge_q1 ? r1_32 - Q : r1_32;
    wire        ge_q2   = (r2_32 >= Q);
    wire [31:0] r3_32   = ge_q2 ? r2_32 - Q : r2_32;

    assign result = r3_32[Q_WIDTH-1:0];

endmodule
