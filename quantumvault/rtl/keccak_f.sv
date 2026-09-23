// QuantumVault R0 — Keccak-f[1600] permutation (single-cycle-per-round)
// All theta/rho/pi/chi computed in one clock cycle using blocking assignments
// A is updated at end via non-blocking to maintain pipeline safety

module keccak_f #(
    parameter ROUNDS      = 24,
    parameter FULL_UNROLL = 0
)(
    input  wire          clk,
    input  wire          rst_n,
    input  wire          start,
    input  wire [1599:0] state_in,
    output reg  [1599:0] state_out,
    output reg           done
);

    reg [63:0] A  [0:24];
    reg [63:0] RC [0:23];

    reg [4:0] round;
    reg       load_pending;
    integer   i;

    wire [63:0] C0, C1, C2, C3, C4;
    wire [63:0] D0, D1, D2, D3, D4;
    wire [63:0] Ap [0:24];
    wire [63:0] B  [0:24];
    wire [63:0] nA [0:24];

    // Theta: column XOR
    assign C0 = A[0]  ^ A[5]  ^ A[10] ^ A[15] ^ A[20];
    assign C1 = A[1]  ^ A[6]  ^ A[11] ^ A[16] ^ A[21];
    assign C2 = A[2]  ^ A[7]  ^ A[12] ^ A[17] ^ A[22];
    assign C3 = A[3]  ^ A[8]  ^ A[13] ^ A[18] ^ A[23];
    assign C4 = A[4]  ^ A[9]  ^ A[14] ^ A[19] ^ A[24];

    // Theta: D = C ^ rot(C, 1)
    assign D0 = C4 ^ {C1[62:0], C1[63]};
    assign D1 = C0 ^ {C2[62:0], C2[63]};
    assign D2 = C1 ^ {C3[62:0], C3[63]};
    assign D3 = C2 ^ {C4[62:0], C4[63]};
    assign D4 = C3 ^ {C0[62:0], C0[63]};

    // Theta: A' = A ^ D
    assign Ap[0]  = A[0]  ^ D0;  assign Ap[1]  = A[1]  ^ D1;  assign Ap[2]  = A[2]  ^ D2;  assign Ap[3]  = A[3]  ^ D3;  assign Ap[4]  = A[4]  ^ D4;
    assign Ap[5]  = A[5]  ^ D0;  assign Ap[6]  = A[6]  ^ D1;  assign Ap[7]  = A[7]  ^ D2;  assign Ap[8]  = A[8]  ^ D3;  assign Ap[9]  = A[9]  ^ D4;
    assign Ap[10] = A[10] ^ D0;  assign Ap[11] = A[11] ^ D1;  assign Ap[12] = A[12] ^ D2;  assign Ap[13] = A[13] ^ D3;  assign Ap[14] = A[14] ^ D4;
    assign Ap[15] = A[15] ^ D0;  assign Ap[16] = A[16] ^ D1;  assign Ap[17] = A[17] ^ D2;  assign Ap[18] = A[18] ^ D3;  assign Ap[19] = A[19] ^ D4;
    assign Ap[20] = A[20] ^ D0;  assign Ap[21] = A[21] ^ D1;  assign Ap[22] = A[22] ^ D2;  assign Ap[23] = A[23] ^ D3;  assign Ap[24] = A[24] ^ D4;

    // Rho + Pi: B[y + 5*((2x+3y)%5)] = rot(Ap[x + 5*y], RC_ROT[y][x])
    // rotate_left(x, n) = {x[63-n:0], x[63:64-n]}
    assign B[0]  = Ap[0];
    assign B[1]  = {Ap[6][19:0],  Ap[6][63:20]};    // rot 44
    assign B[2]  = {Ap[12][20:0], Ap[12][63:21]};    // rot 43
    assign B[3]  = {Ap[18][42:0], Ap[18][63:43]};    // rot 21
    assign B[4]  = {Ap[24][49:0], Ap[24][63:50]};    // rot 14
    assign B[5]  = {Ap[3][35:0],  Ap[3][63:36]};     // rot 28
    assign B[6]  = {Ap[9][43:0],  Ap[9][63:44]};     // rot 20
    assign B[7]  = {Ap[10][60:0], Ap[10][63:61]};    // rot 3
    assign B[8]  = {Ap[16][18:0], Ap[16][63:19]};    // rot 45
    assign B[9]  = {Ap[22][2:0],  Ap[22][63:3]};     // rot 61
    assign B[10] = {Ap[1][62:0],  Ap[1][63]};        // rot 1
    assign B[11] = {Ap[7][57:0],  Ap[7][63:58]};     // rot 6
    assign B[12] = {Ap[13][38:0], Ap[13][63:39]};    // rot 25
    assign B[13] = {Ap[19][55:0], Ap[19][63:56]};    // rot 8
    assign B[14] = {Ap[20][45:0], Ap[20][63:46]};    // rot 18
    assign B[15] = {Ap[4][36:0],  Ap[4][63:37]};     // rot 27
    assign B[16] = {Ap[5][27:0],  Ap[5][63:28]};     // rot 36
    assign B[17] = {Ap[11][53:0], Ap[11][63:54]};    // rot 10
    assign B[18] = {Ap[17][48:0], Ap[17][63:49]};    // rot 15
    assign B[19] = {Ap[23][7:0],  Ap[23][63:8]};     // rot 56
    assign B[20] = {Ap[2][1:0],   Ap[2][63:2]};      // rot 62
    assign B[21] = {Ap[8][8:0],   Ap[8][63:9]};      // rot 55
    assign B[22] = {Ap[14][24:0], Ap[14][63:25]};    // rot 39
    assign B[23] = {Ap[15][22:0], Ap[15][63:23]};    // rot 41
    assign B[24] = {Ap[21][61:0], Ap[21][63:62]};    // rot 2

    // Chi: nA[5*y+x] = B[5*y+x] ^ (~B[5*y+(x+1)%5] & B[5*y+(x+2)%5])
    // Row y=0
    assign nA[0]  = B[0]  ^ (~B[1]  & B[2]);
    assign nA[1]  = B[1]  ^ (~B[2]  & B[3]);
    assign nA[2]  = B[2]  ^ (~B[3]  & B[4]);
    assign nA[3]  = B[3]  ^ (~B[4]  & B[0]);
    assign nA[4]  = B[4]  ^ (~B[0]  & B[1]);
    // Row y=1
    assign nA[5]  = B[5]  ^ (~B[6]  & B[7]);
    assign nA[6]  = B[6]  ^ (~B[7]  & B[8]);
    assign nA[7]  = B[7]  ^ (~B[8]  & B[9]);
    assign nA[8]  = B[8]  ^ (~B[9]  & B[5]);
    assign nA[9]  = B[9]  ^ (~B[5]  & B[6]);
    // Row y=2
    assign nA[10] = B[10] ^ (~B[11] & B[12]);
    assign nA[11] = B[11] ^ (~B[12] & B[13]);
    assign nA[12] = B[12] ^ (~B[13] & B[14]);
    assign nA[13] = B[13] ^ (~B[14] & B[10]);
    assign nA[14] = B[14] ^ (~B[10] & B[11]);
    // Row y=3
    assign nA[15] = B[15] ^ (~B[16] & B[17]);
    assign nA[16] = B[16] ^ (~B[17] & B[18]);
    assign nA[17] = B[17] ^ (~B[18] & B[19]);
    assign nA[18] = B[18] ^ (~B[19] & B[15]);
    assign nA[19] = B[19] ^ (~B[15] & B[16]);
    // Row y=4
    assign nA[20] = B[20] ^ (~B[21] & B[22]);
    assign nA[21] = B[21] ^ (~B[22] & B[23]);
    assign nA[22] = B[22] ^ (~B[23] & B[24]);
    assign nA[23] = B[23] ^ (~B[24] & B[20]);
    assign nA[24] = B[24] ^ (~B[20] & B[21]);

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            done         <= 0;
            round        <= 0;
            state_out    <= 0;
            load_pending <= 0;
        end else if (start && round == 0 && !load_pending) begin
            for (i = 0; i < 25; i = i + 1)
                A[i] <= state_in[64*(i+1)-1 -: 64];
            load_pending <= 1;
            done <= 0;
        end else if (load_pending && round == 0) begin
            load_pending <= 0;
            round <= 1;
        end else if (round > 0) begin
            // Iota + write A (single cycle)
            A[0] <= nA[0] ^ RC[round - 1];
            A[1]  <= nA[1];  A[2]  <= nA[2];  A[3]  <= nA[3];
            A[4]  <= nA[4];  A[5]  <= nA[5];  A[6]  <= nA[6];
            A[7]  <= nA[7];  A[8]  <= nA[8];  A[9]  <= nA[9];
            A[10] <= nA[10]; A[11] <= nA[11]; A[12] <= nA[12];
            A[13] <= nA[13]; A[14] <= nA[14]; A[15] <= nA[15];
            A[16] <= nA[16]; A[17] <= nA[17]; A[18] <= nA[18];
            A[19] <= nA[19]; A[20] <= nA[20]; A[21] <= nA[21];
            A[22] <= nA[22]; A[23] <= nA[23]; A[24] <= nA[24];

            if (round == ROUNDS) begin
                done <= 1'b1;
                round <= 0;
            end else begin
                round <= round + 1;
            end
        end else if (done) begin
            done <= 0;
            for (i = 0; i < 25; i = i + 1)
                state_out[64*(i+1)-1 -: 64] <= A[i];
        end
    end

    initial begin
        RC[0]  = 64'h0000000000000001; RC[1]  = 64'h0000000000008082;
        RC[2]  = 64'h800000000000808A; RC[3]  = 64'h8000000080008000;
        RC[4]  = 64'h000000000000808B; RC[5]  = 64'h0000000080000001;
        RC[6]  = 64'h8000000080008081; RC[7]  = 64'h8000000000008009;
        RC[8]  = 64'h000000000000008A; RC[9]  = 64'h0000000000000088;
        RC[10] = 64'h0000000080008009; RC[11] = 64'h000000008000000A;
        RC[12] = 64'h000000008000808B; RC[13] = 64'h800000000000008B;
        RC[14] = 64'h8000000000008089; RC[15] = 64'h8000000000008003;
        RC[16] = 64'h8000000000008002; RC[17] = 64'h8000000000000080;
        RC[18] = 64'h000000000000800A; RC[19] = 64'h800000008000000A;
        RC[20] = 64'h8000000080008081; RC[21] = 64'h8000000000008080;
        RC[22] = 64'h0000000080000001; RC[23] = 64'h8000000080008008;
    end

endmodule
