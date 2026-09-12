#!/usr/bin/env python3
"""Extract lap-level Level 3 samples from a computed telemetry pickle."""
from __future__ import annotations

import argparse
import json
import pickle
from pathlib import Path

try:
    import _bootstrap  # noqa: F401
except ImportError:
    from . import _bootstrap  # noqa: F401

from src.intelligence.lap_dataset import extract_lap_samples


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pickle_path", type=Path)
    parser.add_argument("--driver", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mass-kg", type=float, default=800.0)
    parser.add_argument("--track-baseline-s", type=float, default=90.0)
    args = parser.parse_args()
    with args.pickle_path.open("rb") as source:
        data = pickle.load(source)
    frames = data.get("frames", data) if isinstance(data, dict) else data
    samples = extract_lap_samples(frames, args.driver, args.mass_kg,
                                   args.track_baseline_s)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w") as destination:
        for index, sample in enumerate(samples, 1):
            destination.write(json.dumps({
                "schema": "lap-time-sample.v1",
                "driver": args.driver,
                "lap": index,
                "lap_time_s": sample.lap_time_s,
                "battery_deployed": sample.battery_deployed,
                "fuel_deployed": sample.fuel_deployed,
                "tyre_wear": sample.tyre_wear,
                "mass_kg": sample.mass_kg,
                "track_baseline_s": sample.track_baseline_s,
            }, separators=(",", ":")) + "\n")
    print(f"extracted {len(samples)} lap samples to {args.output}")


if __name__ == "__main__":
    main()
