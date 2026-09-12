#!/usr/bin/env python3
"""Evaluate ERS-mode classification on labelled JSONL data."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from src.intelligence.hierarchical import FortyStateHMM, RivalTelemetry


def evaluate(dataset: Path, artifact: Path | None = None):
    models = {}
    confusion = defaultdict(lambda: defaultdict(int))
    total = correct = 0
    with dataset.open() as source:
        for line in source:
            record = json.loads(line)
            event = record.get("event", "default")
            if event not in models:
                models[event] = (FortyStateHMM.from_artifact(str(artifact))
                                 if artifact else FortyStateHMM())
            result = models[event].observe(RivalTelemetry(
                speed_kmh=record["speed_kmh"],
                throttle_pct=record["throttle_pct"],
                brake=record["brake"],
                gap_s=record.get("gap_s") or 0.0,
                active_aero=record.get("active_aero", 0.0),
                lap=record.get("lap", 0),
            ))
            actual = record.get("ers_mode")
            if actual not in result.ers_probabilities:
                continue
            predicted = result.estimated_soc_mode
            confusion[actual][predicted] += 1
            correct += predicted == actual
            total += 1
    return {
        "accuracy": correct / total if total else 0.0,
        "samples": total,
        "confusion": {actual: dict(predictions)
                      for actual, predictions in confusion.items()},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--artifact", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = evaluate(args.dataset, args.artifact)
    text = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
