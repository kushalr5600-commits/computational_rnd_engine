from __future__ import annotations

from rnd_engine.cli import _build_parser


def test_parser_legacy_flags():
    parser = _build_parser()
    args = parser.parse_args(['--population', '8', '--generations', '3', '--seed', '99'])
    assert args.population == 8
    assert args.generations == 3
    assert args.seed == 99


def test_parser_subcommand_eda_doctor():
    parser = _build_parser()
    args = parser.parse_args(['eda-doctor', '--profile', 'sky130'])
    assert args.cmd == 'eda-doctor'
    assert args.profile == 'sky130'


def test_parser_subcommand_flow():
    parser = _build_parser()
    args = parser.parse_args(['flow', '--stages', 'lint,simulation'])
    assert args.cmd == 'flow'
    assert args.stages == 'lint,simulation'


def test_parser_subcommand_doctor_alias():
    parser = _build_parser()
    args = parser.parse_args(['doctor'])
    assert args.cmd == 'doctor'


def test_parser_default_values():
    parser = _build_parser()
    args = parser.parse_args([])
    assert args.population == 16
    assert args.generations == 2
    assert args.seed == 1
    assert args.domain == 'cpu'

# --- fab-status / lineage ---------------------------------------------------

def _run_cmd(argv):
    from rnd_engine.cli import main
    return main(argv)


def test_fab_status_reports_persisted_state(tmp_path, capsys):
    """fab-status reads the persisted fab_state.json for a real flow run."""
    from rnd_engine.engine import InventionEngine
    from rnd_engine.flow import run_flow
    from rnd_engine.models import Domain

    engine = InventionEngine(population=4, generations=1, seed=42,
                             domain=Domain('cpu'))
    engine.run()
    design = engine.archive.best(1)[0].design
    run_flow(design, stages=('lint',), out_dir=str(tmp_path))
    rc = _run_cmd(['fab-status', '--out-dir', str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert 'state          DISCOVERED' in out
    assert 'fab_ready      False' in out
    assert 'lint' in out  # blocked stage recorded


def test_fab_status_no_data_exits_nonzero(tmp_path, capsys):
    rc = _run_cmd(['fab-status', '--out-dir', str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 1
    assert 'no fab state found' in out


def test_lineage_reports_experiment_funnel(tmp_path, capsys):
    """lineage reads the persisted promotion funnel of a real experiment."""
    from rnd_engine.experiments import ExperimentConfig, run_experiment

    config = ExperimentConfig(name='cli-lineage', seed=7, domain='cpu',
                              population=4, generations=1)
    run_experiment(config, out_dir=str(tmp_path))
    rc = _run_cmd(['lineage', '--out-dir', str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 0
    assert 'rung SURROGATE candidates: 4' in out
    assert 'surrogate-only lineage' in out


def test_lineage_no_data_exits_nonzero(tmp_path, capsys):
    rc = _run_cmd(['lineage', '--out-dir', str(tmp_path)])
    out = capsys.readouterr().out
    assert rc == 1
    assert 'no experiments found' in out


def test_parser_fab_status_and_lineage():
    parser = _build_parser()
    assert parser.parse_args(['fab-status']).cmd == 'fab-status'
    assert parser.parse_args(['lineage']).cmd == 'lineage'

