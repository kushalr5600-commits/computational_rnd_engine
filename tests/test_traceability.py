"""Phase F tests: traceability chain (toolless scope)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from rnd_engine.microarchitecture import derive_microarchitecture
from rnd_engine.models import Domain
from rnd_engine.rtl import generate_rtl
from rnd_engine.search import SearchEngine
from rnd_engine.specification import build_specification
from rnd_engine.synthesis import SynthesisManifest, synthesize
from rnd_engine.traceability import (
    TRACEABILITY_SCHEMA_VERSION,
    TraceabilityError,
    build_traceability_manifest,
)
from rnd_engine.verification import generate_verification


def _micro(seed: int = 42, domain: Domain = Domain.HETEROGENEOUS):
    design = SearchEngine(seed).seed(1, domain)[0]
    return derive_microarchitecture(build_specification(design))


@pytest.fixture(scope="module")
def micro():
    return _micro()


@pytest.fixture(scope="module")
def traced(micro, tmp_path_factory):
    out = tmp_path_factory.mktemp("trace")
    rtl = generate_rtl(micro, out)
    ver = generate_verification(micro, rtl, out)
    syn = synthesize(micro, rtl, out)
    return build_traceability_manifest(micro, rtl, ver, syn, out), out


def test_traceability_chain_is_complete(traced, micro):
    manifest, out = traced
    assert manifest.design_id == micro.design_id
    assert {s.stage for s in manifest.stages} == {"rtl", "verification", "synthesis"}
    assert manifest.traceability_schema_version == TRACEABILITY_SCHEMA_VERSION
    assert manifest.specification_hash == micro.specification_hash
    for stage in manifest.stages:
        assert (Path(out) / stage.artifact).exists(), stage.artifact


def test_traceability_hashes_match_on_disk(traced):
    manifest, out = traced
    for stage in manifest.stages:
        data = (Path(out) / stage.artifact).read_bytes()
        assert hashlib.sha256(data).hexdigest() == stage.sha256


def test_traceability_records_stage_statuses(traced):
    manifest, _ = traced
    ver = manifest.stage("verification")
    syn = manifest.stage("synthesis")
    assert ver is not None and ver.status == "PASSED"
    assert syn is not None and syn.status == "BLOCKED"


def test_traceability_rejects_hash_mismatch(micro, tmp_path):
    rtl = generate_rtl(micro, tmp_path)
    ver = generate_verification(micro, rtl, tmp_path)
    syn = synthesize(micro, rtl, tmp_path)
    tampered = SynthesisManifest(
        **{**syn.model_dump(mode="json"), "rtl_architecture_hash": "deadbeef"})
    with pytest.raises(TraceabilityError, match="RTL build hash"):
        build_traceability_manifest(micro, rtl, ver, tampered, tmp_path)


def test_traceability_rejects_design_id_disagreement(micro, tmp_path):
    rtl = generate_rtl(micro, tmp_path)
    ver = generate_verification(micro, rtl, tmp_path)
    syn = synthesize(micro, rtl, tmp_path)
    other = _micro(seed=99)
    with pytest.raises(TraceabilityError, match="design_id"):
        build_traceability_manifest(other, rtl, ver, syn, tmp_path)


def test_full_chain_is_deterministic(micro, tmp_path):
    """Same design -> byte-identical traceability manifest across trees."""
    hashes = []
    for sub in ("a", "b"):
        out = tmp_path / sub
        rtl = generate_rtl(micro, out)
        ver = generate_verification(micro, rtl, out)
        syn = synthesize(micro, rtl, out)
        tm = build_traceability_manifest(micro, rtl, ver, syn, out)
        hashes.append(tm.model_dump_json())
    assert hashes[0] == hashes[1]
    assert json.loads(hashes[0])["architecture_schema_version"] >= 1