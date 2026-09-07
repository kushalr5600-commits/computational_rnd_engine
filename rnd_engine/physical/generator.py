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

    Each script follows the proven Sky130A counter8 smoke-test pattern.
    Scripts are generated here, executed only by a real toolchain install.
    """
    fp = config.floorplan
    cts = config.cts
    layers = " ".join(config.routing_layers)

    return {
        "floorplan": (
            f"# Floorplan stage for {config.design_id}\n"
            f"set pdk /usr/local/share/pdk/sky130A\n"
            f"read_lef $pdk/libs.ref/sky130_fd_sc_hd/techlef/sky130_fd_sc_hd__nom.tlef\n"
            f"read_lef $pdk/libs.ref/sky130_fd_sc_hd/lef/sky130_fd_sc_hd.lef\n"
            f"read_liberty $pdk/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib\n"
            f"read_verilog {config.design_id}.v\n"
            f"link_design {config.design_id}\n"
            f"read_sdc {config.design_id}.sdc\n"
            f"initialize_floorplan -site unithd "
            f"-die_area {{0 0 99.96 100.128}} "
            f"-core_area {{9.996 10.08 89.964 90.048}}\n"
            f"source $pdk/libs.tech/openroad/sky130_fd_sc_hd/tracks.info\n"
            f"remove_buffers\n"
            f"place_pins -random -hor_layers met3 -ver_layers met2\n"
            f"tapcell -distance {fp.tap_distance if hasattr(fp, 'tap_distance') else 14} "
            f"-tapcell_master sky130_fd_sc_hd__tapvpwrvgnd_1\n"
            f"pdngen -verbose $pdk/libs.tech/openroad/sky130_fd_sc_hd/pdn.cfg\n"
        ),
        "placement": (
            f"# Placement stage for {config.design_id}\n"
            f"set_global_routing_layer_adjustment met1 0.5\n"
            f"set_global_routing_layer_adjustment met2 0.5\n"
            f"set_global_routing_layer_adjustment met3 0.5\n"
            f"set_global_routing_layer_adjustment met4 0.5\n"
            f"set_global_routing_layer_adjustment met5 0.5\n"
            f"set_routing_layers -signal {{{layers}}} -clock {{met3-met5}}\n"
            f"set_macro_extension 2\n"
            f"global_placement -routability_driven -density 0.3 -pad_left 4 -pad_right 4\n"
            f"place_pins -hor_layers met3 -ver_layers met2\n"
            f"estimate_parasitics -placement\n"
            f"repair_design\n"
            f"repair_tie_fanout -separation 5 sky130_fd_sc_hd__conb_1/LO\n"
            f"repair_tie_fanout -separation 5 sky130_fd_sc_hd__conb_1/HI\n"
            f"set_placement_padding -global -left 2 -right 2\n"
            f"detailed_placement\n"
            f"report_worst_slack -min -digits 3\n"
            f"report_worst_slack -max -digits 3\n"
            f"report_tns -digits 3\n"
            f"check_placement -verbose\n"
        ),
        "cts": (
            f"# CTS stage for {config.design_id}\n"
            f"# clock {cts.clock_port}: period {cts.period_ns} ns, "
            f"max skew {cts.max_skew_ns} ns\n"
            f"repair_clock_inverters\n"
            f"clock_tree_synthesis -root_buf sky130_fd_sc_hd__clkbuf_1 "
            f"-buf_list sky130_fd_sc_hd__clkbuf_1 -sink_clustering_enable\n"
            f"repair_clock_nets\n"
            f"estimate_parasitics -placement\n"
            f"set_propagated_clock [all_clocks]\n"
            f"repair_timing\n"
            f"detailed_placement\n"
            f"filler_placement sky130_fd_sc_hd__fill_*\n"
            f"check_placement -verbose\n"
        ),
        "routing": (
            f"# Routing stage for {config.design_id}\n"
            f"# Metal stack: {layers}\n"
            f"global_route -congestion_iterations 100\n"
            f"check_antennas -report_violating_nets "
            f"-report_file {config.design_id}.ant.log\n"
            f"write_verilog -remove_cells sky130_fd_sc_hd__fill_* "
            f"{config.design_id}.routed.v\n"
            f"set_thread_count 2\n"
            f"detailed_route -verbose 0\n"
            f"detailed_route_num_drvs\n"
            f"define_process_corner -ext_model_index 0 X\n"
            f"extract_parasitics -ext_model_file "
            f"$pdk/libs.tech/openroad/sky130_fd_sc_hd/sky130hd.rcx_rules\n"
            f"write_spef {config.design_id}.spef\n"
            f"read_spef {config.design_id}.spef\n"
            f"write_def {config.design_id}_route.def\n"
        ),
        "sta": (
            f"# Multi-corner STA for {config.design_id}\n"
            f"set pdk /usr/local/share/pdk/sky130A\n"
            f"read_verilog {config.design_id}.routed.v\n"
            f"link_design {config.design_id}\n"
            f"read_sdc {config.design_id}.sdc\n"
            f"read_spef {config.design_id}.spef\n"
            f"set_propagated_clock [all_clocks]\n"
            f"# TT corner\n"
            f"read_liberty $pdk/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib\n"
            f"report_checks -path_delay min_max -digits 3\n"
            f"report_worst_slack -min -digits 3\n"
            f"report_worst_slack -max -digits 3\n"
            f"report_tns -digits 3\n"
            f"report_check_types -max_slew -max_capacitance -max_fanout -violators -digits 3\n"
            f"report_clock_skew -digits 3\n"
            f"# FF corner\n"
            f"read_liberty $pdk/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__ff_017C_1v95.lib\n"
            f"report_worst_slack -min -digits 3\n"
            f"report_worst_slack -max -digits 3\n"
            f"report_tns -digits 3\n"
            f"# SS corner\n"
            f"read_liberty $pdk/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__ss_017C_0v72.lib\n"
            f"report_worst_slack -min -digits 3\n"
            f"report_worst_slack -max -digits 3\n"
            f"report_tns -digits 3\n"
        ),
        "power": (
            f"# Power analysis for {config.design_id}\n"
            f"set pdk /usr/local/share/pdk/sky130A\n"
            f"read_lef $pdk/libs.ref/sky130_fd_sc_hd/techlef/sky130_fd_sc_hd__nom.tlef\n"
            f"read_lef $pdk/libs.ref/sky130_fd_sc_hd/lef/sky130_fd_sc_hd.lef\n"
            f"read_liberty $pdk/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib\n"
            f"read_verilog {config.design_id}.routed.v\n"
            f"link_design {config.design_id}\n"
            f"read_sdc {config.design_id}.sdc\n"
            f"read_spef {config.design_id}.spef\n"
            f"set_propagated_clock [all_clocks]\n"
            f"set_power_activity -global 0.1\n"
            f"report_power\n"
            f"report_power -corner ff\n"
            f"report_power -corner ss\n"
            f"report_design_area\n"
        ),
        "drc": (
            f"# DRC for {config.design_id} via magic\n"
            f"set pdk /usr/local/share/pdk/sky130A\n"
            f"gds read $pdk/libs.ref/sky130_fd_sc_hd/gds/sky130_fd_sc_hd.gds\n"
            f"load {config.design_id}\n"
            f"source $pdk/libs.tech/magic/sky130A.tcl\n"
            f"drc check\n"
            f"drc listall why\n"
            f"feedback save {config.design_id}_drc.log\n"
        ),
        "lvs": (
            f"# LVS for {config.design_id} via netgen\n"
            f"set pdk /usr/local/share/pdk/sky130A\n"
            f"gds read $pdk/libs.ref/sky130_fd_sc_hd/gds/sky130_fd_sc_hd.gds\n"
            f"load {config.design_id}\n"
            f"source $pdk/libs.tech/magic/sky130A.tcl\n"
            f"extract all\n"
            f"ext2spice lvs\n"
            f"feedback save {config.design_id}_lvs_extract.log\n"
            f"lvs {{{config.design_id}.spice {config.design_id}}} "
            f"{{{config.design_id}_netlist.v {config.design_id}}} "
            f"$pdk/libs.tech/netgen/setup.tcl {config.design_id}_lvs.rpt\n"
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