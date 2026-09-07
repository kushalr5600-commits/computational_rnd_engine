"""Physical design + DRC/LVS abstraction (Phase H, toolless scope).

Generates the deterministic physical-implementation plan (OpenROAD stage
scripts, STA/DRC/LVS run scripts) for a design bound to an open-PDK profile.
No stage is ever executed here and no physical metric is ever fabricated:
without a real toolchain every stage reports **BLOCKED** with a reason, and
``metrics`` stay empty until a checker produced the numbers.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from ..microarchitecture.model import MicroArchitectureSpec
from ..rtl.model import RtlManifest
from ..synthesis.model import SynthesisManifest
from ..technology.model import TechnologyConfig, TechnologyManifest
from ..technology.registry import match_profile
from .model import (
    PHYSICAL_STAGES,
    CtsParams,
    FloorplanParams,
    PhysicalConfig,
    PhysicalManifest,
    StageStatus,
)

PHYSICAL_SCHEMA_VERSION: int = 1
PHYSICAL_FLOWS_DIR = "flows/physical"


class PhysicalError(RuntimeError):
    """Raised when a physical plan cannot be prepared for a design."""


def _physical_config(
    micro: MicroArchitectureSpec, tech: TechnologyConfig, metal_stack: list[str]
) -> PhysicalConfig:
    """Derive the physical plan parameters from the design + technology."""
    params = micro.datapaths
    entries = max(int(params.register_file_entries), 16)
    # Deterministic, documented heuristics for the plan inputs only.
    utilization = 45.0 if entries >= 256 else 55.0
    return PhysicalConfig(
        design_id=micro.design_id,
        pdk_name=tech.pdk_name,
        standard_cell_library=tech.standard_cell_library,
        clock_period_ns=tech.clock_period_ns,
        floorplan=FloorplanParams(
            utilization_pct=utilization,
            aspect_ratio=1.0,
            core_margin_um=5.0,
            place_site_name=tech.pdk_name.split("A")[0] + "_site",
        ),
        cts=CtsParams(
            clock_port="clk",
            period_ns=tech.clock_period_ns,
            max_skew_ns=round(tech.clock_period_ns * 0.05, 4),
        ),
        routing_layers=list(metal_stack),  # from the PDK profile metal stack
        provenance={"seed": micro.provenance.get("seed")},
    )

def render_stage_scripts(config: PhysicalConfig) -> dict[str, str]:
    """Render the deterministic per-stage OpenROAD/checker scripts.

    Each script is a complete, real tool invocation plan — generated here,
    executed only by a real toolchain install.
    """
    fp = config.floorplan
    cts = config.cts
    core = (
        f"initialize_floorplan -utilization {fp.utilization_pct} "
        f"-aspect_ratio {fp.aspect_ratio} -core_space {fp.core_margin_um} "
        f"-site {fp.place_site_name}"
    )
    layers = " ".join(config.routing_layers)
    return {
        "floorplan": (
            f"# Floorplan stage for {config.design_id} (generated, not executed).\n"
            f"read_db {config.design_id}.odb\n{core}\n"
            "insert_tiecells sky130_fd_sc_hd__tie4_hi\n"
        ),
        "placement": (
            f"# Placement stage for {config.design_id} (generated, not executed).\n"
            "read_db floorplan.odb\nglobal_placement\n"
            "estimate_parasitics -placement\ndetailed_placement\n"
            f"check_placement -verbose\nwrite_db placement.odb\n"
        ),
        "cts": (
            f"# CTS stage for {config.design_id} (generated, not executed).\n"
            f"# clock {cts.clock_port}: period {cts.period_ns} ns, "
            f"max skew {cts.max_skew_ns} ns\n"
            f"clock_tree_synthesis -buf_list sky130_fd_sc_hd__clkbuf_4 "
            f"-root_buf sky130_fd_sc_hd__clkbuf_8 "
            f"-sink_clustering_enable\ndetailed_placement\nwrite_db cts.odb\n"
        ),
        "routing": (
            f"# Routing stage for {config.design_id} (generated, not executed).\n"
            f"read_db cts.odb\nset_routing_layers -signal {{li1 met1-met5}}\n"
            "global_route\nroute_gen\n"
            f"# layers in stack: {layers}\nwrite_db routed.odb\n"
        ),
        "sta": (
            f"# STA stage for {config.design_id} (generated, not executed).\n"
            "# WNS/TNS/slack numbers are produced ONLY by OpenSTA on a real run.\n"
            "read_db routed.odb\nread_sdc\nreport_checks -path_delay max\n"
            "report_checks -path_delay min\nreport_wns\nreport_tns\n"
        ),
        "power": (
            f"# Power stage for {config.design_id} (generated, not executed).\n"
            "# Dynamic/leakage breakdown is produced ONLY by a real power run.\n"
            "read_db routed.odb\nread_sdc\nset_power_activity -global 0.1\n"
            "report_power\n"
        ),
        "drc": (
            f"# DRC stage for {config.design_id} (generated, not executed).\n"
            "# Results come ONLY from magic/KLayout against the real rule deck.\n"
            f"gds read {config.design_id}.gds\n"
            f"load {config.pdk_name}\nrun_magic_drc\ncount_drc\n"
        ),
        "lvs": (
            f"# LVS stage for {config.design_id} (generated, not executed).\n"
            "# Results come ONLY from netgen/KLayout against the real setup.\n"
            f"lvs {{ {config.design_id}.spice {config.design_id} }} "
            f"{{ {config.design_id}_lay.spice {config.design_id} }} "
            f"{config.pdk_name}/lvs setup.tcl report.log\n"
        ),
    }


def _blocked_stages(reason: str) -> list[StageStatus]:
    return [StageStatus(stage=s, status="BLOCKED", reason=reason) for s in PHYSICAL_STAGES]

def bind_physical(
    micro: MicroArchitectureSpec,
    rtl_manifest: RtlManifest,
    synthesis_manifest: SynthesisManifest,
    technology_manifest: TechnologyManifest,
    out_dir: str | Path = "artifacts",
) -> PhysicalManifest:
    """Emit the physical-design plan and honest per-stage gate statuses.

    The plan (config + stage scripts) is always generated deterministically.
    Every stage gate is BLOCKED unless the technology manifest binds an
    installed PDK — and even then the stage is NOT_RUN until a real OpenROAD
    / magic / netgen run (Phase I signoff consumes those results). No physical
    metric is ever written by this toolless flow.
    """
    if not micro.design_id:
        raise PhysicalError("MicroArchitectureSpec has no design_id.")
    for name, manifest in (
        ("RTL", rtl_manifest),
        ("synthesis", synthesis_manifest),
        ("technology", technology_manifest),
    ):
        if manifest.design_id != micro.design_id:
            raise PhysicalError(f"{name} manifest design {manifest.design_id} != {micro.design_id}")

    base = Path(out_dir)
    reports_dir = base / "reports" / "physical" / micro.design_id
    stages_dir = base / PHYSICAL_FLOWS_DIR / micro.design_id / "stages"
    reports_dir.mkdir(parents=True, exist_ok=True)
    stages_dir.mkdir(parents=True, exist_ok=True)

    tech_cfg = technology_manifest.config
    if tech_cfg is None:
        reason = "technology binding BLOCKED: no open-PDK profile for this design node"
        stages = _blocked_stages(reason)
        config = None
    else:
        profile = match_profile(tech_cfg.node_nm, tech_cfg.voltage_v)
        if profile is None or not technology_manifest.pdk_installed:
            reason = (
                f"PDK '{tech_cfg.pdk_name}' declared but not installed; "
                "physical stages cannot run"
            )
            stages = _blocked_stages(reason)
            config = _physical_config(micro, tech_cfg, profile.metal_stack if profile else [])
        else:
            reason = (
                "PDK files detected; OpenROAD/magic/netgen runner arrives with a "
                "real toolchain install — stages are NOT_RUN, not PASS"
            )
            stages = [
                StageStatus(stage=s, status="NOT_RUN", reason=reason)
                for s in PHYSICAL_STAGES
            ]
            config = _physical_config(micro, tech_cfg, profile.metal_stack)

    if config is not None:
        cfg_path = base / "configs" / "physical" / micro.design_id / "config.json"
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        cfg_path.write_text(
            json.dumps(config.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
        for stage, script in render_stage_scripts(config).items():
            (stages_dir / f"{stage}.tcl").write_text(script, encoding="utf-8")

    openroad_path = shutil.which("openroad")
    manifest = PhysicalManifest(
        design_id=micro.design_id,
        rtl_architecture_hash=rtl_manifest.architecture_hash,
        synthesis_config_hash=synthesis_manifest.synthesis_config_hash,
        physical_schema_version=PHYSICAL_SCHEMA_VERSION,
        status="BLOCKED" if any(s.status == "BLOCKED" for s in stages)
        else ("NOT_RUN" if any(s.status == "NOT_RUN" for s in stages) else "PASSED"),
        tool_path=openroad_path,
        config=config,
        stages=stages,
        provenance={
            **(micro.provenance or {}),
            "config_path": f"configs/physical/{micro.design_id}/config.json",
            "stage_scripts": f"{PHYSICAL_FLOWS_DIR}/{micro.design_id}/stages/",
            "status_reason": reason,
        },
    )
    (reports_dir / "manifest.json").write_text(
        json.dumps(manifest.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8")
    return manifest