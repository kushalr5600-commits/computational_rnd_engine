# Production boundary

This repository is a production-oriented *research engine*, but the default evaluator is deterministic/surrogate. It must not be represented as a silicon-proven CPU/GPU design system.

For real hardware R&D, connect tool adapters for:

- CPU architecture simulation (for example gem5)
- GPU/kernel simulation and profiling
- RTL simulation (for example Verilator)
- formal/property checking
- synthesis and physical design (for example OpenROAD or commercial EDA)
- FPGA implementation
- power/timing/area measurement

The invariant is: proposal -> execute -> measure -> verify -> Ω -> archive. Surrogate evidence never becomes physical proof.
