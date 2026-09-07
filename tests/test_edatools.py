from __future__ import annotations

from rnd_engine.edatools import (
    RUN_FAILED,
    RUN_NOT_FOUND,
    RUN_PASSED,
    RUN_TIMEOUT,
    ToolRun,
    _resolve_binary,
    run_external_tool,
    toolchain_fingerprint,
)
from rnd_engine.errors import (
    TIMEOUT,
    TOOL_EXECUTION_FAILED,
    TOOL_NOT_FOUND,
    ExternalToolError,
)


def test_tool_run_passed_property():
    run = ToolRun(tool='test', status=RUN_PASSED, exit_code=0)
    assert run.passed is True


def test_tool_run_failed_not_passed():
    run = ToolRun(tool='test', status=RUN_FAILED, exit_code=1)
    assert run.passed is False


def test_tool_run_not_found_not_passed():
    run = ToolRun(tool='test', status=RUN_NOT_FOUND)
    assert run.passed is False


def test_tool_run_timeout_not_passed():
    run = ToolRun(tool='test', status=RUN_TIMEOUT)
    assert run.passed is False


def test_run_external_tool_not_found(tmp_path):
    config = {'tools': {}, 'security': {'env_allowlist': []}}
    run = run_external_tool(['nonexistent_tool_xyz'], tool='nonexistent_tool_xyz', config=config, workdir=tmp_path)
    assert run.status == RUN_NOT_FOUND
    assert run.error_code == TOOL_NOT_FOUND


def test_run_external_tool_success(tmp_path):
    config = {'tools': {}, 'security': {'env_allowlist': []}}
    run = run_external_tool(['python', '--version'], tool='python', config=config, workdir=tmp_path)
    assert run.status == RUN_PASSED
    assert run.exit_code == 0
    assert run.passed is True


def test_run_external_tool_failure(tmp_path):
    config = {'tools': {}, 'security': {'env_allowlist': []}}
    run = run_external_tool(['python', '-c', 'import sys; sys.exit(1)'], tool='python', config=config, workdir=tmp_path)
    assert run.status == RUN_FAILED
    assert run.exit_code == 1


def test_run_external_tool_timeout(tmp_path):
    config = {'tools': {}, 'security': {'env_allowlist': [], 'default_timeout_s': 1}}
    run = run_external_tool(['python', '-c', 'import time; time.sleep(10)'], tool='python', config=config, workdir=tmp_path, timeout_s=1)
    assert run.status == RUN_TIMEOUT
    assert run.error_code == TIMEOUT


def test_toolchain_fingerprint_empty():
    config = {'tools': {}}
    fp = toolchain_fingerprint(config=config)
    assert fp == {}


def test_resolve_binary_missing():
    config = {'tools': {}}
    assert _resolve_binary('verilator', config) is None


def test_external_tool_error_from_run():
    run = ToolRun(tool='verilator', status=RUN_FAILED, exit_code=1)
    err = ExternalToolError.from_run(run, stage='lint', candidate_id='abc123')
    assert err.code == TOOL_EXECUTION_FAILED
    assert err.tool == 'verilator'
    assert err.stage == 'lint'
    assert err.candidate_id == 'abc123'


def test_external_tool_error_from_config():
    err = ExternalToolError.from_config('bad config')
    assert err.code == 'CONFIG_INVALID'


def test_external_tool_error_from_pdk():
    err = ExternalToolError.from_pdk('missing pdk')
    assert err.code == 'PDK_MISSING'


def test_external_tool_error_from_artifact():
    err = ExternalToolError.from_artifact('bad artifact')
    assert err.code == 'ARTIFACT_INVALID'


def test_external_tool_error_to_dict():
    err = ExternalToolError(TOOL_NOT_FOUND, 'verilator', 'not found', exit_code=None)
    d = err.to_dict()
    assert d['code'] == TOOL_NOT_FOUND
    assert d['tool'] == 'verilator'
    assert 'timestamp_utc' in d


def test_external_tool_error_env_filters_secrets():
    err = ExternalToolError(TOOL_EXECUTION_FAILED, 'tool', 'msg', env={'MY_SECRET_KEY': 'abc', 'PATH': '/usr/bin'})
    assert 'MY_SECRET_KEY' not in err.env
    assert 'PATH' in err.env
