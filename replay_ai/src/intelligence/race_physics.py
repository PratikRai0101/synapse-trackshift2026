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
        self._previous_order: dict[str, float] = {}

    def evaluate(self, ego: CarPose, rival: CarPose) -> PassResult:
        longitudinal_gap = abs(ego.distance_m - rival.distance_m)
        lateral_gap = abs(ego.lateral_m - rival.lateral_m) - (ego.width_m + rival.width_m) / 2
        clearance = min(longitudinal_gap - (ego.length_m + rival.length_m) / 2,
                        lateral_gap)
        contact = clearance < 0.0
        ego_on_track = abs(ego.lateral_m) + ego.width_m / 2 <= self.track.width_m / 2
        rival_on_track = abs(rival.lateral_m) + rival.width_m / 2 <= self.track.width_m / 2
        previous = self._previous_order.get(ego.car_id)
        self._previous_order[ego.car_id] = ego.distance_m - rival.distance_m
        order_changed = previous is not None and previous < 0.0 <= ego.distance_m - rival.distance_m
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
