"""Deterministic flow configuration (fixes the empty-``configs/`` policy debt).

Configuration lives in YAML under ``configs/`` (repository root). Nothing flow
relevant (clock, voltage, PDK path, standard-cell library, timing corners,
die/core geometry, utilization, routing, technology, tool executable or tool
options) is hardcoded in the Python flow code — the EDA bootstrap layer reads
it exclusively from here.

Rules enforced by this module:

- default profile: ``configs/default.yaml``
- target profile (sky130 / gf180): ``configs/<profile>.yaml`` overlays defaults
- flow files under ``configs/flows/`` carry the per-stage tool/options
- machine-specific paths may enter ONLY via the documented environment
  variables (``PDK_ROOT``, ``EDA_ROOT``, ``<TOOL>_BIN``) during ``resolve_env``
- once resolved, the merged configuration is deterministic and
  ``configuration_hash`` is a stable digest of it; any env change that alters
  it changes the hash

A config change (or a toolchain/PDK change) must change the experiment
identity — that is the point of ``configuration_hash`` / ``toolchain_hash`` /
``pdk_hash`` (§22).
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

from .errors import ExternalToolError
from .reproducibility import stable_digest

_CONFIG_DIR = Path(__file__).resolve().parent.parent / "configs"

_ENV_REF = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


class ConfigError(ExternalToolError):
    """Invalid/inconsistent flow configuration."""

    def __init__(self, message: str) -> None:
        super().__init__("CONFIG_INVALID", "config", message)


def _config_dir() -> Path:
    """Directory holding the YAML configs (overridable via RND_ENGINE_CONFIG_DIR)."""
    override = os.environ.get("RND_ENGINE_CONFIG_DIR")
    if override:
        return Path(override)
    return _CONFIG_DIR


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load one YAML config file, validating it is a mapping node."""
    target = Path(path)
    if not target.exists():
        raise ConfigError(f"config file not found: {target}")
    with target.open("r", encoding="utf-8") as fh:
        try:
            data = yaml.safe_load(fh)
        except yaml.YAMLError as exc:
            raise ConfigError(f"invalid YAML in {target}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"config {target} must be a mapping, got {type(data).__name__}")
    return data


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge ``overlay`` onto ``base`` (overlay wins)."""
    out = dict(base)
    for key, value in overlay.items():
        if (
            key in out
            and isinstance(out[key], dict)
            and isinstance(value, dict)
            and key != "env_allowlist"
        ):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _resolve_value(value: Any, env: dict[str, str]) -> Any:
    """Substitute ``${VAR}`` references in strings from a controlled env map."""
    if isinstance(value, str):
        def _sub(m: re.Match[str]) -> str:
            name = m.group(1)
            if name in env:
                return env[name]
            raise ConfigError(
                f"environment variable {name} referenced but not allowed/available"
            )
        return _ENV_REF.sub(_sub, value)
    if isinstance(value, list):
        return [_resolve_value(v, env) for v in value]
    if isinstance(value, dict):
        return {k: _resolve_value(v, env) for k, v in value.items()}
    return value


def resolve_env(
    config: dict[str, Any],
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Resolve ``${VAR}`` references using an *allowlisted* env snapshot.

    Only variables present in ``env`` (or, when ``env`` is None, in the
    actual os.environ) can be substituted. This keeps the resolved config
    deterministic per machine and prevents accidental host-secret capture.
    """
    source = dict(os.environ) if env is None else dict(env)
    allowlist = set(config.get("security", {}).get("env_allowlist", []))
    allowlist.update(
        k for k in source if k.endswith("_BIN") or k in ("PDK_ROOT", "PDK", "EDA_ROOT")
    )
    allowed = {k: v for k, v in source.items() if k in allowlist}
    return _resolve_value(config, allowed)


def load_config(
    profile: str = "default",
    *,
    config_dir: str | Path | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Load + merge + resolve the flow configuration for a PDK profile.

    ``profile='default'`` returns the machine-independent defaults. A target
    profile (``sky130`` / ``gf180``) overlays its YAML on defaults.
    """
    directory = Path(config_dir) if config_dir else _config_dir()
    base = load_yaml(directory / "default.yaml")
    if profile != "default":
        profile_file = directory / f"{profile}.yaml"
        if not profile_file.exists():
            raise ConfigError(f"unknown config profile '{profile}' (no {profile_file})")
        base = _deep_merge(base, load_yaml(profile_file))
    resolved = resolve_env(base, env=env)
    validate_config(resolved)
    return resolved


def load_flow_config(
    flow: str,
    *,
    profile: str = "default",
    config_dir: str | Path | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Load a full resolved configuration with the per-flow overlay applied."""
    directory = Path(config_dir) if config_dir else _config_dir()
    base = load_config(profile=profile, config_dir=directory, env=env)
    flow_file = directory / "flows" / f"{flow}.yaml"
    if not flow_file.exists():
        raise ConfigError(f"unknown flow '{flow}' (no {flow_file})")
    merged = _deep_merge(base, load_yaml(flow_file))
    resolved = resolve_env(merged, env=env)
    validate_config(resolved)
    return resolved


def validate_config(config: dict[str, Any]) -> None:
    """Structural validation of a resolved configuration (raises ConfigError)."""
    for section in ("tools", "security", "flows", "pdk", "fidelity"):
        if section not in config:
            raise ConfigError(f"config missing required section '{section}'")
    if not isinstance(config["tools"], dict) or not config["tools"]:
        raise ConfigError("config 'tools' must be a non-empty mapping")
    if "default_timeout_s" not in config["security"]:
        raise ConfigError("config 'security.default_timeout_s' required")
    if "target" not in config["pdk"]:
        raise ConfigError("config 'pdk.target' required")
    if not isinstance(config["fidelity"].get("promotion", {}), dict):
        raise ConfigError("config 'fidelity.promotion' must be a mapping")


def configuration_hash(config: dict[str, Any]) -> str:
    """Stable content hash of a *resolved* configuration (§22)."""
    payload = {
        "schema_version": config.get("schema_version"),
        "tools": config["tools"],
        "security": {
            k: v for k, v in config["security"].items() if k != "env_allowlist"
        },
        "flows": config["flows"],
        "pdk": config["pdk"],
        "fidelity": config["fidelity"],
    }
    return stable_digest(payload, length=32)


def toolchain_hash(tool_versions: dict[str, str]) -> str:
    """Stable identity of a resolved toolchain: name->version map (§22)."""
    return stable_digest({"toolchain": dict(sorted(tool_versions.items()))}, length=32)


def pdk_hash(pdk_tree: str | Path) -> str:
    """Content hash of an installed PDK tree (sorted relative-path walk).

    Only the *tree* is hashed (metadata, mtimes and absolute path are
    excluded) so the digest is reproducible across machines with byte-identical
    PDK trees. Raises ConfigError if the tree does not exist.
    """
    import hashlib

    root = Path(pdk_tree)
    if not root.is_dir():
        raise ConfigError(f"cannot hash PDK tree: {root} is not a directory")
    digest = hashlib.sha256()
    digest.update(b"pdk-tree-v1\n")
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if any(part.startswith(".git") for part in Path(rel).parts):
            continue
        digest.update(f"{rel}\0".encode())
        with path.open("rb") as fh:
            while chunk := fh.read(65536):
                digest.update(chunk)
        digest.update(b"\0")
    return digest.hexdigest()[:32]