"""Causal lap-level feature extraction from cached replay frames."""
from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable, Mapping

from .lap_strategy import LapTimeSample


def extract_lap_samples(frames: Iterable[Mapping[str, Any]], driver: str,
                        mass_kg: float = 800.0,
                        track_baseline_s: float = 90.0) -> list[LapTimeSample]:
    """Extract one sample per completed lap for one driver.

    FastF1 replay frames expose no fuel mass or battery channel. Fuel and
    battery deployment are therefore transparent proxies derived from pedal,
    speed and elapsed time; the output is suitable for fitting a baseline map,
    not for claiming measured energy usage.
    """
    laps: dict[int, list[Mapping[str, Any]]] = defaultdict(list)
    for frame in frames:
        row = (frame.get("drivers", {}) or {}).get(driver)
        if row is None:
            continue
        lap = int(row.get("lap", 0) or 0)
        if lap > 0:
            laps[lap].append({"t": float(frame.get("t", 0.0)), **row})

    samples: list[LapTimeSample] = []
    for lap in sorted(laps):
        rows = sorted(laps[lap], key=lambda row: row["t"])
        if len(rows) < 2:
            continue
        lap_time = rows[-1]["t"] - rows[0]["t"]
        if lap_time <= 0.0:
            continue
        deployed = 0.0
        fuel_proxy = 0.0
        for previous, current in zip(rows, rows[1:]):
            dt = max(0.0, current["t"] - previous["t"])
            throttle = max(0.0, min(100.0, float(current.get("throttle", 0.0))))
            speed = float(current.get("speed", 0.0))
            if throttle >= 80.0 and speed >= 70.0:
                deployed += ((throttle - 80.0) / 20.0) * 1.2 * dt
            fuel_proxy += (throttle / 100.0) * dt
        tyre_wear = float(rows[-1].get("tyre_life", 0.0) or 0.0)
        samples.append(LapTimeSample(
            lap_time_s=lap_time,
            battery_deployed=deployed,
            fuel_deployed=fuel_proxy,
            tyre_wear=tyre_wear,
            mass_kg=mass_kg,
            track_baseline_s=track_baseline_s,
        ))
    return samples
