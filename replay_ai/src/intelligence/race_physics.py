"""Race geometry, dirty-air and pit-strategy reference models."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class CarPose:
    car_id: str
    distance_m: float
    lateral_m: float = 0.0
    length_m: float = 5.5
    width_m: float = 2.0


@dataclass(frozen=True)
class TrackGeometry:
    length_m: float = 5000.0
    width_m: float = 12.0


@dataclass(frozen=True)
class PassResult:
    legal: bool
    contact: bool
    clearance_m: float
    reason: str


class PassMonitor:
    """Require longitudinal order change, clearance and track containment."""

    def __init__(self, track: TrackGeometry | None = None,
                 clearance_margin_m: float = 0.25) -> None:
        self.track = track or TrackGeometry()
        self.clearance_margin_m = clearance_margin_m
        self._previous_pose: dict[tuple[str, str], tuple[float, float]] = {}

    @staticmethod
    def _swept_contact(previous, current, half_length, half_width):
        """Intersect relative linear motion with the open Minkowski rectangle.

        A pair is in contact only when BOTH axes overlap at the same time.
        Sweeping prevents a same-lane pass from tunnelling between samples.
        """
        enter, leave = 0.0, 1.0
        for start, end, extent in zip(previous, current, (half_length, half_width)):
            delta = end - start
            if abs(delta) < 1e-12:
                if abs(start) >= extent:
                    return False
                continue
            a, b = sorted(((-extent - start) / delta, (extent - start) / delta))
            enter, leave = max(enter, a), min(leave, b)
            if enter >= leave:
                return False
        return enter < leave

    def evaluate(self, ego: CarPose, rival: CarPose) -> PassResult:
        longitudinal_gap = abs(ego.distance_m - rival.distance_m)
        lateral_gap = abs(ego.lateral_m - rival.lateral_m) - (ego.width_m + rival.width_m) / 2
        half_length = (ego.length_m + rival.length_m) / 2
        half_width = (ego.width_m + rival.width_m) / 2
        clearance = max(longitudinal_gap - half_length, lateral_gap)
        relative = (ego.distance_m - rival.distance_m, ego.lateral_m - rival.lateral_m)
        key = (ego.car_id, rival.car_id)
        previous = self._previous_pose.get(key)
        contact = clearance < 0.0 or (
            previous is not None and self._swept_contact(previous, relative, half_length, half_width)
        )
        ego_on_track = abs(ego.lateral_m) + ego.width_m / 2 <= self.track.width_m / 2
        rival_on_track = abs(rival.lateral_m) + rival.width_m / 2 <= self.track.width_m / 2
        self._previous_pose[key] = relative
        order_changed = previous is not None and previous[0] < 0.0 <= relative[0]
        if contact:
            return PassResult(False, True, clearance, "contact")
        if not ego_on_track or not rival_on_track:
            return PassResult(False, False, clearance, "track exit")
        if order_changed and clearance >= self.clearance_margin_m:
            return PassResult(True, False, clearance, "clean pass")
        return PassResult(False, False, clearance, "catch-up")


class DirtyAirModel:
    """Downforce/grip reduction behind a leading car."""

    def __init__(self, max_grip_loss: float = 0.15, reference_gap_s: float = 1.0) -> None:
        self.max_grip_loss = max(0.0, min(0.8, max_grip_loss))
        self.reference_gap_s = max(1e-6, reference_gap_s)

    def grip_multiplier(self, gap_s: float, ahead_active_aero: float = 1.0) -> float:
        if gap_s > self.reference_gap_s:
            return 1.0
        proximity = max(0.0, min(1.0, 1.0 - gap_s / self.reference_gap_s))
        return max(0.2, 1.0 - self.max_grip_loss * proximity * ahead_active_aero)


@dataclass(frozen=True)
class PitDecision:
    pit: bool
    compound: str
    expected_time_loss_s: float
    reason: str


class PitStrategy:
    """Reference pit decision based on tyre wear, fuel and remaining laps."""

    def __init__(self, pit_loss_s: float = 22.0, wear_threshold: float = 0.75) -> None:
        self.pit_loss_s = pit_loss_s
        self.wear_threshold = wear_threshold

    def decide(self, tyre_wear: float, fuel_kg: float, laps_remaining: int,
               available_compound: str = "medium") -> PitDecision:
        if tyre_wear >= self.wear_threshold and laps_remaining > 3:
            return PitDecision(True, available_compound, self.pit_loss_s,
                               "tyre wear exceeds pit threshold")
        if fuel_kg < 2.0 and laps_remaining > 1:
            return PitDecision(True, available_compound, self.pit_loss_s,
                               "fuel reserve is insufficient")
        return PitDecision(False, "current", 0.0, "continue current stint")
