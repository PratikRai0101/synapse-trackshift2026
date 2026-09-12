"""Level 3 race strategy: empirical lap-time map and energy allocation.

This is the transparent baseline for the proposed neural lap-time map. It uses
observed lap samples and interpolation-friendly bins, then solves a small finite
horizon dynamic program over deployable energy. The interface is intentionally
compatible with replacing ``LapTimeMap.predict`` with a trained neural model.
"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence


@dataclass(frozen=True)
class LapTimeSample:
    lap_time_s: float
    battery_deployed: float
    fuel_deployed: float = 0.0
    tyre_wear: float = 0.0
    mass_kg: float = 800.0
    track_baseline_s: float = 90.0


@dataclass(frozen=True)
class LapTarget:
    lap_index: int
    deploy_energy: float
    target_lap_time_s: float
    reserve_after_lap: float


class LapTimeMap:
    """Binned empirical surrogate for ``T_lap(ΔEb, ΔEf, wear, mass)``."""

    def __init__(self, bin_width: float = 5.0) -> None:
        self.bin_width = max(1e-6, float(bin_width))
        self._buckets: dict[tuple[int, int, int, int], list[float]] = defaultdict(list)
        self._global: list[float] = []

    def _key(self, sample: LapTimeSample) -> tuple[int, int, int, int]:
        return (
            round(sample.battery_deployed / self.bin_width),
            round(sample.fuel_deployed / self.bin_width),
            round(sample.tyre_wear / max(self.bin_width, 1.0)),
            round(sample.mass_kg / 10.0),
            round(sample.track_baseline_s / self.bin_width),
        )

    def fit(self, samples: Iterable[LapTimeSample]) -> "LapTimeMap":
        self._buckets.clear()
        self._global.clear()
        for sample in samples:
            if sample.lap_time_s <= 0.0:
                continue
            self._buckets[self._key(sample)].append(float(sample.lap_time_s))
            self._global.append(float(sample.lap_time_s))
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "empirical-lap-time-map.v1",
            "bin_width": self.bin_width,
            "buckets": [
                {"key": list(key), "values": values}
                for key, values in self._buckets.items()
            ],
            "global": self._global,
        }

    def save(self, path: str) -> str:
        import json
        with open(path, "w") as destination:
            json.dump(self.to_dict(), destination, indent=2)
        return path

    @classmethod
    def from_file(cls, path: str) -> "LapTimeMap":
        import json
        with open(path) as source:
            return cls.from_dict(json.load(source))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "LapTimeMap":
        result = cls(bin_width=float(data.get("bin_width", 5.0)))
        result._global = [float(value) for value in data.get("global", [])]
        for bucket in data.get("buckets", []):
            key = tuple(int(value) for value in bucket["key"])
            result._buckets[key] = [float(value) for value in bucket["values"]]
        return result

    @property
    def fitted(self) -> bool:
        return bool(self._global)

    def predict(self, sample: LapTimeSample) -> float:
        if not self._global:
            raise RuntimeError("lap-time map has not been fitted")
        values = self._buckets.get(self._key(sample))
        if values:
            return sum(values) / len(values)
        # Transparent fallback: nearest bucket by normalized feature distance.
        key = self._key(sample)
        nearest = min(self._buckets, key=lambda candidate: sum(
            (a - b) ** 2 for a, b in zip(key, candidate)))
        values = self._buckets[nearest]
        return sum(values) / len(values)


@dataclass(frozen=True)
class StrategyConfig:
    lap_count: int = 5
    energy_step: float = 5.0
    minimum_reserve: float = 5.0
    wear_time_penalty: float = 0.15
    energy_time_gain: float = 0.04
    soh_energy_floor: float = 0.60
    resistance_time_penalty: float = 0.20


class RaceEnergyPlanner:
    """Finite-horizon DP that allocates battery energy lap by lap."""

    def __init__(self, lap_map: LapTimeMap, config: StrategyConfig | None = None) -> None:
        self.lap_map = lap_map
        self.config = config or StrategyConfig()

    def plan(self, initial_energy: float, tyre_wear: float = 0.0,
             mass_kg: float = 800.0, battery_soh: float = 1.0,
             wear_cost: float = 0.0) -> tuple[LapTarget, ...]:
        if not self.lap_map.fitted:
            raise RuntimeError("lap-time map has not been fitted")
        cfg = self.config
        step = max(1e-6, cfg.energy_step)
        soh = max(cfg.soh_energy_floor, min(1.0, float(battery_soh)))
        usable_energy = initial_energy * soh
        resistance_penalty = (1.0 - soh) * cfg.resistance_time_penalty
        energy_units = max(0, int(math.floor(usable_energy / step)))
        # DP value is remaining race time; store chosen action for reconstruction.
        values: dict[tuple[int, int], float] = {}
        actions: dict[tuple[int, int], float] = {}
        for lap in range(cfg.lap_count, -1, -1):
            for remaining in range(energy_units + 1):
                if lap == cfg.lap_count:
                    values[(lap, remaining)] = 0.0
                    continue
                available = remaining * step
                candidates = []
                for deployed in range(0, remaining + 1):
                    energy = deployed * step
                    reserve = available - energy
                    if reserve < cfg.minimum_reserve and lap < cfg.lap_count - 1:
                        continue
                    sample = LapTimeSample(
                        lap_time_s=1.0,
                        battery_deployed=energy,
                        tyre_wear=tyre_wear + lap,
                        mass_kg=mass_kg,
                    )
                    base = self.lap_map.predict(sample)
                    lap_time = base - cfg.energy_time_gain * energy
                    lap_time += cfg.wear_time_penalty * (tyre_wear + lap)
                    lap_time += wear_cost + resistance_penalty
                    next_units = int(round(reserve / step))
                    score = lap_time + values[(lap + 1, next_units)]
                    candidates.append((score, energy))
                if candidates:
                    score, energy = min(candidates)
                    values[(lap, remaining)] = score
                    actions[(lap, remaining)] = energy
        targets = []
        remaining = energy_units
        for lap in range(cfg.lap_count):
            energy = actions.get((lap, remaining), 0.0)
            reserve = remaining * step - energy
            predicted = self.lap_map.predict(LapTimeSample(
                lap_time_s=1.0, battery_deployed=energy,
                tyre_wear=tyre_wear + lap, mass_kg=mass_kg))
            targets.append(LapTarget(lap + 1, energy, predicted - cfg.energy_time_gain * energy,
                                     reserve))
            remaining = max(0, int(round(reserve / step)))
        return tuple(targets)
