"""Technology/PDK abstraction (Phase G, toolless scope).

Resolves each design to a declared open-PDK profile and emits a deterministic
technology config + OpenROAD flow. The physical-implementation gate is honestly
**BLOCKED** unless the PDK files are actually installed (``PDK_ROOT`` probe) —
a declared profile is metadata, not a toolchain.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..microarchitecture.model import MicroArchitectureSpec
from ..rtl.generator import _build_params
from ..rtl.model import RtlManifest
from ..synthesis.model import SynthesisManifest
from .model import PdkCorner, TechnologyConfig, TechnologyManifest
from .registry import match_profile, pdk_installed

TECHNOLOGY_SCHEMA_VERSION: int = 1


class TechnologyError(RuntimeError):
    """Raised when a design cannot be bound to a technology target."""


def _technology_config(micro: MicroArchitectureSpec) -> TechnologyConfig:
    """Bind the design's node/voltage to a declared open-PDK profile."""
    domain = micro.clock_reset.domains[0] if micro.clock_reset.domains else None
    node_nm = domain.technology_nm if domain else 130
    voltage = domain.voltage_v if domain else 1.8
    profile = match_profile(node_nm, voltage)
    if profile is None:
        raise TechnologyError(
            f"no declared open-PDK profile matches node {node_nm}nm / "
            f"{voltage}V; extend rnd_engine/technology/registry.py")
    library = profile.standard_cell_libraries[0]
    params = _build_params(micro)
    return TechnologyConfig(
        design_id=micro.design_id,
        pdk_name=profile.name,
        node_nm=profile.node_nm,
        voltage_v=voltage,
        standard_cell_library=library,
        corners=[PdkCorner(**c.model_dump()) for c in profile.corners],
        clock_period_ns=round(1000.0 / int(params["CORE_FREQ_MHZ"]), 4)
        if int(params["CORE_FREQ_MHZ"]) > 0 else 10.0,
        open_source=profile.open_source,
        provenance={"seed": micro.provenance.get("seed")},
    )


def render_openroad_flow(config: TechnologyConfig) -> str:
    """Deterministic OpenROAD flow script for a technology config.

    The flow is generated for a real install; it is *never* executed here
    unless the PDK probe passes, and results are only produced by OpenROAD.
    """
    corner = config.corners[0].name if config.corners else "tt"
    return f"""# Generated OpenROAD flow for design {config.design_id} (Phase G).
# PDK: {config.pdk_name} ({config.node_nm}nm)  LIB: {config.standard_cell_library}
# Corner: {corner}   Target period: {config.clock_period_ns} ns
set ::env(DESIGN_NAME) top
set ::env(PDK) {config.pdk_name}
set ::env(STD_CELL_LIBRARY) {config.standard_cell_library}
set ::env(CLOCK_PERIOD) {config.clock_period_ns}
set ::env(SYNTH_TOP_MODULE) top
# Physical implementation stages run only under a real OpenROAD install.
# This script is generated, not executed, by the toolless flow.
"""

def _quote_env(name: str) -> str:
    return f"${{{name}}}"


def bind_technology(
    micro: MicroArchitectureSpec,
    rtl_manifest: RtlManifest,
    synthesis_manifest: SynthesisManifest,
    out_dir: str | Path = "artifacts",
) -> TechnologyManifest:
    """Resolve the technology target and emit config + flow artifacts.

    Always generates the deterministic artifacts. The physical gate is BLOCKED
    unless the matched PDK is actually installed (filesystem probe); the gate
    can never claim PASS without a real toolchain run.
    """
    if not micro.design_id:
        raise TechnologyError("MicroArchitectureSpec has no design_id.")
    if rtl_manifest.design_id != micro.design_id:
        raise TechnologyError(
            f"RTL manifest design {rtl_manifest.design_id} != {micro.design_id}")
    if synthesis_manifest.design_id != micro.design_id:
        raise TechnologyError(
            f"synthesis manifest design {synthesis_manifest.design_id} != "
            f"{micro.design_id}")

    base = Path(out_dir)
    try:
        config = _technology_config(micro)
    except TechnologyError as exc:
        # Foundry-node designs have no declared open profile: the open-PDK
        # path cannot serve them — honest BLOCKED, no artifacts fabricated.
        manifest = TechnologyManifest(
            design_id=micro.design_id,
            rtl_architecture_hash=rtl_manifest.architecture_hash,
            synthesis_config_hash=synthesis_manifest.synthesis_config_hash,
            technology_schema_version=TECHNOLOGY_SCHEMA_VERSION,
            status="BLOCKED",
            pdk_installed=False,
            config=None,
            provenance={
                **(micro.provenance or {}),
                "status_reason": str(exc),
            },
        )
        reports_dir = base / "reports" / "technology" / micro.design_id
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / "manifest.json").write_text(
            json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        return manifest

    flow_text = render_openroad_flow(config)
    base = Path(out_dir)
    cfg_dir = base / "configs" / "technology" / micro.design_id
    flow_dir = base / "flows" / "physical" / micro.design_id
    reports_dir = base / "reports" / "technology" / micro.design_id
    for d in (cfg_dir, flow_dir, reports_dir):
        d.mkdir(parents=True, exist_ok=True)
    cfg_path = cfg_dir / "config.json"
    cfg_path.write_text(
        json.dumps(config.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    (flow_dir / "openroad_flow.tcl").write_text(flow_text, encoding="utf-8")

    profile = match_profile(config.node_nm, config.voltage_v)
    installed = bool(profile and pdk_installed(profile))

    if installed:
        # A real install would hand off to OpenROAD here. The toolless engine
        # does not drive physical implementation, so even with a PDK present
        # the stage stays NOT_RUN until Phase H lands its runner.
        status, reason = "NOT_RUN", (
            "PDK files detected; physical implementation runner arrives in "
            "Phase H — gate is NOT_RUN, not PASS")
    else:
        status, reason = "BLOCKED", (
            f"PDK '{config.pdk_name}' declared but not installed "
            f"(set {_quote_env('PDK_ROOT')} with the PDK tree to unblock)")

    manifest = TechnologyManifest(
        design_id=micro.design_id,
        rtl_architecture_hash=rtl_manifest.architecture_hash,
        synthesis_config_hash=synthesis_manifest.synthesis_config_hash,
        technology_schema_version=TECHNOLOGY_SCHEMA_VERSION,
        status=status,
        pdk_installed=installed,
        config=config,
        provenance={
            **(micro.provenance or {}),
            "config_path": f"configs/technology/{micro.design_id}/config.json",
            "flow_path": f"flows/physical/{micro.design_id}/openroad_flow.tcl",
            "status_reason": reason,
        },
    )
    (reports_dir / "manifest.json").write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    return manifest