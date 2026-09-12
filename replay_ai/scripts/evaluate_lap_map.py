#!/usr/bin/env python3
"""Fit a lap-time map on train races and score held-out races."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    import _bootstrap  # noqa: F401
except ImportError:
    from . import _bootstrap  # noqa: F401

from src.intelligence.lap_strategy import LapTimeMap, LapTimeSample


def _samples(path: Path):
    with path.open() as source:
        for line in source:
            if line.strip():
                row = json.loads(line)
                yield row, LapTimeSample(
                    lap_time_s=float(row["lap_time_s"]),
                    battery_deployed=float(row.get("battery_deployed", 0.0)),
                    fuel_deployed=float(row.get("fuel_deployed", 0.0)),
                    tyre_wear=float(row.get("tyre_wear", 0.0)),
                    mass_kg=float(row.get("mass_kg", 800.0)),
                )


def evaluate(dataset_dir: Path) -> dict:
    train = list(_samples(dataset_dir / "train.jsonl"))
    lap_map = LapTimeMap().fit(sample for _, sample in train)
    reports = {}
    for split in ("train", "validation", "test"):
        rows = list(_samples(dataset_dir / f"{split}.jsonl"))
        errors = [abs(lap_map.predict(sample) - sample.lap_time_s)
                  for _, sample in rows] if rows else []
        reports[split] = {
            "samples": len(rows),
            "mae_s": sum(errors) / len(errors) if errors else None,
            "max_error_s": max(errors) if errors else None,
        }
    return {"schema": "lap-map-evaluation.v1", "reports": reports}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = evaluate(args.dataset)
    text = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
