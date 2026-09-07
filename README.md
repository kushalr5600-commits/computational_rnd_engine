# Computational R&D Invention Engine

Standalone CPU/GPU invention and design-space exploration engine centered on the Ω objective.

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest
rnd-engine --domain heterogeneous --population 32 --generations 10
```

Results are written to `artifacts/`.

## Important

The built-in evaluator is deterministic surrogate evaluation. It is intentionally honest about that boundary. It provides the search/objective infrastructure but is not a replacement for cycle-accurate simulation, formal verification, RTL, synthesis, FPGA, or silicon measurements.
