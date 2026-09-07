"""Synthesis abstraction (Phase F, toolless scope)."""

from .generator import (
    SYNTHESIS_SCHEMA_VERSION,
    SynthesisError,
    render_yosys_flow,
    run_yosys,
    synthesize,
)
from .model import SynthesisCellStats, SynthesisConfig, SynthesisManifest

__all__ = [
    "SYNTHESIS_SCHEMA_VERSION",
    "SynthesisCellStats",
    "SynthesisConfig",
    "SynthesisError",
    "SynthesisManifest",
    "render_yosys_flow",
    "run_yosys",
    "synthesize",
]
