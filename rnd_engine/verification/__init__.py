"""Verification infrastructure (Phase E, toolless scope)."""

from .generator import (
    GENERATOR_VERSION as VERIFICATION_GENERATOR_VERSION,
)
from .generator import (
    VERIFICATION_SCHEMA_VERSION,
    VerificationError,
    generate_verification,
    run_reference_gate,
)
from .model import RefRunResult, RtlTestCase, VerificationManifest
from .reference import (  # noqa: F401 — opcodes are part of the public surface
    OP_ADD,
    OP_AND,
    OP_HALT,
    OP_LD,
    OP_NOP,
    OP_OR,
    OP_ST,
    OP_SUB,
    OP_XOR,
    REFERENCE_OPS,
    ReferenceModel,
    encode_insn,
)

__all__ = [
    "REFERENCE_OPS",
    "VERIFICATION_GENERATOR_VERSION",
    "VERIFICATION_SCHEMA_VERSION",
    "RefRunResult",
    "ReferenceModel",
    "RtlTestCase",
    "VerificationError",
    "VerificationManifest",
    "encode_insn",
    "generate_verification",
    "run_reference_gate",
]
