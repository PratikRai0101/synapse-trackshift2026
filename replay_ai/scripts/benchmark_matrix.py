#!/usr/bin/env python3
"""Run paired multi-seed controller benchmarks with 95% intervals."""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

try:
    import _bootstrap  # noqa: F401
except ImportError:
    from . import _bootstrap

from src.intelligence.closed_loop import ClosedLoopSimulator, HiddenRivalMode


CONTROLLERS = ("full", "no_mpc", "no_search", "no_soh", "no_spatial")
SCENARIOS = ("nominal", "energy_stress", "thermal_stress")


def episode(controller: str, mode: HiddenRivalMode, scenario: str,
            seed: int, steps: int) -> dict:
    simulator = ClosedLoopSimulator(
        mode, seed=seed,
        use_mpc=controller != "no_mpc",
        controller_variant=controller,
        scenario=scenario,
    )
    trace = simulator.run(steps)
    burns = sum(step.decision.command == "BURN" for step in trace)
    return {
        "controller": controller,
        "rival_mode": mode.value,
        "scenario": scenario,
        "seed": seed,
        "final_gap_s": simulator.ego.gap_s,
        "energy_used": 70.0 - simulator.ego.energy,
        "burn_steps": burns,
        "completed": len(trace) == steps,
    }


def _summary(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "mean": None, "std": None, "ci95": None}
    mean = sum(values) / len(values)
    if len(values) > 1:
        variance = sum((value - mean) ** 2 for value in values) / (len(values) - 1)
        std = math.sqrt(variance)
        ci = 1.96 * std / math.sqrt(len(values))
    else:
        std, ci = 0.0, 0.0
    return {"n": len(values), "mean": mean, "std": std, "ci95": ci}


def benchmark(seeds: list[int], steps: int = 100) -> dict:
    rows = [episode(controller, mode, scenario, seed, steps)
            for seed in seeds
            for mode in HiddenRivalMode
            for scenario in SCENARIOS
            for controller in CONTROLLERS]
    grouped = defaultdict(list)
    for row in rows:
        key = (row["controller"], row["rival_mode"], row["scenario"])
        grouped[key].append(row)
    summaries = {}
    for key, group in grouped.items():
        summaries[f"{key[0]}:{key[1]}:{key[2]}"] = {
            "gap_s": _summary([row["final_gap_s"] for row in group]),
            "energy_used": _summary([row["energy_used"] for row in group]),
            "burn_steps": _summary([row["burn_steps"] for row in group]),
            "completion_rate": sum(row["completed"] for row in group) / len(group),
        }
    return {"schema": "paired-benchmark.v1", "seeds": seeds,
            "steps": steps, "summaries": summaries, "episodes": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=10)
    parser.add_argument("--steps", type=int, default=100)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = benchmark(list(range(args.seeds)), args.steps)
    text = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
