#!/usr/bin/env python3
"""Evaluate ERS-mode classification on labelled JSONL data."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

try:
    import _bootstrap  # noqa: F401  (adds project root to sys.path)
except ImportError:  # imported as ``scripts.<name>`` by the test suite
    from . import _bootstrap  # noqa: F401
from src.intelligence.hierarchical import FortyStateHMM, RivalTelemetry


def evaluate(dataset: Path, artifact: Path | None = None):
    models = {}
    confusion = defaultdict(lambda: defaultdict(int))
    total = correct = 0
    # The tactically critical pair. Confusing H with M is a mild energy
    # mispricing; confusing a harvest trap with a genuine derate is what makes
    # the controller attack a car that is deliberately holding energy back.
    critical_total = critical_wrong = 0
    critical_labels = {"Lharvest", "Lderate"}
    with dataset.open() as source:
        for line in source:
            line = line.strip()
            if not line:
                continue
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
            if actual in critical_labels:
                critical_total += 1
                # Count only the dangerous swap; picking H or M here is a
                # separate (and less costly) weakness.
                if predicted in critical_labels and predicted != actual:
                    critical_wrong += 1
    return {
        "accuracy": correct / total if total else 0.0,
        "samples": total,
        "harvest_vs_derate_accuracy": (
            1.0 - critical_wrong / critical_total if critical_total else 0.0
        ),
        "harvest_vs_derate_samples": critical_total,
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
