#!/usr/bin/env python3
"""Fit and serialize the empirical Level 3 lap-time map."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    import _bootstrap  # noqa: F401
except ImportError:
    from . import _bootstrap  # noqa: F401

from src.intelligence.lap_strategy import LapTimeMap, LapTimeSample


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bin-width", type=float, default=5.0)
    args = parser.parse_args()
    samples = []
    with args.dataset.open() as source:
        for line in source:
            if line.strip():
                row = json.loads(line)
                samples.append(LapTimeSample(
                    lap_time_s=float(row["lap_time_s"]),
                    battery_deployed=float(row.get("battery_deployed", 0.0)),
                    fuel_deployed=float(row.get("fuel_deployed", 0.0)),
                    tyre_wear=float(row.get("tyre_wear", 0.0)),
                    mass_kg=float(row.get("mass_kg", 800.0)),
                ))
    lap_map = LapTimeMap(args.bin_width).fit(samples)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(lap_map.to_dict(), indent=2) + "\n")
    print(f"fit {len(samples)} lap samples into {len(lap_map._buckets)} bins")


if __name__ == "__main__":
    main()
