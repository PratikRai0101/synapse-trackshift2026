"""Backtest the Race Engineer's recommendations on real race telemetry.

This is the evidence layer: instead of asserting the decision policy is good, we
replay a race and measure whether its ATTACK calls actually *convert*.

Why gap-closure and not overtake labels? The replay's position field is noisy
(derived orderings jitter, and the cached data has artifacts), so labelling
"overtakes" gives unreliable ground truth. Gap-to-car-ahead is a continuous,
trustworthy signal and is the direct prerequisite for a pass: you cannot
overtake without first closing.

Definition of a **conversion**: for a driver within a second of the car ahead,
the gap either (a) falls to <= ``attempt_gap_s`` (0.3s, effectively alongside)
or (b) shrinks by at least ``close_by_s`` (1.0s) within ``horizon_s``.

Reported metrics:
- ``attack_conversion`` / ``baseline_conversion`` / ``lift``
- ``recall`` = share of all conversions that occurred on ATTACK frames
- ``mean_energy_per_conversion`` = estimated EU deployed per successful ATTACK
- threshold sweep for calibration

Run from the CLI:

    python -m src.intelligence.backtest <telemetry.pkl> [label] [--sweep]
"""

from __future__ import annotations

import pickle
import statistics
import sys
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from .config import DEFAULT_CONFIG, ModelConfig
from .energy import (
    ATTACK_MIN_SCORE,
    MODE_ATTACK,
    MODE_HARVEST,
    MODE_LIFT_COAST,
    EnergyEstimator,
    recommend_deployment_mode,
)
from .overtake import evaluate_overtake_window

SPEED_REF_KPH = 55.56  # metres/second at the ~200 km/h reference speed


def _num(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


@dataclass
class BacktestResult:
    label: str
    horizon_s: float
    attack_min_score: float
    n_driver_samples: int
    n_windows: int
    n_attack: int
    n_baseline: int
    n_harvest: int
    n_conversions: int
    attack_conversion: float
    baseline_conversion: float
    harvest_conversion: float
    lift: float
    recall: float
    mean_closure_attack: float
    mean_closure_baseline: float
    mean_energy_per_conversion: float

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def summary(self) -> str:
        base = (
            "n/a" if self.baseline_conversion <= 0
            else f"{self.baseline_conversion:.1%}"
        )
        lift = "n/a" if self.baseline_conversion <= 0 else f"{self.lift:.1f}x"
        return (
            f"[{self.label}] windows={self.n_windows} ATTACK={self.n_attack} | "
            f"conversion ATTACK={self.attack_conversion:.1%} vs baseline {base} "
            f"-> lift {lift} | HARVEST={self.harvest_conversion:.1%} | "
            f"recall={self.recall:.0%} | energy/conv={self.mean_energy_per_conversion:.1f} EU"
        )


def _sample_race(frames: Sequence[dict], stride: int):
    """Downsample into aligned per-driver arrays plus per-frame track order."""
    codes = sorted({c for f in frames for c in f["drivers"]})
    n = len(frames)
    idxs = list(range(0, n, max(1, stride)))
    out: Dict[str, Dict[str, list]] = {
        c: {k: [] for k in ("t", "lap", "dist", "speed", "throttle", "brake", "drs", "tyre", "in_pit", "present")}
        for c in codes
    }
    last: Dict[str, Optional[dict]] = {c: None for c in codes}
    order: List[List[str]] = []
    times: List[float] = []

    for i in idxs:
        f = frames[i]
        t = _num(f.get("t"))
        times.append(t)
        present: List[str] = []
        for c in codes:
            pos = f["drivers"].get(c)
            if pos is not None:
                last[c] = pos
            elif last[c] is not None:
                pos = last[c]
            d = out[c]
            if pos is None:
                d["t"].append(t); d["lap"].append(1); d["dist"].append(np.nan)
                d["speed"].append(0.0); d["throttle"].append(0.0); d["brake"].append(0.0)
                d["drs"].append(0); d["tyre"].append(0.0); d["in_pit"].append(False); d["present"].append(False)
                continue
            d["t"].append(t)
            d["lap"].append(int(pos.get("lap", 1) or 1))
            d["dist"].append(_num(pos.get("dist")))
            d["speed"].append(_num(pos.get("speed")))
            d["throttle"].append(_num(pos.get("throttle")))
            d["brake"].append(_num(pos.get("brake")))
            d["drs"].append(pos.get("drs", 0))
            d["tyre"].append(_num(pos.get("tyre_life")))
            d["in_pit"].append(bool(pos.get("in_pit", False)))
            d["present"].append(True)
            present.append(c)
        present.sort(key=lambda c: (out[c]["lap"][-1], out[c]["dist"][-1]), reverse=True)
        order.append(present)
    return codes, out, order, times


def run_backtest(
    frames: Sequence[dict],
    *,
    label: str = "race",
    stride: Optional[int] = None,
    horizon_s: float = 8.0,
    attempt_gap_s: float = 0.3,
    close_by_s: float = 1.0,
    attack_min_score: Optional[float] = None,
    total_laps: Optional[int] = None,
    config: Optional[ModelConfig] = None,
) -> BacktestResult:
    base_cfg = config or DEFAULT_CONFIG
    threshold = base_cfg.attack_min_score if attack_min_score is None else float(attack_min_score)
    cfg = replace(base_cfg, attack_min_score=threshold)

    empty = BacktestResult(label, horizon_s, threshold, 0, 0, 0, 0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
    if not frames:
        return empty

    dt = abs(_num(frames[1].get("t")) - _num(frames[0].get("t"))) if len(frames) > 1 else 0.04
    if stride is None:
        stride = max(1, int(round(0.5 / dt))) if dt > 0 else 12

    codes, out, order, times = _sample_race(frames, stride)
    n_samples = len(times)
    step_dt = (times[1] - times[0]) if n_samples > 1 else 0.5
    h = max(1, int(round(horizon_s / step_dt)))

    estimator = EnergyEstimator(config=cfg)
    soc, deploy = {}, {}
    for c in codes:
        d = out[c]
        series = estimator.estimate_arrays(d["t"], d["throttle"], d["brake"], d["speed"], d["lap"])
        soc[c] = series.soc
        deploy[c] = series.deploy

    if total_laps is None:
        max_lap = 0
        for c in codes:
            arr = out[c]["lap"]
            if arr:
                max_lap = max(max_lap, max(int(x) for x in arr))
        total_laps = max_lap or None

    def gap_to_ahead(i: int, code: str):
        """(gap_s, ahead_code) for code at sample i, or (None, None)."""
        present = order[i]
        if code not in present:
            return None, None
        r = present.index(code)
        if r == 0 or not out[code]["present"][i]:
            return None, None
        ahead = present[r - 1]
        if not out[ahead]["present"][i]:
            return None, None
        if out[ahead]["lap"][i] != out[code]["lap"][i]:
            return None, None
        d1, d2 = out[code]["dist"][i], out[ahead]["dist"][i]
        if d1 != d1 or d2 != d2:
            return None, None
        return abs(_num(d2) - _num(d1)) / SPEED_REF_KPH, ahead

    n_driver_samples = 0
    n_windows = 0
    n_attack = n_baseline = n_harvest = 0
    n_conv_attack = n_conv_baseline = n_conv_harvest = 0
    n_conversions = 0
    closure_attack: List[float] = []
    closure_baseline: List[float] = []
    energy_per_conv: List[float] = []

    for i in range(n_samples - h):
        present = order[i]
        for rank, code in enumerate(present):
            if not out[code]["present"][i]:
                continue
            n_driver_samples += 1
            gap_now, ahead = gap_to_ahead(i, code)
            if gap_now is None or gap_now > 1.0:
                continue
            gap_future, ahead_future = gap_to_ahead(i + h, code)
            if gap_future is None or ahead_future != ahead:
                continue
            # Ignore windows interrupted by a pit stop.
            if any(out[code]["in_pit"][i:i + h + 1]):
                continue

            drs = out[code]["drs"][i] in (8, 10, 12, 14)
            laps_remaining = max(0, int(total_laps) - int(out[code]["lap"][i])) if total_laps else None
            sc = evaluate_overtake_window(
                gap_ahead_s=gap_now,
                speed_delta_kmh=_num(out[code]["speed"][i]) - _num(out[ahead]["speed"][i]),
                drs=drs,
                soc=float(soc[code][i]),
                tyre_life=_num(out[code]["tyre"][i]),
                laps_remaining=laps_remaining,
                position=rank + 1,
                config=cfg,
            )
            advice = recommend_deployment_mode(
                soc=float(soc[code][i]),
                gap_ahead_s=gap_now,
                laps_remaining=laps_remaining,
                drs=drs,
                tyre_life=_num(out[code]["tyre"][i]),
                overtake_score=sc.score,
                config=cfg,
            )

            closed = gap_now - gap_future
            converted = (gap_future <= attempt_gap_s) or (closed >= close_by_s)
            n_windows += 1
            n_conversions += int(converted)

            if advice.mode == MODE_ATTACK and sc.score >= threshold:
                n_attack += 1
                n_conv_attack += int(converted)
                closure_attack.append(closed)
                if converted:
                    seg = deploy[code][i:i + h]
                    energy_per_conv.append(float(np.nansum(seg) * step_dt))
            elif advice.mode in (MODE_HARVEST, MODE_LIFT_COAST):
                n_harvest += 1
                n_conv_harvest += int(converted)
            else:
                n_baseline += 1
                n_conv_baseline += int(converted)
                closure_baseline.append(closed)

    attack_conversion = n_conv_attack / n_attack if n_attack else 0.0
    baseline_conversion = n_conv_baseline / n_baseline if n_baseline else 0.0
    harvest_conversion = n_conv_harvest / n_harvest if n_harvest else 0.0
    lift = attack_conversion / baseline_conversion if baseline_conversion > 0 else 0.0
    recall = n_conv_attack / n_conversions if n_conversions else 0.0

    return BacktestResult(
        label=label,
        horizon_s=horizon_s,
        attack_min_score=threshold,
        n_driver_samples=n_driver_samples,
        n_windows=n_windows,
        n_attack=n_attack,
        n_baseline=n_baseline,
        n_harvest=n_harvest,
        n_conversions=n_conversions,
        attack_conversion=attack_conversion,
        baseline_conversion=baseline_conversion,
        harvest_conversion=harvest_conversion,
        lift=lift,
        recall=recall,
        mean_closure_attack=(statistics.mean(closure_attack) if closure_attack else 0.0),
        mean_closure_baseline=(statistics.mean(closure_baseline) if closure_baseline else 0.0),
        mean_energy_per_conversion=(statistics.mean(energy_per_conv) if energy_per_conv else 0.0),
    )


def sweep_thresholds(
    frames: Sequence[dict],
    thresholds: Sequence[float] = (-20.0, -10.0, 0.0, 10.0, 20.0, 35.0, 50.0),
    **kwargs,
) -> List[BacktestResult]:
    return [run_backtest(frames, attack_min_score=t, **kwargs) for t in thresholds]


def select_operating_point(
    results: Sequence[BacktestResult],
    *,
    min_recall: float = 0.8,
    objective: str = "lift",
) -> Optional[BacktestResult]:
    """Pick the best result by ``objective`` subject to a recall floor."""
    candidates = [r for r in results if r.recall >= min_recall] or list(results)
    if not candidates:
        return None
    return max(candidates, key=lambda r: (getattr(r, objective, 0.0), r.recall))


def calibrate(
    frames: Sequence[dict],
    *,
    thresholds: Sequence[float] = (-20.0, -10.0, 0.0, 10.0, 20.0, 35.0, 50.0),
    min_recall: float = 0.8,
    objective: str = "lift",
    config: Optional[ModelConfig] = None,
    **kwargs,
):
    """Sweep the ATTACK threshold; return ``(best, best_config, all_results)``.

    The returned config has ``attack_min_score`` set to the winning threshold so
    it can be saved and picked up by the app.
    """
    base = config or DEFAULT_CONFIG
    results = sweep_thresholds(frames, thresholds=thresholds, config=base, **kwargs)
    best = select_operating_point(results, min_recall=min_recall, objective=objective)
    best_cfg = replace(base, attack_min_score=float(best.attack_min_score)) if best else base
    return best, best_cfg, results


def main(argv: Optional[List[str]] = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print("usage: python -m src.intelligence.backtest <telemetry.pkl> [label] [--sweep]")
        return 2
    path = argv[0]
    label = argv[1] if len(argv) > 1 and not argv[1].startswith("--") else path.split("/")[-1]
    with open(path, "rb") as fh:
        data = pickle.load(fh)
    frames = data["frames"]
    total_laps = data.get("total_laps")

    if "--sweep" in argv:
        for r in sweep_thresholds(frames, label=label, total_laps=total_laps):
            print(r.summary())
        return 0

    print(run_backtest(frames, label=label, total_laps=total_laps).summary())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
