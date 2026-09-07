"""Command-line interface: legacy flags + hardware-flow subcommands (§9).

Legacy (no subcommand):

    rnd-engine --population 32 --generations 10 --seed 42 --domain heterogeneous

Subcommands preserve those flags and add hardware-flow stages:

    rnd-engine flow --stages lint,simulation
    rnd-engine specify | rtl | verify | formal | synth | physical | sta
                 | power | drc | lvs | signoff | release | experiment
                 | status | doctor | eda-doctor
"""

from __future__ import annotations

import json
from pathlib import Path

from .engine import InventionEngine
from .flow import DEFAULT_STAGES, run_flow
from .models import Domain

_DOMAIN_CHOICES = [d.value for d in Domain]


def _search(args) -> InventionEngine:
    """Run a deterministic search and return the engine (legacy behavior)."""
    engine = InventionEngine(
        population=args.population,
        generations=args.generations,
        seed=args.seed,
        domain=Domain(args.domain),
    )
    engine.run()
    return engine


def _best_design(args):
    """Best surrogate candidate for the CLI stage subcommands."""
    engine = InventionEngine(
        population=args.population, generations=args.generations,
        seed=args.seed, domain=Domain(args.domain))
    engine.run()
    best = engine.archive.best(1)
    if not best:
        raise SystemExit("no candidate found")
    return best[0].design


def _cmd_flow(args) -> int:
    import os
    stages = tuple(s.strip() for s in args.stages.split(",")) if args.stages else DEFAULT_STAGES
    design = _best_design(args)
    # Forward PDK_ROOT/EDA_ROOT so physical stages can resolve the PDK
    flow_env = {k: v for k, v in os.environ.items() if k.startswith(("PDK_ROOT", "EDA_ROOT", "OPENROAD", "MAGIC", "NETGEN", "OPENSTA"))}
    receipt = run_flow(
        design,
        profile=args.profile,
        stages=stages,
        out_dir=args.out_dir,
        config_dir=args.config_dir,
        experiment_id=args.experiment_id or "",
        env=flow_env if flow_env else None,
    )
    print(json.dumps({
        "candidate_id": receipt.candidate_id,
        "evidence_level": receipt.evidence_level,
        "signoff_tapeout_ready": receipt.signoff_tapeout_ready,
        "stages": {s.stage: s.status for s in receipt.stages},
        "receipt": f"receipts/{receipt.candidate_id}/receipt.json",
    }, indent=2))
    return 0


def _cmd_doctor(args) -> int:
    from .edadoctor import format_doctor_report, run_eda_doctor
    report = run_eda_doctor(args.profile, workdir=args.out_dir,
                            config_dir=args.config_dir)
    print(format_doctor_report(report))
    if args.strict and (report.summary.get("READY", 0) < len(report.tools)):
        not_ready = [t.tool for t in report.tools if t.status != "READY"]
        print(f"strict: {len(not_ready)} tool(s) not ready: {', '.join(not_ready)}")
        return 1
    return 0


def _cmd_status(args) -> int:
    from .receipt import load_receipt
    root = Path(args.out_dir)
    print("=== computational-rnd-engine status ===")
    print(f"artifacts root: {root.resolve()}")
    receipts_dir = root / "receipts"
    if receipts_dir.is_dir():
        for candidate_dir in sorted(receipts_dir.iterdir()):
            receipt_path = candidate_dir / "receipt.json"
            if not receipt_path.is_file():
                continue
            receipt = load_receipt(receipt_path)
            print(f"candidate {receipt.candidate_id}")
            print(f"  evidence_level={receipt.evidence_level}")
            for stage in receipt.stages:
                print(f"  {stage.stage:11s} {stage.status}")
    else:
        print("no receipts found (no hardware flow has run)")
    return 0


def _cmd_release(args) -> int:
    """Report the release assessment for the latest receipt."""
    root = Path(args.out_dir)
    receipts_dir = root / "receipts"
    if not receipts_dir.is_dir():
        print("no receipts found -- run 'rnd-engine flow' first")
        return 1
    candidates = sorted(receipts_dir.iterdir())
    latest = None
    for c in candidates:
        rp = c / "receipt.json"
        if rp.is_file():
            latest = rp
    if latest is None:
        print("no valid receipt found")
        return 1
    from .receipt import load_receipt as _load
    receipt = _load(latest)
    print(f"candidate {receipt.candidate_id}")
    print(f"  evidence_level={receipt.evidence_level}")
    print(f"  signoff_tapeout_ready={receipt.signoff_tapeout_ready}")
    print(f"  configuration_hash={receipt.configuration_hash}")
    print(f"  toolchain_hash={receipt.toolchain_hash}")
    print(f"  pdk_hash={receipt.pdk_hash}")
    for stage in receipt.stages:
        print(f"  {stage.stage:11s} {stage.status}")
    return 0


def _cmd_signoff(args) -> int:
    """Run the full flow for the best candidate and print signoff info."""
    design = _best_design(args)
    receipt = run_flow(
        design, profile=args.profile,
        stages=("lint", "simulation", "formal", "synthesis", "physical",
                "sta", "power", "drc", "lvs"),
        out_dir=args.out_dir, config_dir=args.config_dir)
    signoff_path = (Path(args.out_dir) / "reports" / "signoff"
                    / design.id / "signoff.json")
    if signoff_path.exists():
        data = json.loads(signoff_path.read_text(encoding="utf-8"))
        print(json.dumps(data, indent=2)[:4000])
    print(f"evidence_level={receipt.evidence_level}")
    return 0


def _cmd_experiment(args) -> int:
    """Run a deterministic experiment."""
    from .experiments import ExperimentConfig, run_experiment
    config = ExperimentConfig(
        name=args.name or "cli",
        seed=args.seed, domain=args.domain,
        population=args.population, generations=args.generations,
    )
    manifest, _funnel = run_experiment(config, out_dir=args.out_dir)
    print(json.dumps({
        "experiment_id": manifest.experiment_id,
        "config": config.model_dump(mode="json"),
        "artifacts": [a.path for a in manifest.artifacts],
    }, indent=2))
    return 0


def _cmd_fab_status(args) -> int:
    """Report persisted fab lifecycle state for every candidate."""
    from .fab_state import compute_fab_state
    from .receipt import load_receipt

    root = Path(args.out_dir)
    receipts_dir = root / "receipts"
    found = 0
    if receipts_dir.is_dir():
        for candidate_dir in sorted(receipts_dir.iterdir()):
            fs_path = candidate_dir / "fab_state.json"
            rp = candidate_dir / "receipt.json"
            if fs_path.is_file():
                data = json.loads(fs_path.read_text(encoding="utf-8"))
            elif rp.is_file():
                # Legacy receipt persisted before fab_state.json existed.
                data = compute_fab_state(load_receipt(rp))
            else:
                continue
            found += 1
            print(f"candidate {data['candidate_id']}")
            print(f"  state          {data['current_state']}"
                  f"{' (terminal)' if data['is_terminal'] else ''}")
            print(f"  fab_ready      {data['fab_ready']}")
            completed = data.get("completed_states", [])
            print(f"  completed      {len(completed)}: {', '.join(completed)}")
            blocked = data.get("blocked_stages", [])
            print(f"  blocked_stages {len(blocked)}: {', '.join(blocked) or '-'}")
            not_run = data.get("not_run_stages", [])
            print(f"  not_run        {len(not_run)}: {', '.join(not_run) or '-'}")
            blocking = data.get("blocking_gates", [])
            print(f"  blocking_gates {len(blocking)}: {', '.join(blocking) or '-'}")
            print(f"  transitions    {data.get('transitions', 0)}"
                  f"  digest {data.get('machine_digest', '')}")
    if not found:
        print("no fab state found -- run 'rnd-engine flow' first")
        return 1
    return 0


def _cmd_lineage(args) -> int:
    """Report persisted experiment promotion lineage (honest about gaps)."""
    root = Path(args.out_dir)
    exp_root = root / "experiments"
    if not exp_root.is_dir():
        print("no experiments found -- run 'rnd-engine experiment' first")
        return 1
    found = 0
    for exp_dir in sorted(exp_root.iterdir()):
        promo_path = exp_dir / "promotion.json"
        manifest_path = exp_dir / "manifest.json"
        if not promo_path.is_file():
            continue
        found += 1
        print(f"experiment {exp_dir.name}")
        funnel = json.loads(promo_path.read_text(encoding="utf-8"))
        summary = funnel.get("counts_summary") or {
            lvl: len(recs) for lvl, recs in (funnel.get("levels") or {}).items()}
        for lvl in sorted(summary):
            print(f"  rung {lvl:9s} candidates: {summary[lvl]}")
        if manifest_path.is_file():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            n_art = len(manifest.get("artifacts", []))
            print(f"  manifest artifacts: {n_art} (sha256-addressed)")
        print("  note: surrogate-only lineage; hardware lineage arrives"
              " with real EDA evidence")
    if not found:
        print("no persisted promotion funnels found")
        return 1
    return 0


def _build_parser():
    import argparse

    parser = argparse.ArgumentParser(
        prog="rnd-engine",
        description="Computational R&D invention engine + hardware validation flow",
    )
    parser.add_argument("--population", type=int, default=16,
                        help="Search population size")
    parser.add_argument("--generations", type=int, default=2,
                        help="Search generations")
    parser.add_argument("--seed", type=int, default=1,
                        help="Deterministic seed")
    parser.add_argument("--domain", default="cpu", choices=_DOMAIN_CHOICES,
                        help="Search domain")

    sub = parser.add_subparsers(dest="cmd")

    def _add_search_args(p):
        p.add_argument("--population", type=int, default=16)
        p.add_argument("--generations", type=int, default=2)
        p.add_argument("--seed", type=int, default=1)
        p.add_argument("--domain", default="cpu", choices=_DOMAIN_CHOICES)

    # eda-doctor
    p_doc = sub.add_parser("eda-doctor", help="Run EDA toolchain diagnostics")
    _add_search_args(p_doc)
    p_doc.add_argument("--profile", default="sky130")
    p_doc.add_argument("--out-dir", default="artifacts")
    p_doc.add_argument("--config-dir", default="configs")
    p_doc.add_argument("--strict", action="store_true")
    p_doc.set_defaults(func=_cmd_doctor)

    # doctor (alias)
    p_doc2 = sub.add_parser("doctor", help="Alias for eda-doctor")
    _add_search_args(p_doc2)
    p_doc2.add_argument("--profile", default="sky130")
    p_doc2.add_argument("--out-dir", default="artifacts")
    p_doc2.add_argument("--config-dir", default="configs")
    p_doc2.add_argument("--strict", action="store_true")
    p_doc2.set_defaults(func=_cmd_doctor)

    # flow
    p_flow = sub.add_parser("flow", help="Run the hardware validation flow")
    _add_search_args(p_flow)
    p_flow.add_argument("--profile", default="sky130")
    p_flow.add_argument("--stages", default=None,
                        help="Comma-separated stage list")
    p_flow.add_argument("--out-dir", default="artifacts")
    p_flow.add_argument("--config-dir", default="configs")
    p_flow.add_argument("--experiment-id", default=None)
    p_flow.set_defaults(func=_cmd_flow)

    # status
    p_st = sub.add_parser("status", help="Show receipt status for past runs")
    _add_search_args(p_st)
    p_st.add_argument("--out-dir", default="artifacts")
    p_st.set_defaults(func=_cmd_status)

    # fab-status
    p_fab = sub.add_parser("fab-status",
                           help="Show fab lifecycle state for past runs")
    _add_search_args(p_fab)
    p_fab.add_argument("--out-dir", default="artifacts")
    p_fab.set_defaults(func=_cmd_fab_status)

    # lineage
    p_lin = sub.add_parser("lineage",
                           help="Show experiment promotion lineage")
    _add_search_args(p_lin)
    p_lin.add_argument("--out-dir", default="artifacts")
    p_lin.set_defaults(func=_cmd_lineage)

    # release
    p_rel = sub.add_parser("release", help="Show release assessment")
    _add_search_args(p_rel)
    p_rel.add_argument("--out-dir", default="artifacts")
    p_rel.set_defaults(func=_cmd_release)

    # signoff
    p_so = sub.add_parser("signoff", help="Run full flow and show signoff")
    _add_search_args(p_so)
    p_so.add_argument("--profile", default="sky130")
    p_so.add_argument("--out-dir", default="artifacts")
    p_so.add_argument("--config-dir", default="configs")
    p_so.set_defaults(func=_cmd_signoff)

    # experiment
    p_exp = sub.add_parser("experiment", help="Run a deterministic experiment")
    _add_search_args(p_exp)
    p_exp.add_argument("--name", default=None)
    p_exp.add_argument("--out-dir", default="artifacts")
    p_exp.set_defaults(func=_cmd_experiment)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Legacy: no subcommand => run search
    if args.cmd is None:
        _search(args)
        return 0

    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())