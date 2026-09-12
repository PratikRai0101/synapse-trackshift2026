#!/usr/bin/env python3
"""Fit initial ERS emission means from labelled sector JSONL records.

Records must contain ``ers_mode`` (H, M, Lharvest, or Lderate). This is intended
for simulator-labelled data or human-reviewed annotations, not unlabeled public
race data. The output can be passed to ``FortyStateHMM(emission_means=...)``.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from src.intelligence.hierarchical import FeatureExtractor, RivalTelemetry, ERSMode


def fit(path: Path):
    sums = defaultdict(lambda: [0.0, 0.0, 0.0, 0])
    extractors = {}
    with path.open() as source:
        for line in source:
            record = json.loads(line)
            label = record.get("ers_mode")
            if label not in {mode.value for mode in ERSMode}:
                continue
            event = record.get("event", "default")
            extractor = extractors.setdefault(event, FeatureExtractor())
            features = extractor.update(RivalTelemetry(
                speed_kmh=record["speed_kmh"],
                throttle_pct=record["throttle_pct"],
                brake=record["brake"],
                gap_s=record.get("gap_s") or 0.0,
                active_aero=record.get("active_aero", 0.0),
                lap=record.get("lap", 0),
            ))
            bucket = sums[label]
            bucket[0] += features.dgap
            bucket[1] += features.throttle_clip
            bucket[2] += features.brake_delta
            bucket[3] += 1
    means = {}
    for label, (dgap, clip, brake, count) in sums.items():
        if count:
            means[label] = {"dgap": dgap / count,
                            "throttle_clip": clip / count,
                            "brake_delta": brake / count,
                            "samples": count}
    return means


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    means = fit(args.dataset)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"schema": "hmm-emissions.v1", "means": means}, indent=2) + "\n")
    print(f"fit {sum(v['samples'] for v in means.values())} labelled observations")


if __name__ == "__main__":
    main()
