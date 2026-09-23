// Multi-seed ML-KEM-768 KeyGen TB for FIPS 203 NTT candidate (post-Bug#15)
// Compares ek/dk against pre-generated seed_XXX_{ek,dk}.hex goldens.
module mlkem_keygen_fips203_ms_tb #(parameter SEED_IDX = 0);
    reg clk, rst_n, start;
    wire done;
    reg [255:0] d_seed, z_seed;
    wire [7:0] ek_byte, dk_byte;
    wire ek_valid, dk_valid, ek_last, dk_last;
    reg ek_ready, dk_ready;

    mlkem_keygen_fips203 uut (
        .clk(clk), .rst_n(rst_n), .start(start), .done(done),
        .d_seed(d_seed), .z_seed(z_seed),
        .ek_byte(ek_byte), .ek_valid(ek_valid), .ek_ready(ek_ready), .ek_last(ek_last),
        .dk_byte(dk_byte), .dk_valid(dk_valid), .dk_ready(dk_ready), .dk_last(dk_last)
    );

    initial clk = 0;
    always #5 clk = ~clk;

    integer cycle_count, ek_idx, dk_idx;
    reg [7:0] ek_buf [0:1183];
    reg [7:0] dk_buf [0:2399];
    reg [7:0] golden_ek [0:1183];
    reg [7:0] golden_dk [0:2399];
    reg [7:0] d_file [0:31];
    reg [7:0] z_file [0:31];

    integer ek_mm, dk_mm, i, ek_xz, dk_xz, timed_out;

    initial begin
        $readmemh($sformatf("/mnt/c/Users/user/Music/computational_rnd_engine/quantumvault/gate_9d_keygen/tb/multiseed/seed_%03d_d.hex", SEED_IDX), d_file);
        $readmemh($sformatf("/mnt/c/Users/user/Music/computational_rnd_engine/quantumvault/gate_9d_keygen/tb/multiseed/seed_%03d_z.hex", SEED_IDX), z_file);
        $readmemh($sformatf("/mnt/c/Users/user/Music/computational_rnd_engine/quantumvault/gate_9d_keygen/tb/multiseed/seed_%03d_ek.hex", SEED_IDX), golden_ek);
        $readmemh($sformatf("/mnt/c/Users/user/Music/computational_rnd_engine/quantumvault/gate_9d_keygen/tb/multiseed/seed_%03d_dk.hex", SEED_IDX), golden_dk);
        $readmemh("/mnt/c/Users/user/Music/computational_rnd_engine/quantumvault/tb/tw_rom.hex", uut.tw_rom);
        $readmemh("/mnt/c/Users/user/Music/computational_rnd_engine/quantumvault/tb/tw_rom_inv.hex", uut.tw_rom_inv);

        for (i = 0; i < 32; i = i + 1) begin
            d_seed[i*8 +: 8] = d_file[i];
            z_seed[i*8 +: 8] = z_file[i];
        end

        rst_n = 0; start = 0; ek_ready = 0; dk_ready = 0;
        ek_idx = 0; dk_idx = 0; cycle_count = 0;
        #50;
        rst_n = 1;
        #20;

        ek_ready = 1; dk_ready = 1; start = 1;
        #10;
        start = 0;

        timed_out = 0;
        while (!done && cycle_count < 200000) begin
            @(posedge clk);
            cycle_count = cycle_count + 1;
            if (ek_valid && ek_ready && ek_idx < 1184) begin
                ek_buf[ek_idx] = ek_byte;
                ek_idx = ek_idx + 1;
            end
            if (dk_valid && dk_ready && dk_idx < 2400) begin
                dk_buf[dk_idx] = dk_byte;
                dk_idx = dk_idx + 1;
            end
        end
        if (!done) timed_out = 1;

        ek_mm = 0; dk_mm = 0; ek_xz = 0; dk_xz = 0;
        for (i = 0; i < 1184; i = i + 1) begin
            if ((ek_buf[i] ^ ek_buf[i]) === 8'hff) ek_xz = ek_xz + 1;
            else if (ek_buf[i] !== golden_ek[i]) ek_mm = ek_mm + 1;
        end
        for (i = 0; i < 2400; i = i + 1) begin
            if ((dk_buf[i] ^ dk_buf[i]) === 8'hff) dk_xz = dk_xz + 1;
            else if (dk_buf[i] !== golden_dk[i]) dk_mm = dk_mm + 1;
        end

        if (timed_out)
            $display("SEED %0d: TIMEOUT after %0d cycles ek=%0d/1184 dk=%0d/2400", SEED_IDX, cycle_count, ek_mm, dk_mm);
        else if (ek_mm == 0 && dk_mm == 0 && ek_xz == 0 && dk_xz == 0 && ek_idx == 1184 && dk_idx == 2400)
            $display("SEED %0d: PASS (ek=0/1184 dk=0/2400 %0d cycles)", SEED_IDX, cycle_count);
        else
            $display("SEED %0d: FAIL ek=%0d/1184 dk=%0d/2400 ek_xz=%0d dk_xz=%0d ek_n=%0d dk_n=%0d cycles=%0d",
                     SEED_IDX, ek_mm, dk_mm, ek_xz, dk_xz, ek_idx, dk_idx, cycle_count);

        $finish;
    end

    initial begin
        #10000000;
        $display("SEED %0d: GLOBAL_TIMEOUT", SEED_IDX);
        $finish;
    end
endmodule
