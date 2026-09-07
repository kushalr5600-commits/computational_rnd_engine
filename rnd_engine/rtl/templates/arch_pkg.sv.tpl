// Generated architecture package for design $DESIGN_ID
// schema: rtl_schema_version=$RTL_SCHEMA_VERSION generator=$GENERATOR_VERSION
package arch_pkg;
  localparam int ISA_WIDTH          = $ISA_WIDTH;
  localparam int VECTOR_WIDTH       = $VECTOR_WIDTH;
  localparam int ISSUE_WIDTH        = $ISSUE_WIDTH;
  localparam int EXECUTION_UNITS    = $EXECUTION_UNITS;
  localparam int REG_COUNT          = $REG_COUNT;
  localparam int LOG_REGS           = $LOG_REGS;
  localparam int SLOTS              = $SLOTS;
  localparam int INSN_WIDTH         = $INSN_WIDTH;
  localparam int PC_WIDTH           = $PC_WIDTH;
  localparam int IF_DEPTH           = $IF_DEPTH;
  localparam int INTERCONNECT_WIDTH = $INTERCONNECT_WIDTH;
  localparam int CACHE_LINE_B       = $CACHE_LINE_B;
  localparam int MEM_CHANNELS       = $MEM_CHANNELS;
  localparam int PARALLEL_LANES     = $PARALLEL_LANES;
  localparam int TENSOR_UNITS       = $TENSOR_UNITS;
  localparam int SPECIALIZED_UNITS  = $SPECIALIZED_UNITS;
  localparam int L1_SETS            = $L1_SETS;
  localparam int L1_WAYS            = $L1_WAYS;
  localparam int L2_SETS            = $L2_SETS;
  localparam int L2_WAYS            = $L2_WAYS;
  localparam int LINE_WORDS         = $LINE_WORDS;
  localparam int SRAM_WORDS         = $SRAM_WORDS;
  localparam int SRAM_ADDR_W        = $SRAM_ADDR_W;
  localparam int CORE_FREQ_MHZ      = $CORE_FREQ_MHZ;
  localparam int MEM_FREQ_MHZ       = $MEM_FREQ_MHZ;

  // Minimal generated ISA for the flow-proving core.
  localparam logic [3:0] OP_NOP  = 4'h0;
  localparam logic [3:0] OP_ADD  = 4'h1;
  localparam logic [3:0] OP_SUB  = 4'h2;
  localparam logic [3:0] OP_AND  = 4'h3;
  localparam logic [3:0] OP_OR   = 4'h4;
  localparam logic [3:0] OP_XOR  = 4'h5;
  localparam logic [3:0] OP_LD   = 4'h6;
  localparam logic [3:0] OP_ST   = 4'h7;
  localparam logic [3:0] OP_HALT = 4'hf;
endpackage