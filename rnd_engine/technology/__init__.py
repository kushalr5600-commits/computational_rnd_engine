"""Technology/PDK abstraction (Phase G, toolless scope)."""

from .generator import (
    TECHNOLOGY_SCHEMA_VERSION,
    TechnologyError,
    bind_technology,
    render_openroad_flow,
)
from .model import PdkCorner, PdkProfile, TechnologyConfig, TechnologyManifest
from .registry import (
    GF180MCU,
    SKY130,
    get_profile,
    match_profile,
    pdk_installed,
)

__all__ = [
    "GF180MCU",
    "SKY130",
    "TECHNOLOGY_SCHEMA_VERSION",
    "PdkCorner",
    "PdkProfile",
    "TechnologyConfig",
    "TechnologyError",
    "TechnologyManifest",
    "bind_technology",
    "get_profile",
    "match_profile",
    "pdk_installed",
    "render_openroad_flow",
]
