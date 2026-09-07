from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from rnd_engine.models import Domain
from rnd_engine.search import SearchEngine
from rnd_engine.specification import (
    ParameterSpec,
    SpecificationError,
    build_specification,
    specification_hash,
    write_markdown,
    write_specification_files,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def design():
    return SearchEngine(42).random_design(Domain.HETEROGENEOUS, 0)


@pytest.fixture(scope="module")
def spec(design):
    return build_specification(design)


def test_specification_is_deterministic(design):
    spec_a = build_specification(design)
    design_b = SearchEngine(42).random_design(Domain.HETEROGENEOUS, 0)
    spec_b = build_specification(design_b)
    assert spec_a.model_dump_json() == spec_b.model_dump_json()
    assert specification_hash(spec_a) == specification_hash(spec_b)


def test_specification_carries_identity_and_provenance(design, spec):
    assert spec.design_id == design.id
    assert spec.architecture_schema_version == design.architecture_schema_version
    assert spec.provenance["seed"] == 42
    params = {p.name: p for p in spec.sections[0].parameters}
    assert params["design_id"].value == design.id
    assert params["seed"].value == 42
    assert params["configuration_fingerprint"].value


def test_specification_parameter_metadata(spec):
    compute = {s.name: s for s in spec.sections}["compute"]
    isa = next(p for p in compute.parameters if p.path == "representation.isa_width")
    assert isa.field_type == "integer"
    assert isa.unit == "bit"
    assert isa.legal_min == 16
    assert isa.legal_max == 256
    assert isa.source == "design.representation.isa_width"
    assert isa.description


def test_specification_section_structure(spec):
    names = [s.name for s in spec.sections]
    assert names == [
        "architecture",
        "compute",
        "memory",
        "interfaces",
        "clock_reset",
        "control",
        "parameters",
    ]


def test_write_specification_files(tmp_path):
    spec = build_specification(SearchEngine(7).random_design(Domain.CPU, 1))
    files = write_specification_files(spec, tmp_path)
    assert "index" in files
    index_path = tmp_path / "specification" / "index.json"
    assert index_path.exists()
    index = json.loads(index_path.read_text(encoding="utf-8"))
    assert index["design_id"] == spec.design_id
    assert index["specification_hash"] == specification_hash(spec)
    for section in spec.sections:
        fname = index["files"][section.name]["file"]
        assert (tmp_path / "specification" / fname).exists()


def test_write_markdown(tmp_path):
    spec = build_specification(SearchEngine(3).random_design(Domain.GPU, 2))
    out = tmp_path / "arch.md"
    write_markdown(spec, out)
    text = out.read_text(encoding="utf-8")
    assert "# Architecture Specification" in text
    assert spec.design_id in text
    assert "## Compute Resources" in text
    assert "## Provenance" in text


def test_unlabeled_design_rejected():

    design = SearchEngine(42).random_design(Domain.HETEROGENEOUS, 0)
    design.id = ""
    with pytest.raises(SpecificationError):
        build_specification(design)


def test_cross_process_specification_hash_stable():
    script = (
        "from rnd_engine.models import Domain\n"
        "from rnd_engine.search import SearchEngine\n"
        "from rnd_engine.specification import build_specification, specification_hash\n"
        "d = SearchEngine(42).random_design(Domain.GPU, 0)\n"
        "print(specification_hash(build_specification(d)))\n"
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


def test_parameter_spec_model_schema():
    spec = ParameterSpec(
        name="x",
        path="rep.x",
        value=1,
        field_type="integer",
        unit="bit",
        legal_min=0,
        legal_max=1,
        description="desc",
        source="design.rep.x",
    )
    assert spec.model_dump()["legal_min"] == 0