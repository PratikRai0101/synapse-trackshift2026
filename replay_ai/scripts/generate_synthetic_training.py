#!/usr/bin/env python3
"""Generate labelled sector observations for HMM development.

This is a calibration fixture, not race evidence. Hidden ERS modes are known
because this generator acts as the synthetic rival simulator.
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

MODES = ("H", "M", "Lharvest", "Lderate")


def generate(events: int, samples_per_event: int, seed: int):
    rng = random.Random(seed)
    for event_index in range(events):
        event = f"synthetic-{event_index:03d}"
        mode = rng.choice(MODES)
        speed = 285.0
        gap = 1.5
        for sample in range(samples_per_event):
            if rng.random() < 0.08:
                mode = rng.choice(MODES)
            means = {
                "H": (0.10, 0.0), "M": (0.03, 0.05),
                "Lharvest": (-0.05, 0.08), "Lderate": (0.16, 0.55),
            }
            closure, clip = means[mode]
            gap = max(0.05, gap - closure + rng.gauss(0.0, 0.025))
            speed += rng.gauss(0.0, 1.5)
            throttle = 99.5 if rng.random() < clip else rng.uniform(75.0, 97.0)
            brake = 1.0 if rng.random() < (0.18 if sample % 8 == 0 else 0.02) else 0.0
            yield {
                "schema": "public-telemetry.v1",
                "event": event,
                "timestamp_s": sample * 0.8,
                "available_at_s": sample * 0.8,
                "driver": "EGO",
                "rival": "SYN",
                "lap": sample // 20 + 1,
                "sector": sample % 3,
                "speed_kmh": round(speed, 3),
                "throttle_pct": round(throttle, 3),
                "brake": brake,
                "gap_s": round(gap, 4),
                "active_aero": 1.0 if sample % 3 == 0 else 0.0,
                "tyre_life": float(sample // 20),
                "ers_mode": mode,
                "synthetic_label": True,
            }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=int, default=20)
    parser.add_argument("--samples-per-event", type=int, default=100)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with args.output.open("w") as destination:
        for record in generate(args.events, args.samples_per_event, args.seed):
            destination.write(json.dumps(record, separators=(",", ":")) + "\n")
            count += 1
    print(f"generated {count} synthetic labelled observations")


if __name__ == "__main__":
    main()
