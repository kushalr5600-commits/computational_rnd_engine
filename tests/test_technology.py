"""Phase G tests: technology/PDK abstraction + open-PDK path (toolless scope)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rnd_engine.microarchitecture import derive_microarchitecture
from rnd_engine.models import Domain
from rnd_engine.rtl import generate_rtl
from rnd_engine.search import SearchEngine
from rnd_engine.specification import build_specification
from rnd_engine.synthesis import synthesize
from rnd_engine.technology import (
    GF180MCU,
    SKY130,
    TECHNOLOGY_SCHEMA_VERSION,
    TechnologyError,
    bind_technology,
    match_profile,
    pdk_installed,
)
from rnd_engine.technology.generator import _technology_config


def _micro(seed: int = 42, domain: Domain = Domain.HETEROGENEOUS):
    design = SearchEngine(seed).seed(1, domain)[0]
    return derive_microarchitecture(build_specification(design))


def _open_pdk_micro(seed: int = 42):
    """Retarget a design to the SKY130 node/voltage so the open path matches."""
    micro = _micro(seed)
    for dom in micro.clock_reset.domains:
        dom.technology_nm = SKY130.node_nm
        dom.voltage_v = 1.8
    return micro


@pytest.fixture()
def bound(tmp_path):
    micro = _open_pdk_micro()
    rtl = generate_rtl(micro, tmp_path)
    syn = synthesize(micro, rtl, tmp_path)
    return bind_technology(micro, rtl, syn, tmp_path), tmp_path, micro, rtl, syn


# --- registry ---------------------------------------------------------------

def test_registry_declares_open_pdks_only():
    assert SKY130.node_nm == 130 and SKY130.open_source
    assert GF180MCU.node_nm == 180 and GF180MCU.open_source
    assert match_profile(130, 1.8) is SKY130
    assert match_profile(180, 3.3) is GF180MCU
    assert match_profile(130, 0.8) is None        # below voltage range
    assert match_profile(14, 0.8) is None         # foundry node, no profile


def test_pdk_installed_is_false_without_env(monkeypatch):
    monkeypatch.delenv("PDK_ROOT", raising=False)
    monkeypatch.delenv("PDK", raising=False)
    assert pdk_installed(SKY130) is False


def test_pdk_installed_true_with_fake_tree(tmp_path, monkeypatch):
    (tmp_path / SKY130.name).mkdir()
    monkeypatch.setenv("PDK_ROOT", str(tmp_path))
    assert pdk_installed(SKY130) is True
    assert pdk_installed(GF180MCU) is False


# --- binding ----------------------------------------------------------------

def test_open_pdk_binding_is_deterministic(bound):
    manifest, _, micro, _, _ = bound
    assert manifest.config is not None
    assert manifest.config.model_dump_json() == _technology_config(micro).model_dump_json()


def test_binding_binds_sky130(bound):
    manifest, _, micro, rtl, syn = bound
    cfg = manifest.config
    assert cfg.pdk_name == "sky130A"
    assert cfg.node_nm == 130
    assert cfg.voltage_v == 1.8
    assert cfg.standard_cell_library == "sky130_fd_sc_hd"
    assert cfg.corners and cfg.corners[0].process == "typical"
    assert cfg.open_source is True
    assert manifest.rtl_architecture_hash == rtl.architecture_hash
    assert manifest.synthesis_config_hash == syn.synthesis_config_hash
    assert manifest.technology_schema_version == TECHNOLOGY_SCHEMA_VERSION
    assert manifest.provenance["seed"] == micro.provenance["seed"]


def test_gate_blocked_without_pdk_installed(bound):
    manifest, *_ = bound
    # No PDK_ROOT on this machine: gate must be BLOCKED even though the
    # profile matched, and never PASS without a real toolchain run.
    assert manifest.status == "BLOCKED"
    assert manifest.pdk_installed is False
    assert "not installed" in manifest.provenance["status_reason"]


def test_artifact_layout(bound):
    _, out, micro, *_ = bound
    design = micro.design_id
    cfg = json.loads((Path(out) / "configs" / "technology" / design
                      / "config.json").read_text(encoding="utf-8"))
    assert cfg["pdk_name"] == "sky130A"
    flow = (Path(out) / "flows" / "physical" / design
            / "openroad_flow.tcl").read_text(encoding="utf-8")
    assert "set ::env(PDK) sky130A" in flow
    assert "set ::env(STD_CELL_LIBRARY) sky130_fd_sc_hd" in flow
    assert "set ::env(CLOCK_PERIOD)" in flow
    assert (Path(out) / "reports" / "technology" / design
            / "manifest.json").exists()


def test_flow_is_generated_not_executed(bound):
    """The flow script documents that the toolless engine never runs it."""
    _, out, micro, *_ = bound
    flow = (Path(out) / "flows" / "physical" / micro.design_id
            / "openroad_flow.tcl").read_text(encoding="utf-8")
    assert "generated, not executed" in flow


def test_foundry_node_design_is_blocked(tmp_path):
    """Search-native designs (foundry nodes) get an honest BLOCKED, no crash."""
    micro = _micro(seed=42)  # 14nm — no open profile
    rtl = generate_rtl(micro, tmp_path)
    syn = synthesize(micro, rtl, tmp_path)
    manifest = bind_technology(micro, rtl, syn, tmp_path)
    assert manifest.status == "BLOCKED"
    assert manifest.config is None
    assert "no declared open-PDK profile" in manifest.provenance["status_reason"]


def test_binding_rejects_foreign_manifests(tmp_path):
    micro = _open_pdk_micro()
    other = _open_pdk_micro(seed=43)
    rtl = generate_rtl(micro, tmp_path)
    syn = synthesize(micro, rtl, tmp_path)
    with pytest.raises(TechnologyError, match="design"):
        bind_technology(other, rtl, syn, tmp_path)


def test_no_physical_results_are_claimed(bound):
    """No DRC/LVS/timing numbers anywhere in the manifest — honesty boundary."""
    manifest, *_ = bound
    text = json.dumps(manifest.model_dump(mode="json")).lower()
    for forbidden in ("wns", "tns", "drc_clean", "lvs_clean", "area_um2"):
        assert forbidden not in text