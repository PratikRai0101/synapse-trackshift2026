#!/usr/bin/env python3
"""Evaluate lap-time generalization with leave-one-circuit-out splits."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    import _bootstrap  # noqa: F401
except ImportError:
    from . import _bootstrap

from src.intelligence.lap_strategy import LapTimeMap, LapTimeSample


def _sample(row: dict) -> LapTimeSample:
    return LapTimeSample(
        lap_time_s=float(row["lap_time_s"]),
        battery_deployed=float(row.get("battery_deployed", 0.0)),
        fuel_deployed=float(row.get("fuel_deployed", 0.0)),
        tyre_wear=float(row.get("tyre_wear", 0.0)),
        mass_kg=float(row.get("mass_kg", 800.0)),
        track_baseline_s=float(row.get("track_baseline_s", 90.0)),
    )


def _rows(dataset: Path) -> list[dict]:
    paths = sorted(dataset.glob("*.jsonl"))
    result = []
    for path in paths:
        with path.open() as source:
            for line in source:
                if line.strip():
                    row = json.loads(line)
                    # Circuit is required to prevent accidental event leakage.
                    if row.get("circuit"):
                        result.append(row)
    return result


def evaluate(dataset: Path) -> dict:
    rows = _rows(dataset)
    circuits = sorted({str(row["circuit"]) for row in rows})
    reports = {}
    pooled_errors: list[float] = []
    for held_out in circuits:
        train = [_sample(row) for row in rows if str(row["circuit"]) != held_out]
        test = [_sample(row) for row in rows if str(row["circuit"]) == held_out]
        if not train:
            reports[held_out] = {"samples": len(test), "mae_s": None,
                                 "status": "insufficient-training-circuits"}
            continue
        model = LapTimeMap().fit(train)
        errors = [abs(model.predict(sample) - sample.lap_time_s) for sample in test]
        pooled_errors.extend(errors)
        reports[held_out] = {
            "samples": len(test),
            "mae_s": sum(errors) / len(errors) if errors else None,
            "max_error_s": max(errors) if errors else None,
            "status": "evaluated" if errors else "no-held-out-samples",
        }
    return {
        "schema": "circuit-holdout-evaluation.v1",
        "circuits": circuits,
        "circuit_count": len(circuits),
        "pooled_samples": len(pooled_errors),
        "pooled_mae_s": (sum(pooled_errors) / len(pooled_errors)
                          if pooled_errors else None),
        "reports": reports,
        "limitations": [
            "Circuit identifiers must be present in every evaluated row.",
            "This evaluates the empirical map; it is not evidence of real-car transfer.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(args.dataset)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
