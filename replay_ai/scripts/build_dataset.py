#!/usr/bin/env python3
"""Build leakage-safe train/validation/test JSONL files from replay pickles.

Example:
  python scripts/build_dataset.py \
    --input bahrain=cache/bahrain.pkl --input monaco=cache/monaco.pkl \
    --driver HAM --rival VER --output data/ers

Splitting is by event, never by individual rows, so adjacent sectors from one
race cannot leak across evaluation sets.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pickle
from io import StringIO
from pathlib import Path
from typing import Dict

try:
    import _bootstrap  # noqa: F401  (adds project root + scripts to sys.path)
except ImportError:  # imported as part of the scripts package
    from . import _bootstrap  # noqa: F401

try:
    from scripts.export_training_data import export_frames
except ImportError:  # direct execution from the scripts directory
    from export_training_data import export_frames


def event_split(event: str) -> str:
    # Stable across machines and Python processes.
    bucket = int(hashlib.sha256(event.encode()).hexdigest()[:8], 16) % 10
    return "test" if bucket == 0 else ("validation" if bucket in (1, 2) else "train")


def build_dataset(inputs, driver: str, rival: str, output: Path,
                  stride: int, track_length_m: float | None) -> Dict[str, int]:
    output.mkdir(parents=True, exist_ok=True)
    handles = {split: (output / f"{split}.jsonl").open("w")
               for split in ("train", "validation", "test")}
    counts = {split: 0 for split in handles}
    try:
        for event, path in inputs:
            with Path(path).open("rb") as source:
                data = pickle.load(source)
            frames = data.get("frames", data) if isinstance(data, dict) else data
            buffer = StringIO()
            export_frames(frames, driver, rival, buffer, stride, track_length_m)
            split = event_split(event)
            for line in buffer.getvalue().splitlines():
                record = json.loads(line)
                record["event"] = event
                record["split"] = split
                handles[split].write(json.dumps(record, separators=(",", ":")) + "\n")
                counts[split] += 1
    finally:
        for handle in handles.values():
            handle.close()
    manifest = {
        "schema": "public-telemetry-dataset.v1",
        "driver": driver,
        "rival": rival,
        "events": [event for event, _ in inputs],
        "counts": counts,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", action="append", required=True,
                        metavar="EVENT=PKL", help="repeat once per race/event")
    parser.add_argument("--driver", required=True)
    parser.add_argument("--rival", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stride", type=int, default=25)
    parser.add_argument("--track-length-m", type=float, default=None)
    args = parser.parse_args()
    inputs = []
    for item in args.input:
        event, separator, path = item.partition("=")
        if not separator or not event or not path:
            parser.error(f"invalid --input {item!r}; expected EVENT=PKL")
        inputs.append((event, path))
    counts = build_dataset(inputs, args.driver, args.rival, args.output,
                           args.stride, args.track_length_m)
    print(json.dumps(counts, sort_keys=True))


if __name__ == "__main__":
    main()
