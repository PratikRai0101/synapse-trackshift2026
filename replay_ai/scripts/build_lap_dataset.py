#!/usr/bin/env python3
"""Build event-partitioned lap-time datasets from replay telemetry pickles."""
from __future__ import annotations

import argparse
import json
import pickle
from pathlib import Path

try:
    import _bootstrap  # noqa: F401
except ImportError:
    from . import _bootstrap  # noqa: F401

from scripts.build_dataset import event_split
from src.intelligence.lap_dataset import extract_lap_samples


def build(inputs, driver: str, output: Path, mass_kg: float = 800.0):
    output.mkdir(parents=True, exist_ok=True)
    handles = {split: (output / f"{split}.jsonl").open("w")
               for split in ("train", "validation", "test")}
    counts = {split: 0 for split in handles}
    events = {split: set() for split in handles}
    try:
        for event, path in inputs:
            with Path(path).open("rb") as source:
                data = pickle.load(source)
            frames = data.get("frames", data) if isinstance(data, dict) else data
            split = event_split(event)
            events[split].add(event)
            for lap, sample in enumerate(extract_lap_samples(frames, driver, mass_kg), 1):
                record = {
                    "schema": "lap-time-sample.v1",
                    "event": event,
                    "split": split,
                    "driver": driver,
                    "lap": lap,
                    "lap_time_s": sample.lap_time_s,
                    "battery_deployed": sample.battery_deployed,
                    "fuel_deployed": sample.fuel_deployed,
                    "tyre_wear": sample.tyre_wear,
                    "mass_kg": sample.mass_kg,
                }
                handles[split].write(json.dumps(record, separators=(",", ":")) + "\n")
                counts[split] += 1
    finally:
        for handle in handles.values():
            handle.close()
    manifest = {"schema": "lap-dataset.v1", "driver": driver,
                "event_counts": {split: len(values) for split, values in events.items()},
                "row_counts": counts}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", action="append", required=True, metavar="EVENT=PKL")
    parser.add_argument("--driver", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mass-kg", type=float, default=800.0)
    args = parser.parse_args()
    inputs = []
    for item in args.input:
        event, separator, path = item.partition("=")
        if not separator or not event or not path:
            parser.error(f"invalid --input {item!r}; expected EVENT=PKL")
        inputs.append((event, path))
    print(json.dumps(build(inputs, args.driver, args.output, args.mass_kg), indent=2))


if __name__ == "__main__":
    main()
