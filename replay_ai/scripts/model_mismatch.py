#!/usr/bin/env python3
"""Measure controller/simulator mismatch across paired stress episodes."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

try:
    import _bootstrap  # noqa: F401
except ImportError:
    from . import _bootstrap

from src.intelligence.closed_loop import ClosedLoopSimulator, HiddenRivalMode
from src.intelligence.race_physics import DirtyAirModel

SCENARIOS = ("nominal", "energy_stress", "thermal_stress")


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def episode(mode: HiddenRivalMode, scenario: str, seed: int, steps: int) -> dict:
    simulator = ClosedLoopSimulator(mode, scenario=scenario, seed=seed)
    trace = simulator.run(steps)
    target_errors = [abs(step.decision.target_speed_kmh - step.ego_speed_kmh)
                     for step in trace]
    expected = {
        HiddenRivalMode.DEPLETE: {"BURN", "PROACTIVE TRAP"},
        HiddenRivalMode.CONSERVE: {"HARVEST", "PROACTIVE TRAP"},
        HiddenRivalMode.MATCH: {"PROACTIVE TRAP", "BURN", "HARVEST"},
    }[mode]
    aligned = sum(step.decision.command in expected for step in trace) / max(len(trace), 1)
    soh = simulator.battery_soh
    physical_resistance = (1.0 + 0.004 * max(0.0, simulator.battery_temperature - 70.0)
                           + 0.25 * simulator.plant.state.tyre_wear)
    lifecycle_resistance = 1.0 + (1.0 - soh) * 0.4
    return {
        "mode": mode.value,
        "scenario": scenario,
        "seed": seed,
        "speed_target_mae_kmh": _mean(target_errors),
        "decision_alignment": aligned,
        "final_gap_s": simulator.ego.gap_s,
        "final_energy": simulator.ego.energy,
        "final_soh": soh,
        "final_temperature_c": simulator.battery_temperature,
        "physical_resistance": physical_resistance,
        "lifecycle_resistance": lifecycle_resistance,
        "resistance_mismatch": abs(physical_resistance - lifecycle_resistance),
    }


def report(seeds: list[int], steps: int = 300) -> dict:
    rows = [episode(mode, scenario, seed, steps)
            for seed in seeds
            for scenario in SCENARIOS
            for mode in HiddenRivalMode]
    metrics = {
        key: _mean([row[key] for row in rows])
        for key in ("speed_target_mae_kmh", "decision_alignment",
                    "resistance_mismatch")
    }
    return {
        "schema": "model-mismatch.v1",
        "seeds": seeds,
        "steps": steps,
        "metrics": metrics,
        "episodes": rows,
        "limitations": [
            "Rival mode is simulator truth, not public telemetry.",
            "Resistance comparison is a reference-model mismatch, not cell validation.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, default=10)
    parser.add_argument("--steps", type=int, default=300)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = report(list(range(args.seeds)), args.steps)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result["metrics"], indent=2))


if __name__ == "__main__":
    main()
