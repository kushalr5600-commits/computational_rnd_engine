from __future__ import annotations

from pathlib import Path

import pytest

from rnd_engine.config import (
    ConfigError,
    configuration_hash,
    load_config,
    pdk_hash,
    toolchain_hash,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_load_default_config_exists():
    config = load_config(profile='default', config_dir=REPO_ROOT / 'configs')
    assert 'tools' in config
    assert 'flows' in config


def test_load_sky130_profile():
    config = load_config(profile='sky130', config_dir=REPO_ROOT / 'configs')
    assert 'tools' in config
    assert 'pdk' in config
    assert config['pdk']['target'] == 'sky130A'


def test_load_gf180_profile():
    config = load_config(profile='gf180', config_dir=REPO_ROOT / 'configs')
    assert config['pdk']['target'] == 'gf180mcuC'


def test_configuration_hash_is_stable():
    config = load_config(profile='sky130', config_dir=REPO_ROOT / 'configs')
    h1 = configuration_hash(config)
    h2 = configuration_hash(config)
    assert h1 == h2
    assert len(h1) == 32


def test_configuration_hash_changes_with_profile():
    c1 = load_config(profile='sky130', config_dir=REPO_ROOT / 'configs')
    c2 = load_config(profile='gf180', config_dir=REPO_ROOT / 'configs')
    assert configuration_hash(c1) != configuration_hash(c2)


def test_toolchain_hash_empty():
    h = toolchain_hash({})
    assert isinstance(h, str)
    assert len(h) == 32


def test_toolchain_hash_stable():
    versions = {'verilator': '5.018', 'yosys': '0.38'}
    assert toolchain_hash(versions) == toolchain_hash(versions)


def test_toolchain_hash_order_independent():
    v1 = {'a': '1.0', 'b': '2.0'}
    v2 = {'b': '2.0', 'a': '1.0'}
    assert toolchain_hash(v1) == toolchain_hash(v2)


def test_pdk_hash_missing_root_raises():
    with pytest.raises(ConfigError):
        pdk_hash('/nonexistent_pdk_path_xyz')


def test_pdk_hash_real_tree(tmp_path):
    (tmp_path / 'lib').mkdir()
    (tmp_path / 'lib' / 'cells.lib').write_text('liberty data')
    h = pdk_hash(tmp_path)
    assert len(h) == 32


def test_config_missing_file_raises():
    with pytest.raises(ConfigError):
        load_config(profile='nonexistent_profile_xyz', config_dir=REPO_ROOT / 'configs')


def test_config_env_override(monkeypatch, tmp_path):
    import yaml
    cfg = {'tools': {'verilator': {'binary': 'verilator'}}, 'flows': {}, 'pdk': {'target': 'x'}, 'security': {'env_allowlist': [], 'default_timeout_s': 60}, 'fidelity': {'promotion': {}}}
    tmp_path.mkdir(exist_ok=True)
    (tmp_path / 'default.yaml').write_text(yaml.safe_dump(cfg))
    monkeypatch.setenv('RND_ENGINE_CONFIG_DIR', str(tmp_path))
    config = load_config(profile='default')
    assert config['tools']['verilator']['binary'] == 'verilator'
