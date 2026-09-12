"""GRID//OPS development CLI.

Commands exist so both developers run the same acceptance seam:

    python -m gridops.cli validate-config configs/scenario_synthetic.json
    python -m gridops.cli run configs/scenario_synthetic.json --controller ambiguity_aware
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .contracts.state import BatteryParams, VehicleParams
from .decision.belief import RivalBelief
from .decision.hmm_belief import HMMBelief, HMMConfig
from .decision.planning import ConditionalConvexPlanner, PlannerConfig
from .evaluation.controllers import (
    AmbiguityAwareController,
    Controller,
    ConvexPlannerController,
    PosteriorMeanPlanner,
    ReferenceController,
    StationaryPlanner,
)
from .evaluation.batch import (
    ABLATION_NAMES,
    CONTACT_MARGIN_M,
    CONTROLLER_NAMES,
    default_manifest,
    run_batch,
)
from .evaluation.calibration import calibrate
from .evaluation.report import build_bundle, render_markdown
from .evaluation.runner import EpisodeConfig, EpisodeRunner
from .race_value.lap_map import default_terminal_value
from .simulation.rivals import RivalPolicy, RivalPolicyConfig
from .simulation.track import synthetic_circuit
from .simulation.tyres import default_tyre_params
from .contracts.ruleset import default_ruleset
from .evaluation.splits import (
    apply_battery,
    apply_rival,
    apply_tyres,
    apply_vehicle,
    split_override,
)

REQUIRED_KEYS = (
    "schema_version",
    "execution_ready",
    "scenario_id",
    "run_mode",
    "duration_s",
    "dt_s",
    "replan_interval_s",
    "decision_budget_s",
    "initial_speed_mps",
    "laps_remaining",
)

SCHEMA_VERSION = "gridops.scenario.v1"


def validate_config(path: str | Path) -> tuple[bool, list[str]]:
    errors: list[str] = []
    try:
        data = json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return False, [f"cannot read config: {exc}"]

    for key in REQUIRED_KEYS:
        if key not in data:
            errors.append(f"missing required key: {key}")
        elif data[key] is None:
            errors.append(f"unresolved (null) required key: {key}")

    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if data.get("execution_ready") is not True:
        errors.append("execution_ready must be true to run")
    if data.get("dt_s") and data.get("replan_interval_s"):
        if data["dt_s"] > data["replan_interval_s"]:
            errors.append("dt_s must not exceed replan_interval_s")

    return (not errors), errors


def _controller(name: str, runner: EpisodeRunner, seed: int) -> Controller:
    if name == "reference":
        return ReferenceController()
    if name == "stationary":
        return StationaryPlanner(runner.terminal_value, horizon=2, iterations=200)
    if name == "posterior_mean":
        return PosteriorMeanPlanner(runner.terminal_value, defensive_probability=0.5)
    if name == "convex":
        return ConvexPlannerController(
            ConditionalConvexPlanner(
                runner.track, runner.vehicle, runner.battery, runner.terminal_value,
                PlannerConfig(),
            )
        )
    if name == "ambiguity_aware":
        return AmbiguityAwareController(
            terminal_value=runner.terminal_value,
            belief=RivalBelief.uniform(),
            horizon=3,
            iterations=400,
            seed=seed,
        )
    if name == "ambiguity_aware_convex":
        return AmbiguityAwareController(
            terminal_value=runner.terminal_value,
            belief=RivalBelief.uniform(),
            horizon=3,
            iterations=400,
            planner=ConditionalConvexPlanner(
                runner.track, runner.vehicle, runner.battery, runner.terminal_value,
                PlannerConfig(),
            ),
            seed=seed,
        )
    if name == "ambiguity_aware_hmm":
        return AmbiguityAwareController(
            terminal_value=runner.terminal_value,
            belief=HMMBelief(HMMConfig(stationary=False)),
            horizon=3,
            iterations=400,
            seed=seed,
        )
    if name == "ambiguity_aware_hmm_stationary":
        return AmbiguityAwareController(
            terminal_value=runner.terminal_value,
            belief=HMMBelief(HMMConfig(stationary=True)),
            horizon=3,
            iterations=400,
            seed=seed,
        )
    raise ValueError(f"unknown controller: {name}")


def _build_runner(data: dict[str, Any], split: str = "development") -> EpisodeRunner:
    override = split_override(split)
    battery = apply_battery(BatteryParams(**data.get("battery", {})), override)
    vehicle = apply_vehicle(VehicleParams(**data.get("vehicle", {})), override)
    tyre_params = apply_tyres(default_tyre_params(), override)
    config = EpisodeConfig(
        duration_s=data["duration_s"],
        dt_s=data["dt_s"],
        replan_interval_s=data["replan_interval_s"],
        decision_budget_s=data["decision_budget_s"],
        ego_progress_m=data.get("ego_progress_m", 0.0),
        rival_progress_m=data.get("rival_progress_m", 30.0),
        initial_speed_mps=data["initial_speed_mps"],
        laps_remaining=data["laps_remaining"],
        run_mode=data["run_mode"],
        compound=data.get("compound", "medium"),
        compound_identity=data.get("compound_identity", "C4"),
        initial_wear=data.get("initial_wear", 0.0),
    )
    return EpisodeRunner(
        track=synthetic_circuit(),
        vehicle=vehicle,
        battery=battery,
        terminal_value=default_terminal_value(battery),
        config=config,
        tyre_params=tyre_params,
        rules=default_ruleset(),
        rival_config=apply_rival(RivalPolicyConfig(), override),
    )


def _print_timeline(report) -> None:
    """Human-readable decision timeline for one episode."""
    print(
        f"{report.run_mode}  duration={report.duration_s:.0f}s  "
        f"decisions={len(report.decisions)}"
    )
    print(f"{'t s':>6s} {'family':>14s} {'status':>17s} {'gap m':>7s} {'P kW':>7s}  reasons")
    for d in report.decisions:
        print(
            f"{d['time_s']:6.1f} {d['family']:>14s} {d['status']:>17s} "
            f"{d['gap_m']:7.2f} {d['p_k_dc_w'] / 1000.0:7.1f}  {','.join(d['reason_codes'])}"
        )
    print(
        f"\nfinal gap {report.final_gap_m:.2f} m | energy spent "
        f"{report.ego_energy_spent_j / 1e6:.3f} MJ | passes {report.pass_events} | "
        f"catch-ups {report.catch_up_events} | contacts {report.contacts}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="gridops")
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate-config", help="check a scenario config")
    validate.add_argument("path")

    run = sub.add_parser("run", help="run one deterministic episode")
    run.add_argument("path")
    run.add_argument(
        "--controller",
        default="ambiguity_aware",
        choices=[
            "reference",
            "stationary",
            "posterior_mean",
            "convex",
            "ambiguity_aware",
            "ambiguity_aware_convex",
            "ambiguity_aware_hmm",
            "ambiguity_aware_hmm_stationary",
        ],
    )
    run.add_argument("--rival-policy", default=None)
    run.add_argument("--seed", type=int, default=1)
    run.add_argument("--show", action="store_true", help="print the decision timeline")
    run.add_argument("--out", default=None, help="write the full run record as JSON")

    bench = sub.add_parser("benchmark", help="paired controller x rival-policy batch")
    bench.add_argument("path")
    bench.add_argument("--seed", type=int, default=1)
    bench.add_argument("--out", default=None, help="write JSON rows to this path")

    batch = sub.add_parser("batch", help="frozen paired batch with ablations")
    batch.add_argument("path")
    batch.add_argument("--seeds", type=int, default=5)
    batch.add_argument("--split", default="development")
    batch.add_argument(
        "--calibrate-split", default=None,
        help="split used to fit the controller's models (default: split's own)",
    )
    batch.add_argument("--controllers", default=None, help="comma-separated")
    batch.add_argument("--policies", default=None, help="comma-separated")
    batch.add_argument("--no-calibrate", action="store_true")
    batch.add_argument(
        "--contact-margin", type=float, default=CONTACT_MARGIN_M,
        help="declared model-error margin for the contact projection (metres)",
    )
    batch.add_argument("--out", default=None)

    report = sub.add_parser("report", help="build the pitch evidence bundle")
    report.add_argument("batches", nargs="+")
    report.add_argument("--out", default=None)
    report.add_argument("--markdown", default=None)

    html = sub.add_parser("export-html", help="render recorded runs as a web page")
    html.add_argument("--runs", nargs="*", default=[], help="run JSON files from 'run --out'")
    html.add_argument("--bundle", default=None, help="pitch bundle JSON from 'report'")
    html.add_argument("--out", required=True)

    args = parser.parse_args(argv)

    if args.command == "validate-config":
        ok, errors = validate_config(args.path)
        print(json.dumps({"ok": ok, "errors": errors}, indent=2))
        return 0 if ok else 1

    if args.command == "run":
        ok, errors = validate_config(args.path)
        if not ok:
            print(json.dumps({"ok": False, "errors": errors}, indent=2))
            return 1
        data = json.loads(Path(args.path).read_text())
        runner = _build_runner(data)
        controller = _controller(args.controller, runner, args.seed)
        policy_name = args.rival_policy or data.get("rival_policy", "matching")
        report = runner.run(
            controller,
            rival_policy=RivalPolicy(policy_name),
            seed=args.seed,
        )
        if args.show:
            _print_timeline(report)
        else:
            print(json.dumps(report.summary(), indent=2))
        if args.out:
            payload = {
                "label": f"{args.controller} vs {policy_name}",
                "summary": report.summary(),
                "decisions": report.decisions,
                "trace": report.trace,
            }
            Path(args.out).write_text(json.dumps(payload, indent=2))
        return 0

    if args.command == "benchmark":
        ok, errors = validate_config(args.path)
        if not ok:
            print(json.dumps({"ok": False, "errors": errors}, indent=2))
            return 1
        data = json.loads(Path(args.path).read_text())
        rows = _benchmark(data, args.seed)
        if args.out:
            Path(args.out).write_text(json.dumps(rows, indent=2))
        print(json.dumps(rows, indent=2))
        return 0

    if args.command == "batch":
        ok, errors = validate_config(args.path)
        if not ok:
            print(json.dumps({"ok": False, "errors": errors}, indent=2))
            return 1
        data = json.loads(Path(args.path).read_text())
        calibration = None
        if not args.no_calibrate:
            override = split_override(args.split)
            calibration_split = args.calibrate_split or override.calibration_split
            probe = _build_runner(data, calibration_split)
            calibration = calibrate(
                probe.track, probe.vehicle, probe.battery,
                tyre_params=probe.tyre_params,
                rival_config=probe.rival_config,
            )
        controllers = (
            tuple(args.controllers.split(",")) if args.controllers else ABLATION_NAMES
        )
        policies = tuple(args.policies.split(",")) if args.policies else None
        manifest = default_manifest(
            seeds=tuple(range(1, args.seeds + 1)),
            split=args.split,
            controllers=controllers,
            policies=policies,
        )
        result = run_batch(
            manifest, lambda: _build_runner(data, args.split), calibration,
            contact_margin_m=args.contact_margin,
        )
        payload = result.to_dict()
        if args.out:
            Path(args.out).write_text(json.dumps(payload, indent=2))
        print(json.dumps({"manifest": payload["manifest"], "aggregate": payload["aggregate"]}, indent=2))
        return 0

    if args.command == "report":
        batches = [json.loads(Path(path).read_text()) for path in args.batches]
        bundle = build_bundle(batches)
        if args.out:
            Path(args.out).write_text(json.dumps(bundle, indent=2))
        markdown = render_markdown(bundle)
        if args.markdown:
            Path(args.markdown).write_text(markdown)
        print(markdown)
        return 0

    if args.command == "export-html":
        from .presentation.html import load_json, write_report

        runs = [load_json(path) for path in args.runs]
        bundle = load_json(args.bundle) if args.bundle else None
        write_report(runs, bundle, args.out)
        print(json.dumps({"ok": True, "output": args.out, "runs": len(runs)}, indent=2))
        return 0

    return 2


def _benchmark(data: dict[str, Any], seed: int) -> list[dict[str, Any]]:
    """Paired comparison: each controller against each rival policy.

    Different controllers, identical observation contract, identical initial
    conditions and rival policy. Failures are retained, never dropped.
    """
    from .simulation.rivals import REACTIVE_POLICIES

    factories: dict[str, Any] = {
        "reference": lambda runner, s: ReferenceController(),
        "stationary": lambda runner, s: StationaryPlanner(runner.terminal_value, 2, 200),
        "posterior_mean": lambda runner, s: PosteriorMeanPlanner(runner.terminal_value, 0.5),
        "convex": lambda runner, s: ConvexPlannerController(
            ConditionalConvexPlanner(
                runner.track, runner.vehicle, runner.battery, runner.terminal_value,
                PlannerConfig(),
            )
        ),
        "ambiguity_aware": lambda runner, s: AmbiguityAwareController(
            runner.terminal_value, RivalBelief.uniform(), horizon=3, iterations=300, seed=s
        ),
        "ambiguity_aware_convex": lambda runner, s: AmbiguityAwareController(
            runner.terminal_value, RivalBelief.uniform(), horizon=3, iterations=300,
            planner=ConditionalConvexPlanner(
                runner.track, runner.vehicle, runner.battery, runner.terminal_value,
                PlannerConfig(),
            ),
            seed=s,
        ),
        "ambiguity_aware_hmm": lambda runner, s: AmbiguityAwareController(
            runner.terminal_value, HMMBelief(HMMConfig(stationary=False)),
            horizon=3, iterations=300, seed=s,
        ),
        "ambiguity_aware_hmm_stationary": lambda runner, s: AmbiguityAwareController(
            runner.terminal_value, HMMBelief(HMMConfig(stationary=True)),
            horizon=3, iterations=300, seed=s,
        ),
    }
    rows: list[dict[str, Any]] = []
    for controller_name, factory in factories.items():
        for policy in REACTIVE_POLICIES:
            runner = _build_runner(data)  # fresh runner and fresh controller state
            controller = factory(runner, seed)
            report = runner.run(controller, rival_policy=policy, seed=seed)
            rows.append(
                {
                    "controller": controller_name,
                    "rival_policy": policy.value,
                    **report.summary(),
                }
            )
    return rows


if __name__ == "__main__":
    sys.exit(main())
