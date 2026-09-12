#!/usr/bin/env python3
"""Fit initial ERS emission means from labelled sector JSONL records.

Records must contain ``ers_mode`` (H, M, Lharvest, or Lderate). This is intended
for simulator-labelled data or human-reviewed annotations, not unlabeled public
race data. The output can be passed to ``FortyStateHMM(emission_means=...)``.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

try:
    import _bootstrap  # noqa: F401  (adds project root to sys.path)
except ImportError:  # imported as ``scripts.<name>`` by the test suite
    from . import _bootstrap  # noqa: F401
from src.intelligence.hierarchical import FeatureExtractor, RivalTelemetry, ERSMode

#: Features the emission model uses, in a fixed order.
FEATURES = ("dgap", "throttle_clip", "brake_delta")


def _feature_vector(features) -> tuple:
    return (features.dgap, features.throttle_clip, features.brake_delta)


def fit(path: Path):
    """Fit per-mode feature means and a pooled diagonal scale per feature.

    The scale matters as much as the means: with a single hard-coded sigma the
    Gaussian is far too flat to separate modes, and the filter degenerates
    toward the prior. Pooled within-mode standard deviation is the simple,
    defensible estimate of how much each feature varies inside a mode.
    """
    counts = defaultdict(int)
    sums = defaultdict(lambda: [0.0, 0.0, 0.0])
    sumsq = defaultdict(lambda: [0.0, 0.0, 0.0])
    extractors = {}
    with path.open() as source:
        for line in source:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            label = record.get("ers_mode")
            if label not in {mode.value for mode in ERSMode}:
                continue
            # One feature extractor per event: baselines must not mix events.
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
            counts[label] += 1
            for i, value in enumerate(_feature_vector(features)):
                sums[label][i] += value
                sumsq[label][i] += value * value

    means = {}
    for label, count in counts.items():
        if not count:
            continue
        mean = [sums[label][i] / count for i in range(len(FEATURES))]
        variance = [max(0.0, sumsq[label][i] / count - mean[i] ** 2)
                    for i in range(len(FEATURES))]
        means[label] = {name: mean[i] for i, name in enumerate(FEATURES)}
        means[label]["samples"] = count
        means[label]["variance"] = {name: variance[i] for i, name in enumerate(FEATURES)}

    # Pool within-mode variance into one scale per feature. A variance floor
    # keeps a feature that never varies in the labels from becoming a
    # zero-width spike that would hard-collapse the posterior.
    pooled = {}
    for i, name in enumerate(FEATURES):
        total = sum(counts[label] for label in means)
        accumulator = 0.0
        for label in means:
            accumulator += means[label]["variance"][name] * counts[label]
        variance = accumulator / total if total else 0.0
        pooled[name] = math.sqrt(max(variance, 1e-6))

    clean_means = {label: {name: values[name] for name in FEATURES}
                   for label, values in means.items()}
    return clean_means, pooled, counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    means, sigma, counts = fit(args.dataset)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({
        "schema": "hmm-emissions.v2",
        "means": means,
        "sigma": sigma,
        "counts": counts,
    }, indent=2, sort_keys=True) + "\n")
    print(f"fit {sum(counts.values())} labelled observations; "
          f"sigma={ {k: round(v, 4) for k, v in sigma.items()} }")


if __name__ == "__main__":
    main()
