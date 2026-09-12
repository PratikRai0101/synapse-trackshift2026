"""Block 0 — causal feature extraction from the telemetry stream.

Everything here uses only samples up to the current time. The features are
deviations against the rival's **rolling baseline**, which absorbs fuel burn and
track evolution, plus the super-clipping fraction.

Definitions (declared):

- ``super_clipping_fraction`` — proportion of samples where throttle is at
  least ``throttle_threshold`` but speed is below the rolling baseline by more
  than ``speed_tolerance``. Observing reduced speed at full throttle does **not**
  by itself establish that MGU-K recovery caused it; this is a proxy feature
  whose interpretation is the HMM's job, not a measurement of recovery.
- Baselines are means over the last ``window`` completed laps on the same
  sample index, so they do not mix different parts of the circuit.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

import numpy as np


@dataclass
class TelemetrySample:
    time_s: float
    speed_mps: float
    throttle: float
    brake: float
    lap: int
    sector: int
    gap_s: float | None = None


@dataclass
class CausalFeatures:
    speed_delta_mps: float
    sector_time_delta_s: float
    brake_delta: float
    speed_variance: float
    super_clipping_fraction: float
    samples: int

    def as_dict(self) -> dict[str, float | int]:
        return {
            "speed_delta_mps": self.speed_delta_mps,
            "sector_time_delta_s": self.sector_time_delta_s,
            "brake_delta": self.brake_delta,
            "speed_variance": self.speed_variance,
            "super_clipping_fraction": self.super_clipping_fraction,
            "samples": self.samples,
        }


@dataclass
class RollingBaseline:
    """Per-(lap-phase) baseline over the last N completed laps."""

    window: int = 5
    lap_slices: int = 20
    throttle_threshold: float = 0.98
    speed_tolerance_mps: float = 1.0
    _speed: deque = field(default_factory=lambda: deque(maxlen=5))
    _brake: deque = field(default_factory=lambda: deque(maxlen=5))
    _sector_times: deque = field(default_factory=lambda: deque(maxlen=5))
    _current_speed: np.ndarray | None = field(default=None, init=False)
    _current_brake: np.ndarray | None = field(default=None, init=False)
    _current_sector_time: float = field(default=0.0, init=False)
    _current_sector: int = field(default=-1, init=False)
    _super_clipping_samples: int = field(default=0, init=False)
    _total_samples: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self._speed = deque(maxlen=self.window)
        self._brake = deque(maxlen=self.window)
        self._sector_times = deque(maxlen=self.window)

    # -- ingestion ---------------------------------------------------------
    def ingest(self, sample: TelemetrySample, progress_fraction: float) -> CausalFeatures:
        """Consume one sample and return features computed from past data only."""
        index = min(self.lap_slices - 1, int(progress_fraction * self.lap_slices))
        if self._current_speed is None:
            self._current_speed = np.full(self.lap_slices, np.nan)
            self._current_brake = np.full(self.lap_slices, np.nan)
        self._current_speed[index] = sample.speed_mps
        self._current_brake[index] = sample.brake

        baseline_speed = (
            float(np.nanmean(np.vstack(self._speed)[:, index])) if self._speed else None
        )
        speed_delta = (
            0.0 if baseline_speed is None else sample.speed_mps - baseline_speed
        )

        if (
            baseline_speed is not None
            and sample.throttle >= self.throttle_threshold
            and sample.speed_mps < baseline_speed - self.speed_tolerance_mps
        ):
            self._super_clipping_samples += 1
        self._total_samples += 1

        if sample.sector != self._current_sector:
            if self._current_sector >= 0:
                self._sector_times.append(self._current_sector_time)
            self._current_sector = sample.sector
            self._current_sector_time = 0.0
        self._current_sector_time += 1.0  # caller supplies dt via time deltas

        baseline_brake = (
            float(np.nanmean(np.vstack(self._brake)[:, index])) if self._brake else 0.0
        )
        baseline_sector = (
            float(np.mean(self._sector_times)) if self._sector_times else self._current_sector_time
        )

        valid_speed = [s for s in self._current_speed if not np.isnan(s)]
        return CausalFeatures(
            speed_delta_mps=speed_delta,
            sector_time_delta_s=self._current_sector_time - baseline_sector,
            brake_delta=sample.brake - baseline_brake,
            speed_variance=float(np.var(valid_speed)) if len(valid_speed) > 1 else 0.0,
            super_clipping_fraction=(
                self._super_clipping_samples / self._total_samples
                if self._total_samples
                else 0.0
            ),
            samples=self._total_samples,
        )

    def complete_lap(self) -> None:
        """Commit the current lap's samples to the rolling window."""
        if self._current_speed is not None and not np.all(np.isnan(self._current_speed)):
            self._speed.append(np.array(self._current_speed, copy=True))
            self._brake.append(
                np.array(self._current_brake if self._current_brake is not None else [], copy=True)
            )
            self._current_speed = None
            self._current_brake = None
            self._super_clipping_samples = 0
            self._total_samples = 0
