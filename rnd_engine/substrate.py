from __future__ import annotations

import hashlib
import json

from .fab_ready import (
    KnowledgeType,
    Primitive,
    SearchPolicy,
    SearchSpaceState,
)
from .knowledge import KnowledgeStore


def evolve_search_space(
    current: SearchSpaceState,
    knowledge: KnowledgeStore,
    generation: int,
) -> SearchSpaceState:
    """S_(t+1) = EvolveSearchSpace(S_t, K_t)

    Adapt parameter bounds, active families, banned/recommended regions
    based on accumulated knowledge.
    """
    new_space = SearchSpaceState(
        space_id=_make_id("space", generation),
        generation=generation,
        parents=[current.space_id],
    )

    # Start from current state
    new_space.parameter_bounds = dict(current.parameter_bounds)
    new_space.active_families = list(current.active_families)
    new_space.banned_regions = list(current.banned_regions)
    new_space.recommended_regions = list(current.recommended_regions)
    new_space.available_primitives = list(current.available_primitives)
    new_space.family_skew = dict(current.family_skew)

    # Learn from verified failures: ban regions
    for failure in knowledge.verified_failures():
        sig = failure.content.get("signature")
        if sig and sig not in new_space.banned_regions:
            new_space.banned_regions.append(sig)

    # Learn from verified successes: recommend regions
    for sol in knowledge.verified_solutions():
        region = sol.content.get("region")
        if region and region not in new_space.recommended_regions:
            new_space.recommended_regions.append(region)

    # Learn from verified primitives
    for prim in knowledge.verified_primitives():
        pid = prim.source_candidate
        if pid not in new_space.available_primitives:
            new_space.available_primitives.append(pid)

    # Adapt family skew from successful lineages
    for lineage_item in knowledge.by_type(KnowledgeType.SUCCESSFUL_LINEAGE):
        family = lineage_item.content.get("family")
        if family:
            new_space.family_skew[family] = new_space.family_skew.get(family, 0.0) + 0.1
            if family not in new_space.active_families:
                new_space.active_families.append(family)

    # Adjust parameter bounds from EDA constraints
    for constraint in knowledge.by_type(KnowledgeType.EDA_CONSTRAINT):
        param = constraint.content.get("parameter")
        lo = constraint.content.get("min")
        hi = constraint.content.get("max")
        if param is not None and lo is not None and hi is not None:
            new_space.parameter_bounds[param] = (lo, hi)

    return new_space


def evolve_policy(
    current: SearchPolicy,
    knowledge: KnowledgeStore,
    generation: int,
) -> SearchPolicy:
    """\u03a0_(t+1) = OptimizeSearchPolicy(\u03a0_t, K_t)

    Adapt exploration rate, mutation weights, promotion budget, and
    architecture-family preferences based on knowledge.
    """
    new_policy = SearchPolicy(
        policy_id=_make_id("policy", generation),
        generation=generation,
        parents=[current.policy_id],
    )

    # Start from current policy
    new_policy.exploration_rate = current.exploration_rate
    new_policy.mutation_weights = dict(current.mutation_weights)
    new_policy.promotion_budget = dict(current.promotion_budget)
    new_policy.architecture_family_weights = dict(current.architecture_family_weights)
    new_policy.diversity_target = current.diversity_target
    new_policy.novelty_pressure = current.novelty_pressure
    new_policy.primitive_reuse = current.primitive_reuse
    new_policy.failure_guided = current.failure_guided

    # If many failures, increase exploration
    n_failures = len(knowledge.verified_failures())
    n_solutions = max(len(knowledge.verified_solutions()), 1)
    failure_ratio = n_failures / (n_failures + n_solutions)
    if failure_ratio > 0.7:
        new_policy.exploration_rate = min(0.8, current.exploration_rate + 0.1)
    elif failure_ratio < 0.2:
        new_policy.exploration_rate = max(0.1, current.exploration_rate - 0.05)

    # Adapt mutation weights from successful transformations
    for tx in knowledge.by_type(KnowledgeType.VERIFIED_TRANSFORMATION):
        kind = tx.content.get("kind")
        if kind:
            new_policy.mutation_weights[kind] = new_policy.mutation_weights.get(kind, 0.0) + 0.05

    # Boost families with successful lineages
    for lineage_item in knowledge.by_type(KnowledgeType.SUCCESSFUL_LINEAGE):
        family = lineage_item.content.get("family")
        if family:
            new_policy.architecture_family_weights[family] = \
                new_policy.architecture_family_weights.get(family, 0.0) + 0.1

    # If primitives verified, enable reuse
    if knowledge.verified_primitives():
        new_policy.primitive_reuse = True

    return new_policy


def promote_primitives(
    knowledge: KnowledgeStore,
    generation: int,
    min_uses: int = 3,
) -> list[Primitive]:
    """P_(t+1) = P_t \u222a NewVerifiedPrimitives

    Promote repeatedly-verified useful structures into reusable primitives.
    """
    promoted: list[Primitive] = []

    # Find transformations verified >= min_uses times
    tx_counts: dict[str, list[str]] = {}
    for tx in knowledge.by_type(KnowledgeType.VERIFIED_TRANSFORMATION):
        key = json.dumps(tx.content.get("definition", {}), sort_keys=True)
        tx_counts.setdefault(key, []).append(tx.source_candidate)

    for key, candidates in tx_counts.items():
        if len(candidates) >= min_uses:
            definition = json.loads(key)
            prim = Primitive(
                primitive_id=hashlib.sha256(key.encode()).hexdigest()[:16],
                name=definition.get("name", f"prim_{generation}"),
                definition=definition,
                verified_evidence=candidates,
                generation=generation,
                content_hash=hashlib.sha256(key.encode()).hexdigest()[:16],
            )
            promoted.append(prim)

    return promoted


def _make_id(prefix: str, generation: int) -> str:
    return f"{prefix}_g{generation}_{hashlib.sha256(f'{prefix}{generation}'.encode()).hexdigest()[:8]}"
