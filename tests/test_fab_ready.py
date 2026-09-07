from __future__ import annotations

from rnd_engine.fab_ready import (
    FAB_PROGRESSION,
    FIDELITY_ORDER,
    CandidateSnapshot,
    EvidenceReceipt,
    FabReadyRelease,
    FabState,
    Fidelity,
    GateStatus,
    KnowledgeItem,
    KnowledgeType,
    LineageRecord,
    Primitive,
    SearchPolicy,
    SearchSpaceState,
    ToolchainFingerprint,
    ToolProvider,
    check_fab_ready,
    fab_ready_required_gates,
    fidelity_requires,
)


def test_fidelity_order_complete():
    assert len(FIDELITY_ORDER) == 8
    assert FIDELITY_ORDER[0] == Fidelity.SURROGATE
    assert FIDELITY_ORDER[-1] == Fidelity.SILICON


def test_fidelity_requirements_monotonic():
    for i, level in enumerate(FIDELITY_ORDER):
        reqs = fidelity_requires(level)
        for j in range(i):
            assert FIDELITY_ORDER[j] in reqs


def test_fab_progression_complete():
    assert len(FAB_PROGRESSION) == 21
    assert FabState.DISCOVERED in FAB_PROGRESSION
    assert FabState.FAB_READY in FAB_PROGRESSION


def test_evidence_receipt_defaults():
    r = EvidenceReceipt()
    assert r.status == GateStatus.NOT_RUN
    assert r.fidelity == Fidelity.SURROGATE


def test_evidence_receipt_content_hash_stable():
    r = EvidenceReceipt(candidate_id="c1", stage="lint", status=GateStatus.PASS)
    assert r.content_hash() == r.content_hash()
    assert len(r.content_hash()) == 32

def test_check_fab_ready_all_pass():
    receipts = [
        EvidenceReceipt(stage=g, status=GateStatus.PASS)
        for g in fab_ready_required_gates()
    ]
    ready, blocking = check_fab_ready(receipts)
    assert ready is True
    assert blocking == []

def test_check_fab_ready_missing_tool():
    receipts = [
        EvidenceReceipt(stage="rtl_lint", status=GateStatus.PASS),
        EvidenceReceipt(stage="simulation", status=GateStatus.BLOCKED),
    ]
    ready, blocking = check_fab_ready(receipts)
    assert ready is False
    assert "simulation" in blocking

def test_check_fab_ready_not_run():
    receipts = [EvidenceReceipt(stage="rtl_lint", status=GateStatus.NOT_RUN)]
    ready, _ = check_fab_ready(receipts)
    assert ready is False

def test_check_fab_ready_empty():
    ready, blocking = check_fab_ready([])
    assert ready is False
    assert len(blocking) == len(fab_ready_required_gates())

def test_gate_status_enum():
    assert GateStatus.PASS == "PASS"
    assert GateStatus.BLOCKED == "BLOCKED"

def test_knowledge_item_defaults():
    k = KnowledgeItem()
    assert k.knowledge_type == KnowledgeType.VERIFIED_SOLUTION
    assert k.fidelity == Fidelity.SURROGATE

def test_toolchain_fingerprint_empty():
    tf = ToolchainFingerprint()
    assert tf.hash()

def test_toolchain_fingerprint_changes():
    tf1 = ToolchainFingerprint(tools={"yosys": ToolProvider(name="yosys", version="0.38")})
    tf2 = ToolchainFingerprint(tools={"yosys": ToolProvider(name="yosys", version="0.39")})
    assert tf1.hash() != tf2.hash()

def test_search_policy_defaults():
    p = SearchPolicy()
    assert p.exploration_rate == 0.3
    assert p.primitive_reuse is True
    assert p.failure_guided is True

def test_search_space_state_defaults():
    s = SearchSpaceState()
    assert "generic" in s.active_families
    assert s.available_primitives == []

def test_fab_ready_release_not_ready():
    r = FabReadyRelease()
    assert r.fab_ready is False
    assert r.fab_state == FabState.DISCOVERED

def test_candidate_snapshot_defaults():
    s = CandidateSnapshot()
    assert s.random_seed == 42
    assert s.proposed_files == []
    assert s.rtl_files == []

def test_primitive_defaults():
    p = Primitive()
    assert p.known_uses == []
    assert p.verified_evidence == []

def test_lineage_record_defaults():
    l = LineageRecord()
    assert l.mutations == []
    assert l.failures == []
