"""Calibrate the AI Motorsport Intelligence model against a cached race.

Runs the backtest at several ATTACK-score thresholds, prints the sweep, picks an
operating point (best lift subject to a recall floor) and writes the resulting
config to ``computed_data/model_config.json``. The app loads that file on
startup, so calibrated parameters take effect automatically.

    python scripts/calibrate_model.py "computed_data/<race>.pkl" [--min-recall 0.85]
"""

from __future__ import annotations

import logging
import os
import pickle
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.disable(logging.CRITICAL)

from src.intelligence.backtest import calibrate  # noqa: E402
from src.intelligence.config import DEFAULT_CONFIG, DEFAULT_CONFIG_PATH  # noqa: E402


def main(argv) -> int:
    args = [a for a in argv if not a.startswith("--")]
    if not args:
        print(__doc__)
        return 2
    path = args[0]

    min_recall = 0.8
    if "--min-recall" in argv:
        try:
            min_recall = float(argv[argv.index("--min-recall") + 1])
        except (IndexError, ValueError):
            pass

    with open(path, "rb") as fh:
        data = pickle.load(fh)

    best, cfg, results = calibrate(
        data["frames"],
        min_recall=min_recall,
        config=DEFAULT_CONFIG,
        total_laps=data.get("total_laps"),
    )

    print(f"{'threshold':>9} | {'attack-time':>11} | {'conversion':>10} | "
          f"{'baseline':>8} | {'lift':>6} | {'recall':>6} | {'attacks':>8}")
    print("-" * 78)
    for r in results:
        attack_time = (r.n_attack / r.n_driver_samples) if r.n_driver_samples else 0.0
        print(f"{r.attack_min_score:>9.0f} | {attack_time:>10.0%} | "
              f"{r.attack_conversion:>9.1%} | {r.baseline_conversion:>7.1%} | "
              f"{r.lift:>6.1f} | {r.recall:>5.0%} | {r.n_attack:>8}")

    if best is None:
        print("no calibration result")
        return 1

    print("-" * 78)
    print(f"chosen: attack_min_score={cfg.attack_min_score:.0f}  "
          f"(lift {best.lift:.1f}x, recall {best.recall:.0%}, min_recall={min_recall:.0%})")
    saved = cfg.save()
    print(f"saved  : {saved}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
