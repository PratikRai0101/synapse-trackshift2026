"""Spatial Level 2 reference trajectory over an upcoming track segment."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .socp_envelope import SOCPPerformanceEnvelope, SOCPProfile


@dataclass(frozen=True)
class TrackSample:
    distance_m: float
    curvature: float


@dataclass(frozen=True)
class SpatialReference:
    distances_m: tuple[float, ...]
    speeds_kmh: tuple[float, ...]
    kinetic_costates: tuple[float, ...]
    envelope: SOCPProfile


class SpatialTrajectoryPlanner:
    """Build a cone-feasible kinetic-energy/speed reference over distance."""

    def __init__(self, envelope: SOCPPerformanceEnvelope | None = None) -> None:
        self.envelope = envelope or SOCPPerformanceEnvelope()

    def plan(self, track: Sequence[TrackSample], requested_speed_kmh: float,
             speed_gain_kmh: float = 0.0, initial_energy: float = 100.0,
             reserve_energy: float = 0.0) -> SpatialReference:
        if not track:
            empty = self.envelope.solve([], [], [])
            return SpatialReference((), (), (), empty)
        distances = [sample.distance_m for sample in track]
        requested = [requested_speed_kmh + speed_gain_kmh * index
                     for index, _ in enumerate(track)]
        curvatures = [sample.curvature for sample in track]
        profile = self.envelope.solve(
            distances, requested, curvatures,
            initial_energy=initial_energy, reserve_energy=reserve_energy,
        )
        speeds = tuple(point.speed_kmh for point in profile.points)
        # Costate proxy: speed value is high where the cone permits extra pace.
        costates = tuple(max(0.0, requested_speed - point.speed_kmh)
                         for requested_speed, point in zip(requested, profile.points))
        return SpatialReference(tuple(distances), speeds, costates, profile)
