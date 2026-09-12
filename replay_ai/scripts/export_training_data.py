#!/usr/bin/env python3
"""Export causal sector samples from a computed replay telemetry pickle.

Usage:
  python scripts/export_training_data.py computed_data/session_telemetry.pkl \
      --driver HAM --rival VER --output data/ham-ver.jsonl
"""
from __future__ import annotations

import argparse
import json
import pickle
from pathlib import Path
from typing import Iterable, Mapping

try:
    import _bootstrap  # noqa: F401  (adds project root to sys.path)
except ImportError:  # imported as ``scripts.<name>`` by the test suite
    from . import _bootstrap  # noqa: F401
from src.intelligence.telemetry_adapter import PublicTelemetryAdapter


def export_frames(
    frames: Iterable[Mapping], driver: str, rival: str, output, stride: int = 25,
    track_length_m: float | None = None
) -> int:
    adapter = PublicTelemetryAdapter(source="fastf1-replay", track_length_m=track_length_m)
    written = 0
    last_lap = None
    for index, frame in enumerate(frames):
        if index % max(1, stride) and frame.get("lap") == last_lap:
            continue
        drivers = frame.get("drivers", {})
        if driver not in drivers or rival not in drivers:
            continue
        timestamp = float(frame.get("t", index / 25.0))
        record = adapter.from_frame(
            frame, driver, rival, timestamp_s=timestamp, available_at_s=timestamp
        )
        payload = {
            "schema": "public-telemetry.v1",
            "frame_index": index,
            **record.as_dict(),
        }
        output.write(json.dumps(payload, separators=(",", ":")) + "\n")
        written += 1
        last_lap = frame.get("lap")
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pickle_path", type=Path)
    parser.add_argument("--driver", required=True)
    parser.add_argument("--rival", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--stride", type=int, default=25,
                        help="sample every N replay frames (default: 25)")
    parser.add_argument("--track-length-m", type=float, default=None,
                        help="track length for estimating gaps when absent")
    args = parser.parse_args()
    with args.pickle_path.open("rb") as source:
        data = pickle.load(source)
    frames = data.get("frames", data) if isinstance(data, dict) else data
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w") as destination:
        count = export_frames(frames, args.driver, args.rival, destination,
                               args.stride, args.track_length_m)
    print(f"exported {count} public records to {args.output}")


if __name__ == "__main__":
    main()
