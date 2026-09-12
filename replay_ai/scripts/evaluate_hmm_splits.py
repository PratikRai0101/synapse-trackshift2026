#!/usr/bin/env python3
"""Fit HMM calibration on train events and score validation/test events."""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

try:
    import _bootstrap  # noqa: F401
except ImportError:
    from . import _bootstrap  # noqa: F401

from scripts.build_dataset import event_split
from scripts.evaluate_hmm import evaluate
from scripts.fit_hmm_emissions import fit


def evaluate_splits(dataset: Path) -> dict:
    rows = {"train": [], "validation": [], "test": []}
    events = {split: set() for split in rows}
    with dataset.open() as source:
        for line in source:
            if not line.strip():
                continue
            record = json.loads(line)
            split = record.get("split") or event_split(record.get("event", "default"))
            rows[split].append(record)
            events[split].add(record.get("event", "default"))

    with tempfile.TemporaryDirectory() as directory:
        directory = Path(directory)
        paths = {}
        for split, records in rows.items():
            path = directory / f"{split}.jsonl"
            path.write_text("\n".join(json.dumps(row) for row in records) +
                            ("\n" if records else ""))
            paths[split] = path
        means, sigma, counts, transition = fit(paths["train"])
        artifact = directory / "artifact.json"
        artifact.write_text(json.dumps({
            "schema": "hmm-emissions.v2",
            "means": means,
            "sigma": sigma,
            "counts": counts,
            "transition": transition,
        }))
        reports = {
            split: evaluate(path, artifact) if rows[split] else None
            for split, path in paths.items()
        }
    return {
        "schema": "hmm-split-evaluation.v1",
        "event_counts": {split: len(values) for split, values in events.items()},
        "row_counts": {split: len(values) for split, values in rows.items()},
        "reports": reports,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = evaluate_splits(args.dataset)
    text = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
