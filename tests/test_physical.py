"""Phase H tests: physical design + DRC/LVS abstraction (toolless scope)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rnd_engine.microarchitecture import derive_microarchitecture
from rnd_engine.models import Domain
from rnd_engine.physical import (
    PHYSICAL_STAGES,
    CtsParams,
    FloorplanParams,
    PhysicalConfig,
    PhysicalError,
    bind_physical,
    render_stage_scripts,
)
from rnd_engine.rtl import generate_rtl
from rnd_engine.search import SearchEngine
from rnd_engine.specification import build_specification
from rnd_engine.synthesis import synthesize
from rnd_engine.technology import SKY130, bind_technology


def _micro(seed: int = 42, domain: Domain = Domain.HETEROGENEOUS):
    design = SearchEngine(seed).seed(1, domain)[0]
    return derive_microarchitecture(build_specification(design))


def _open_pdk_micro(seed: int = 42):
    micro = _micro(seed)
    for dom in micro.clock_reset.domains:
        dom.technology_nm = SKY130.node_nm
        dom.voltage_v = 1.8
    return micro


@pytest.fixture(scope="module")
def bound(tmp_path_factory):
    micro = _open_pdk_micro()
    out = tmp_path_factory.mktemp("physical")
    rtl = generate_rtl(micro, out)
    syn = synthesize(micro, rtl, out)
    tech = bind_technology(micro, rtl, syn, out)
    return bind_physical(micro, rtl, syn, tech, out), out, micro, rtl, syn, tech


# --- configuration ----------------------------------------------------------

def test_physical_config_is_deterministic(bound):
    manifest, out, micro, rtl, syn, tech = bound
    assert manifest.config is not None
    # Re-binding from the same inputs must produce a byte-identical manifest.
    again = bind_physical(micro, rtl, syn, tech, out)
    assert again.model_dump_json() == manifest.model_dump_json()


def test_config_derives_floorplan_and_cts(bound):
    manifest, _, micro, _, _, tech = bound
    cfg = manifest.config
    assert cfg.pdk_name == "sky130A"
    assert cfg.clock_period_ns == tech.config.clock_period_ns
    assert 0 < cfg.floorplan.utilization_pct < 100
    assert cfg.floorplan.aspect_ratio == 1.0
    assert cfg.cts.clock_port == "clk"
    assert cfg.cts.period_ns == cfg.clock_period_ns
    assert cfg.cts.max_skew_ns < cfg.clock_period_ns
    assert cfg.routing_layers == SKY130.metal_stack
    assert manifest.provenance["seed"] == micro.provenance["seed"]


# --- gate honesty -----------------------------------------------------------

def test_all_stages_blocked_without_toolchain(bound):
    manifest, *_ = bound
    assert {s.stage for s in manifest.stages} == set(PHYSICAL_STAGES)
    assert all(s.status == "BLOCKED" for s in manifest.stages)
    assert all(s.metrics == {} for s in manifest.stages)  # no fabricated metrics
    assert all("not installed" in s.reason for s in manifest.stages)
    assert manifest.status == "BLOCKED"
    assert manifest.tool_path is None


def test_foundry_design_yields_blocked_config_less_manifest(tmp_path):
    micro = _micro(seed=7)  # foundry node, no open profile
    rtl = generate_rtl(micro, tmp_path)
    syn = synthesize(micro, rtl, tmp_path)
    tech = bind_technology(micro, rtl, syn, tmp_path)
    manifest = bind_physical(micro, rtl, syn, tech, tmp_path)
    assert manifest.status == "BLOCKED"
    assert manifest.config is None
    assert all(s.status == "BLOCKED" for s in manifest.stages)


def test_pdk_installed_yields_not_run_not_passed(bound, monkeypatch, tmp_path):
    """Even with the PDK detected, stages stay NOT_RUN — never PASS."""
    _, out, micro, rtl, syn, _ = bound
    fake_root = tmp_path / "pdk"
    (fake_root / SKY130.name).mkdir(parents=True)
    monkeypatch.setenv("PDK_ROOT", str(fake_root))
    tech2 = bind_technology(micro, rtl, syn, out)
    # Bind into a private tree so the shared fixture artifacts stay untouched.
    manifest2 = bind_physical(micro, rtl, syn, tech2, tmp_path / "own")
    assert tech2.pdk_installed is True
    assert all(s.status == "NOT_RUN" for s in manifest2.stages)
    assert manifest2.status == "NOT_RUN"

# --- artifacts --------------------------------------------------------------

def test_stage_scripts_written_and_labeled(bound):
    _, out, micro, *_ = bound
    stages_dir = Path(out) / "flows" / "physical" / micro.design_id / "stages"
    for stage in PHYSICAL_STAGES:
        script = stages_dir / f"{stage}.tcl"
        assert script.exists(), stage
        content = script.read_text(encoding="utf-8")
        # Scripts now contain real Sky130A PDK commands
        assert "sky130" in content.lower() or "pdk" in content.lower()
    assert "initialize_floorplan" in (stages_dir / "floorplan.tcl").read_text("utf-8")
    assert "clock_tree_synthesis" in (stages_dir / "cts.tcl").read_text("utf-8")
    assert "report_worst_slack" in (stages_dir / "sta.tcl").read_text("utf-8")
    assert "drc check" in (stages_dir / "drc.tcl").read_text("utf-8")
    assert "lvs" in (stages_dir / "lvs.tcl").read_text("utf-8")


def test_config_and_report_files_exist(bound):
    manifest, out, micro, *_ = bound
    design = micro.design_id
    assert (Path(out) / "configs" / "physical" / design / "config.json").exists()
    report = json.loads((Path(out) / "reports" / "physical" / design
                         / "manifest.json").read_text(encoding="utf-8"))
    # Shared artifact tree: earlier tests may have re-bound with an installed
    # PDK, so the on-disk report must match a fresh bind, not a fixed status.
    assert report["status"] == manifest.status
    assert len(report["stages"]) == len(PHYSICAL_STAGES)


def test_manifest_chained_to_upstream_hashes(bound):
    manifest, _, _, rtl, syn, tech = bound
    assert manifest.rtl_architecture_hash == rtl.architecture_hash
    assert manifest.synthesis_config_hash == syn.synthesis_config_hash
    assert manifest.design_id == tech.design_id


def test_rejects_foreign_manifest(tmp_path):
    micro = _open_pdk_micro()
    other = _open_pdk_micro(seed=43)
    rtl = generate_rtl(micro, tmp_path)
    syn = synthesize(micro, rtl, tmp_path)
    tech = bind_technology(micro, rtl, syn, tmp_path)
    with pytest.raises(PhysicalError, match="design"):
        bind_physical(other, rtl, syn, tech, tmp_path)


def test_no_physical_results_are_claimed(bound):
    """Honesty boundary: no DRC/LVS/timing/power numbers anywhere."""
    manifest, *_ = bound
    text = json.dumps(manifest.model_dump(mode="json")).lower()
    for forbidden in ("\"wns\":", "\"tns\":", "\"drc_violations", "lvs_clean",
                      "\"area\":", "\"power_w"):
        assert forbidden not in text


def test_render_stage_scripts_covers_every_stage():
    """Pins the full stage set so a future stage cannot be silently dropped."""
    micro = _open_pdk_micro()
    cfg = PhysicalConfig(
        design_id=micro.design_id, pdk_name="sky130A",
        standard_cell_library="sky130_fd_sc_hd", clock_period_ns=10.0,
        floorplan=FloorplanParams(utilization_pct=50, aspect_ratio=1.0,
                                  core_margin_um=5.0, place_site_name="s"),
        cts=CtsParams(clock_port="clk", period_ns=10.0, max_skew_ns=0.5),
        routing_layers=["met1"],
    )
    scripts = render_stage_scripts(cfg)
    assert set(scripts) == set(PHYSICAL_STAGES)