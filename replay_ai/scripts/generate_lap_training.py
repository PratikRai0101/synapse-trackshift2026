#!/usr/bin/env python3
"""Generate simulator-labelled lap samples for Level 3 model development.

This generator provides hidden battery/fuel truth that public FastF1 telemetry
cannot provide. It is a physics-shaped development fixture, not race evidence.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

try:
    import _bootstrap  # noqa: F401
except ImportError:
    from . import _bootstrap

from scripts.build_dataset import event_split


def generate(events: int, laps_per_event: int, seed: int):
    rng = random.Random(seed)
    for event_index in range(events):
        event = f"sim-race-{event_index:03d}"
        base_time = rng.uniform(78.0, 105.0)
        for lap in range(1, laps_per_event + 1):
            battery = rng.uniform(0.0, 40.0)
            fuel = rng.uniform(0.0, 3.0)
            wear = rng.uniform(0.0, 12.0) + lap * rng.uniform(0.0, 0.15)
            mass = rng.uniform(745.0, 815.0) - fuel * 0.8
            # A transparent surrogate for a simulator's lap-time response.
            lap_time = (base_time - 0.055 * battery - 0.30 * fuel +
                        0.18 * wear + 0.012 * (mass - 780.0) +
                        rng.gauss(0.0, 0.08))
            yield {
                "schema": "lap-time-sample.v1",
                "event": event,
                "split": event_split(event),
                "lap": lap,
                "lap_time_s": round(lap_time, 5),
                "battery_deployed": round(battery, 5),
                "fuel_deployed": round(fuel, 5),
                "tyre_wear": round(wear, 5),
                "mass_kg": round(mass, 5),
                "track_baseline_s": round(base_time, 5),
                "energy_source": "simulator-truth",
                "synthetic_label": True,
            }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=int, default=100)
    parser.add_argument("--laps-per-event", type=int, default=20)
    parser.add_argument("--seed", type=int, default=13)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    handles = {split: (args.output / f"{split}.jsonl").open("w")
               for split in ("train", "validation", "test")}
    counts = {split: 0 for split in handles}
    try:
        for record in generate(args.events, args.laps_per_event, args.seed):
            split = record["split"]
            handles[split].write(json.dumps(record, separators=(",", ":")) + "\n")
            counts[split] += 1
    finally:
        for handle in handles.values():
            handle.close()
    (args.output / "manifest.json").write_text(json.dumps({
        "schema": "simulator-lap-dataset.v1", "counts": counts,
        "events": args.events, "laps_per_event": args.laps_per_event,
    }, indent=2) + "\n")
    print(json.dumps(counts, sort_keys=True))


if __name__ == "__main__":
    main()
