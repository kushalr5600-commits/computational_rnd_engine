"""Declarative open-PDK registry (Phase G).

Profiles are *metadata only*: declaring a profile here does not mean the PDK
files are installed. ``pdk_installed()`` probes the filesystem honestly.
"""

from __future__ import annotations

import os
from pathlib import Path

from .model import PdkCorner, PdkProfile

# Open PDKs with stable public metadata. Node/valueranges follow each PDK's
# published documentation; nothing here is measured or executed.
SKY130 = PdkProfile(
    name="sky130A",
    node_nm=130,
    open_source=True,
    standard_cell_libraries=["sky130_fd_sc_hd", "sky130_fd_sc_hs"],
    metal_stack=["li1", "met1", "met2", "met3", "met4", "met5"],
    voltage_range=(1.65, 5.5),
    corners=[
        PdkCorner(name="tt_1V80_25C", process="typical", voltage_v=1.8, temperature_c=25),
        PdkCorner(name="ss_1V60_-40C", process="slow", voltage_v=1.6, temperature_c=-40),
        PdkCorner(name="ff_1V95_100C", process="fast", voltage_v=1.95, temperature_c=100),
    ],
    notes="Open-source Google/SkyWater 130nm PDK; default open-flow target.",
)

GF180MCU = PdkProfile(
    name="gf180mcuC",
    node_nm=180,
    open_source=True,
    standard_cell_libraries=["gf180mcu_fd_sc_mcu7t5v0"],
    metal_stack=["met1", "met2", "met3", "met4", "met5"],
    voltage_range=(3.0, 5.0),
    corners=[
        PdkCorner(name="tt_3V30_25C", process="typical", voltage_v=3.3, temperature_c=25),
        PdkCorner(name="ss_3V00_-40C", process="slow", voltage_v=3.0, temperature_c=-40),
        PdkCorner(name="ff_3V60_100C", process="fast", voltage_v=3.6, temperature_c=100),
    ],
    notes="Open-source GlobalFoundries 180nm MCU PDK.",
)

OPEN_PROFILES: dict[str, PdkProfile] = {
    SKY130.name: SKY130,
    GF180MCU.name: GF180MCU,
}

# Environment variables a real OpenROAD/SKY130 install typically provides.
_PDK_ROOT_ENV = "PDK_ROOT"
_PDK_ENV = "PDK"


def get_profile(name: str) -> PdkProfile | None:
    return OPEN_PROFILES.get(name)


def pdk_installed(profile: PdkProfile) -> bool:
    """Honest filesystem probe: is this PDK actually present?

    Checks PDK_ROOT/PDK env conventions used by the open toolchain; a profile
    in the registry alone is never enough.
    """
    pdk_root = os.environ.get(_PDK_ROOT_ENV)
    if pdk_root and (Path(pdk_root) / profile.name).is_dir():
        return True
    if os.environ.get(_PDK_ENV) == profile.name and pdk_root:
        return (Path(pdk_root) / profile.name).is_dir()
    return False


def match_profile(node_nm: int, voltage_v: float) -> PdkProfile | None:
    """Pick the open profile whose node matches and voltage fits its range."""
    for profile in OPEN_PROFILES.values():
        if profile.node_nm == node_nm:
            lo, hi = profile.voltage_range
            if lo <= voltage_v <= hi:
                return profile
    return None
