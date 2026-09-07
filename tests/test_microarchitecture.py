from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from rnd_engine.microarchitecture import (
    derive_microarchitecture,
    microarchitecture_hash,
    write_microarchitecture_files,
    write_microarchitecture_markdown,
)
from rnd_engine.models import Domain
from rnd_engine.search import SearchEngine
from rnd_engine.specification import build_specification, specification_hash

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def spec():
    design = SearchEngine(42).seed(1, Domain.HETEROGENEOUS)[0]
    return build_specification(design)


@pytest.fixture(scope="module")
def micro(spec):
    return derive_microarchitecture(spec)


def test_derivation_is_deterministic(spec):
    design_b = SearchEngine(42).seed(1, Domain.HETEROGENEOUS)[0]
    spec_b = build_specification(design_b)
    micro_a = derive_microarchitecture(spec)
    micro_b = derive_microarchitecture(spec_b)
    assert micro_a.model_dump_json() == micro_b.model_dump_json()
    assert microarchitecture_hash(micro_a) == microarchitecture_hash(micro_b)


def test_microarchitecture_links_to_spec_and_design(spec, micro):
    assert micro.design_id == spec.design_id
    assert micro.specification_hash == specification_hash(spec)
    assert micro.architecture_schema_version == spec.architecture_schema_version
    assert micro.provenance == spec.provenance


def test_pipeline_structure(spec, micro):
    names = [s.name for s in micro.pipeline.stages]
    assert names[0] == "fetch"
    assert names[-1] == "retire"
    assert "decode" in names and "issue" in names and "execute" in names
    # classic in-order floor: 6 stages absent a vector stage
    isa = spec.sections[1].parameters[0].value
    vec = spec.sections[1].parameters[1].value
    expected = 6 + (1 if vec > isa else 0)
    assert len(micro.pipeline.stages) == expected


def test_every_element_traceable(spec, micro):
    for stage in micro.pipeline.stages:
        assert stage.derived_from
        assert stage.rule
    for dpath in micro.datapaths.datapaths:
        assert dpath.derived_from
        assert dpath.rule
    for cache in micro.memories.caches:
        assert cache.derived_from
        assert cache.rule
    for ctrl in micro.control.mechanisms:
        assert ctrl.derived_from
        assert ctrl.rule


def test_cache_math(micro):
    for cache in micro.memories.caches:
        if cache.capacity_kb > 0:
            assert cache.ways and cache.sets and cache.ways >= 1 and cache.sets >= 1
    l1 = next(c for c in micro.memories.caches if c.name == "l1")
    assert l1.capacity_kb > 0


def test_l3_only_when_present(spec):
    l3 = next(
        (p for section in spec.sections for p in section.parameters if p.path == "structure.l3_kb"),
        None,
    )
    micro = derive_microarchitecture(spec)
    names = {c.name for c in micro.memories.caches}
    if l3 and l3.value > 0:
        assert "l3" in names
    else:
        assert "l3" not in names


def test_clocks_respect_spec(spec, micro):
    clock_param = next(
        p for section in spec.sections for p in section.parameters if p.path == "synthesized.clock_ghz"
    )
    freq_scale_param = next(
        p for section in spec.sections for p in section.parameters if p.path == "hardware.frequency_scaling"
    )
    core = next(d for d in micro.clock_reset.domains if d.name == "core")
    expected = clock_param.value * freq_scale_param.value
    assert core.frequency_ghz == pytest.approx(round(expected, 3), abs=1e-3)


def test_write_files(tmp_path, micro):
    files = write_microarchitecture_files(micro, tmp_path)
    assert "index" in files
    for name in ("pipeline", "datapaths", "memories", "interfaces", "control", "clock_reset"):
        assert (tmp_path / "microarchitecture" / f"{name}.json").exists()


def test_write_markdown(tmp_path, micro):
    out = tmp_path / "micro.md"
    write_microarchitecture_markdown(micro, out)
    text = out.read_text(encoding="utf-8")
    assert "# Microarchitecture Specification" in text
    assert micro.design_id in text
    assert "## Pipeline" in text
    assert "## Control" in text


def test_unlabeled_spec_rejected():
    design = SearchEngine(7).random_design(Domain.CPU, 0)
    design.id = ""
    from rnd_engine.specification import SpecificationError

    with pytest.raises(SpecificationError):
        spec = build_specification(design)
        derive_microarchitecture(spec)


def test_cross_process_microarchitecture_hash_stable():
    script = (
        "from rnd_engine.models import Domain\n"
        "from rnd_engine.search import SearchEngine\n"
        "from rnd_engine.specification import build_specification\n"
        "from rnd_engine.microarchitecture import derive_microarchitecture, microarchitecture_hash\n"
        "d = SearchEngine(42).seed(1, Domain.GPU)[0]\n"
        "print(microarchitecture_hash(derive_microarchitecture(build_specification(d))))\n"
    )

    def run() -> str:
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            check=True,
            cwd=REPO_ROOT,
        )
        return result.stdout.strip()

    assert run() == run()