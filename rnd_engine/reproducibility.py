from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize any JSON-compatible value with sorted keys for stable digests."""
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def stable_digest(value: Any, length: int = 16) -> str:
    """Deterministic SHA-256 digest (hex, truncated) of a JSON-compatible value.

    Python's built-in ``hash()`` is randomized per process and must never be
    used for persistent identity; this helper is the stable alternative.
    """
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()[:length]


def configuration_fingerprint(
    search_config: dict[str, Any] | None = None,
    objective_config: dict[str, Any] | None = None,
    architecture_schema_version: int | None = None,
) -> str:
    """Stable identifier for the search + objective configuration of a run.

    Two runs reproduce identical designs only when this fingerprint AND the
    architecture schema version match.
    """
    payload: dict[str, Any] = {
        "architecture_schema_version": architecture_schema_version,
        "search_config": search_config or {},
        "objective_config": objective_config or {},
    }
    return stable_digest(payload, length=16)