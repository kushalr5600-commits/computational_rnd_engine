from __future__ import annotations

from rnd_engine.receipt import (
    EVIDENCE_RTL,
    EVIDENCE_SIGNOFF,
    EVIDENCE_SURROGATE,
    STAGE_BLOCKED,
    STAGE_FAIL,
    STAGE_PASS,
    StageReceipt,
    ToolRunReceipt,
    evidence_from_stages,
    load_receipt,
    signoff_ready_from_stages,
    write_receipt,
)


def test_tool_run_receipt_from_run():
    run = type('Run', (), {
        'tool': 'verilator', 'command': ['verilator', '--lint-only', 'x.sv'],
        'status': 'PASSED', 'exit_code': 0, 'stdout': 'ok', 'stderr': '',
        'tool_version': '5.018', 'duration_s': 1.5, 'error_code': None,
        'workdir': '/tmp', 'env_keys': ['PATH'],
    })()
    r = ToolRunReceipt.from_run(run)
    assert r.tool == 'verilator'
    assert r.status == 'PASSED'


def test_evidence_all_pass_stages():
    stages = [
        StageReceipt(stage='lint', status=STAGE_PASS),
        StageReceipt(stage='simulation', status=STAGE_PASS),
        StageReceipt(stage='formal', status=STAGE_PASS),
        StageReceipt(stage='synthesis', status=STAGE_PASS),
        StageReceipt(stage='physical', status=STAGE_PASS),
        StageReceipt(stage='sta', status=STAGE_PASS),
        StageReceipt(stage='power', status=STAGE_PASS),
        StageReceipt(stage='drc', status=STAGE_PASS),
        StageReceipt(stage='lvs', status=STAGE_PASS),
    ]
    assert evidence_from_stages(stages) == EVIDENCE_SIGNOFF

def test_evidence_blocked_caps_level():
    stages = [
        StageReceipt(stage='lint', status=STAGE_PASS),
        StageReceipt(stage='simulation', status=STAGE_BLOCKED),
    ]
    assert evidence_from_stages(stages) == EVIDENCE_RTL

def test_evidence_all_blocked_is_surrogate():
    stages = [StageReceipt(stage='lint', status=STAGE_BLOCKED)]
    assert evidence_from_stages(stages) == EVIDENCE_SURROGATE

def test_signoff_ready_all_pass():
    stages = [
        StageReceipt(stage='lint', status=STAGE_PASS),
        StageReceipt(stage='simulation', status=STAGE_PASS),
        StageReceipt(stage='formal', status=STAGE_PASS),
        StageReceipt(stage='synthesis', status=STAGE_PASS),
        StageReceipt(stage='physical', status=STAGE_PASS),
        StageReceipt(stage='sta', status=STAGE_PASS),
        StageReceipt(stage='power', status=STAGE_PASS),
        StageReceipt(stage='drc', status=STAGE_PASS),
        StageReceipt(stage='lvs', status=STAGE_PASS),
    ]
    assert signoff_ready_from_stages(stages) is True

def test_signoff_ready_one_fails():
    stages = [
        StageReceipt(stage='lint', status=STAGE_PASS),
        StageReceipt(stage='simulation', status=STAGE_PASS),
        StageReceipt(stage='formal', status=STAGE_PASS),
        StageReceipt(stage='synthesis', status=STAGE_PASS),
        StageReceipt(stage='physical', status=STAGE_PASS),
        StageReceipt(stage='sta', status=STAGE_PASS),
        StageReceipt(stage='power', status=STAGE_PASS),
        StageReceipt(stage='drc', status=STAGE_PASS),
        StageReceipt(stage='lvs', status=STAGE_FAIL),
    ]
    assert signoff_ready_from_stages(stages) is False

def test_signoff_ready_missing_stage():
    stages = [StageReceipt(stage='lint', status=STAGE_PASS)]
    assert signoff_ready_from_stages(stages) is False

def test_write_and_load_receipt(tmp_path):
    from rnd_engine.receipt import FlowReceipt
    receipt = FlowReceipt(
        candidate_id='test123',
        experiment_id='exp1',
        configuration_hash='abc123',
        stages=[StageReceipt(stage='lint', status=STAGE_PASS)],
    )
    path = write_receipt(receipt, tmp_path)
    assert path.exists()
    loaded = load_receipt(path)
    assert loaded.candidate_id == 'test123'
    assert loaded.stages[0].status == STAGE_PASS

def test_receipt_hash_stable(tmp_path):
    from rnd_engine.receipt import FlowReceipt
    r1 = FlowReceipt(candidate_id='c1', configuration_hash='h1', stages=[StageReceipt(stage='lint', status=STAGE_PASS)])
    r2 = FlowReceipt(candidate_id='c1', configuration_hash='h1', stages=[StageReceipt(stage='lint', status=STAGE_PASS)])
    assert r1.receipt_hash() == r2.receipt_hash()
