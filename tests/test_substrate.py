"""Tests for the recursive substrate evolution engine (S/Pi/P)."""
from __future__ import annotations

import pytest

from rnd_engine.fab_ready import (
    KnowledgeItem,
    KnowledgeType,
    SearchPolicy,
    SearchSpaceState,
)
from rnd_engine.knowledge import KnowledgeStore
from rnd_engine.substrate import (
    evolve_policy,
    evolve_search_space,
    promote_primitives,
)


def make_store() -> KnowledgeStore:
    store = KnowledgeStore()
    store.append(KnowledgeItem(
        knowledge_type=KnowledgeType.VERIFIED_FAILURE,
        source_candidate="c_fail",
        generation=0,
        content={"signature": {"param": "stages", "max": 3}, "reason": "timing"},
    ))
    store.append(KnowledgeItem(
        knowledge_type=KnowledgeType.VERIFIED_SOLUTION,
        source_candidate="c_win",
        generation=0,
        content={"region": {"family": "inorder", "stages": [4, 8]}, "omega": 1.5},
    ))
    return store


class TestEvolveSearchSpace:
    def test_bans_regions_from_verified_failures(self) -> None:
        new_space = evolve_search_space(SearchSpaceState(space_id="s0"), make_store(), 1)
        assert {"param": "stages", "max": 3} in new_space.banned_regions

    def test_recommends_regions_from_verified_solutions(self) -> None:
        new_space = evolve_search_space(SearchSpaceState(space_id="s0"), make_store(), 1)
        assert {"family": "inorder", "stages": [4, 8]} in new_space.recommended_regions

    def test_adds_verified_primitives_to_available(self) -> None:
        store = KnowledgeStore()
        store.append(KnowledgeItem(
            knowledge_type=KnowledgeType.VERIFIED_PRIMITIVE,
            source_candidate="prim_a",
            generation=0,
            content={},
        ))
        new_space = evolve_search_space(SearchSpaceState(space_id="s0"), store, 1)
        assert "prim_a" in new_space.available_primitives

    def test_family_skew_from_successful_lineage(self) -> None:
        store = KnowledgeStore()
        store.append(KnowledgeItem(
            knowledge_type=KnowledgeType.SUCCESSFUL_LINEAGE,
            source_candidate="c_lin",
            generation=0,
            content={"family": "inorder"},
        ))
        new_space = evolve_search_space(SearchSpaceState(space_id="s0"), store, 1)
        assert new_space.family_skew.get("inorder") == pytest.approx(0.1)
        assert "inorder" in new_space.active_families

    def test_eda_constraints_tighten_bounds(self) -> None:
        store = KnowledgeStore()
        store.append(KnowledgeItem(
            knowledge_type=KnowledgeType.EDA_CONSTRAINT,
            source_candidate="tool",
            generation=0,
            content={"parameter": "voltage", "min": 0.7, "max": 0.9},
        ))
        new_space = evolve_search_space(SearchSpaceState(space_id="s0"), store, 1)
        assert new_space.parameter_bounds["voltage"] == (0.7, 0.9)

    def test_parentage_tracked(self) -> None:
        parent = SearchSpaceState(space_id="s_parent", generation=0)
        child = evolve_search_space(parent, KnowledgeStore(), 1)
        assert child.parents == ["s_parent"]
        assert child.generation == 1

    def test_deterministic(self) -> None:
        a = evolve_search_space(SearchSpaceState(space_id="s0"), make_store(), 1)
        b = evolve_search_space(SearchSpaceState(space_id="s0"), make_store(), 1)
        assert a.model_dump() == b.model_dump()



class TestEvolvePolicy:
    def test_high_failure_ratio_raises_exploration(self) -> None:
        store = KnowledgeStore()
        for i in range(8):
            store.append(KnowledgeItem(
                knowledge_type=KnowledgeType.VERIFIED_FAILURE,
                source_candidate=f"f{i}", generation=0, content={},
            ))
        store.append(KnowledgeItem(
            knowledge_type=KnowledgeType.VERIFIED_SOLUTION,
            source_candidate="w0", generation=0, content={},
        ))
        new_policy = evolve_policy(SearchPolicy(), store, 1)
        assert new_policy.exploration_rate == pytest.approx(0.4)

    def test_low_failure_ratio_lowers_exploration(self) -> None:
        store = KnowledgeStore()
        for i in range(10):
            store.append(KnowledgeItem(
                knowledge_type=KnowledgeType.VERIFIED_SOLUTION,
                source_candidate=f"w{i}", generation=0, content={},
            ))
        new_policy = evolve_policy(SearchPolicy(), store, 1)
        assert new_policy.exploration_rate == pytest.approx(0.25)

    def test_mutation_weights_learn_from_transformations(self) -> None:
        store = KnowledgeStore()
        store.append(KnowledgeItem(
            knowledge_type=KnowledgeType.VERIFIED_TRANSFORMATION,
            source_candidate="t0", generation=0,
            content={"kind": "widen_ibus"},
        ))
        new_policy = evolve_policy(SearchPolicy(), store, 1)
        assert new_policy.mutation_weights["widen_ibus"] == pytest.approx(0.05)

    def test_family_weights_learn_from_lineages(self) -> None:
        store = KnowledgeStore()
        store.append(KnowledgeItem(
            knowledge_type=KnowledgeType.SUCCESSFUL_LINEAGE,
            source_candidate="l0", generation=0,
            content={"family": "inorder"},
        ))
        new_policy = evolve_policy(SearchPolicy(), store, 1)
        assert new_policy.architecture_family_weights["inorder"] == pytest.approx(0.1)

    def test_primitive_reuse_enabled_by_verified_primitives(self) -> None:
        store = KnowledgeStore()
        store.append(KnowledgeItem(
            knowledge_type=KnowledgeType.VERIFIED_PRIMITIVE,
            source_candidate="p0", generation=0, content={},
        ))
        base = SearchPolicy(primitive_reuse=False)
        new_policy = evolve_policy(base, store, 1)
        assert new_policy.primitive_reuse is True

    def test_parentage_tracked(self) -> None:
        child = evolve_policy(SearchPolicy(policy_id="p_parent"), KnowledgeStore(), 1)
        assert child.parents == ["p_parent"]

    def test_deterministic(self) -> None:
        a = evolve_policy(SearchPolicy(), make_store(), 1)
        b = evolve_policy(SearchPolicy(), make_store(), 1)
        assert a.model_dump() == b.model_dump()


class TestPromotePrimitives:
    def _add_transformations(self, store: KnowledgeStore, n: int) -> None:
        for i in range(n):
            store.append(KnowledgeItem(
                knowledge_type=KnowledgeType.VERIFIED_TRANSFORMATION,
                source_candidate=f"c{i}",
                generation=0,
                content={"definition": {"name": "dual_issue", "op": "widen"}},
            ))

    def test_promotes_at_min_uses(self) -> None:
        store = KnowledgeStore()
        self._add_transformations(store, 3)
        promoted = promote_primitives(store, generation=1)
        assert len(promoted) == 1
        assert promoted[0].name == "dual_issue"
        assert len(promoted[0].verified_evidence) == 3

    def test_skips_below_threshold(self) -> None:
        store = KnowledgeStore()
        self._add_transformations(store, 2)
        assert promote_primitives(store, generation=1) == []

    def test_content_addressed_identity(self) -> None:
        store = KnowledgeStore()
        self._add_transformations(store, 3)
        prim = promote_primitives(store, generation=1)[0]
        assert prim.primitive_id == prim.content_hash
        assert len(prim.primitive_id) == 16

    def test_deterministic(self) -> None:
        s1, s2 = KnowledgeStore(), KnowledgeStore()
        self._add_transformations(s1, 3)
        self._add_transformations(s2, 3)
        a = [p.model_dump() for p in promote_primitives(s1, generation=1)]
        b = [p.model_dump() for p in promote_primitives(s2, generation=1)]
        assert a == b
