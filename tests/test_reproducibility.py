from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from rnd_engine.models import Design, Domain, design_id
from rnd_engine.search import SearchEngine

POPULATION = 16
REPO_ROOT = Path(__file__).resolve().parents[1]


def _seed(seed: int, n: int = POPULATION) -> list[Design]:
    return SearchEngine(seed).seed(n, Domain.HETEROGENEOUS)


def test_same_seed_identical_populations():
    first = _seed(42)
    second = _seed(42)
    assert len(first) == len(second) == POPULATION
    for da, db in zip(first, second):
        assert da.id == db.id
        assert da.model_dump_json() == db.model_dump_json()


def test_different_seed_different_populations():
    first = _seed(42)
    second = _seed(43)
    assert [d.id for d in first] != [d.id for d in second]
    assert [d.model_dump_json() for d in first] != [d.model_dump_json() for d in second]
    ids = [d.id for d in first] + [d.id for d in second]
    assert len(set(ids)) == len(ids)


def test_schema_version_and_provenance_deterministic():
    designs = _seed(42)
    for d in designs:
        assert d.architecture_schema_version == 1
        assert d.provenance["seed"] == 42
        assert d.provenance["search_config"]["engine"] == "SearchEngine"
        assert d.provenance["configuration_fingerprint"]
    provenances = {json.dumps(d.provenance, sort_keys=True) for d in designs}
    assert len(provenances) == 1


def test_provenance_participates_in_design_id():
    design = SearchEngine(42).random_design(Domain.HETEROGENEOUS, 0)
    clone = design.model_copy(deep=True)
    clone.provenance = dict(clone.provenance)
    clone.provenance["seed"] = 99
    assert design_id(clone) != design.id


def test_evolution_reproducibility():
    def evolve_with(seed: int) -> list[Design]:
        search = SearchEngine(seed)
        parents = search.seed(8, Domain.HETEROGENEOUS)
        return search.evolve(parents, 1, POPULATION)

    first = evolve_with(42)
    second = evolve_with(42)
    assert len(first) == len(second) == POPULATION
    for child_a, child_b in zip(first, second):
        assert child_a.generation == 1
        assert len(child_a.parent_ids) == 1
        assert child_a.id == child_b.id
        assert child_a.model_dump_json() == child_b.model_dump_json()


def test_cross_process_reproducibility():
    script = (
        "import json\n"
        "from rnd_engine.models import Domain\n"
        "from rnd_engine.search import SearchEngine\n"
        "ids = [d.id for d in SearchEngine(42).seed(16, Domain.HETEROGENEOUS)]\n"
        "print(json.dumps(ids))\n"
    )

    def run() -> list:
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            check=True,
            cwd=REPO_ROOT,
        )
        return json.loads(result.stdout.strip())

    assert run() == run()


def test_design_id_is_content_addressed_and_ignores_own_id():
    search = SearchEngine(42)
    design = search.random_design(Domain.HETEROGENEOUS, 0)
    expected = design_id(design)
    assert design.id == expected

    clone = design.model_copy(deep=True)
    clone.id = "00000000-0000-0000-0000-000000000000"
    assert design_id(clone) == expected

    different = design.model_copy(deep=True)
    different.parent_ids = ["11111111-1111-1111-1111-111111111111"]
    assert design_id(different) != expected