"""Release/tapout framework (Phase K).

Assesses a build's release level from its stage manifests and either emits a
tapout package (TAPEOUT only, when every gate is genuinely PASSED) or writes a
refusal notice (every other level). The framework can refuse, but it never
claims.
"""

from .bundle import (
    BUNDLE_DIR,
    BUNDLE_SCHEMA_VERSION,
    TapeoutRefused,
    build_tapeout_bundle,
)
from .generator import (
    GATE_BLOCKED,
    GATE_FAILED,
    GATE_NOT_RUN,
    GATE_PASS,
    ReleaseError,
    assess_gate,
    assess_release,
)
from .model import (
    RELEASE_PACKAGE_NAME,
    RELEASE_SCHEMA_VERSION,
    GateStatus,
    ReleaseLevel,
    ReleaseManifest,
)

__all__ = [
    "BUNDLE_DIR",
    "BUNDLE_SCHEMA_VERSION",
    "GATE_BLOCKED",
    "GATE_FAILED",
    "GATE_NOT_RUN",
    "GATE_PASS",
    "RELEASE_PACKAGE_NAME",
    "RELEASE_SCHEMA_VERSION",
    "GateStatus",
    "ReleaseError",
    "ReleaseLevel",
    "ReleaseManifest",
    "TapeoutRefused",
    "assess_gate",
    "assess_release",
    "build_tapeout_bundle",
]