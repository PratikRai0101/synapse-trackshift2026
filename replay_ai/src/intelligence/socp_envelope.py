"""Spatial second-order-cone performance envelope reference solver.

The implementation keeps the SOCP contract explicit while solving the coupled
spatial constraints with a deterministic forward/backward projection. A solver
backend can replace this routine without changing the profile or residual API.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class SOCPConfig:
    friction_mu: float = 1.45
    gravity: float = 9.81
    max_speed_kmh: float = 360.0
    min_speed_kmh: float = 20.0
    max_brake_accel: float = 15.0
    max_power_accel: float = 8.0
    energy_rate_per_m: float = 0.001
    reserve_energy: float = 0.0


@dataclass(frozen=True)
class SOCPPoint:
    distance_m: float
    speed_kmh: float
    curvature: float
    lateral_accel: float
    longitudinal_accel: float
    cone_radius: float
    cone_residual: float
    feasible: bool
    energy_remaining: float = 0.0
    speed_residual: float = 0.0
    reserve_residual: float = 0.0


@dataclass(frozen=True)
class SOCPProfile:
    points: tuple[SOCPPoint, ...]
    objective: float
    feasible: bool
    max_residual: float
    energy_remaining: float = 0.0
    reserve_feasible: bool = True


class SOCPPerformanceEnvelope:
    """Coupled spatial speed, grip and battery-reserve projection."""

    def __init__(self, config: SOCPConfig | None = None) -> None:
        self.config = config or SOCPConfig()

    def _curvature_speed_limit(self, curvature: float) -> float:
        cfg = self.config
        if abs(curvature) < 1e-12:
            return cfg.max_speed_kmh
        return min(cfg.max_speed_kmh,
                   3.6 * math.sqrt(cfg.friction_mu * cfg.gravity / abs(curvature)))

    def solve(self, distances: Sequence[float], requested_speeds_kmh: Sequence[float],
              curvatures: Sequence[float], requested_accels: Sequence[float] | None = None,
              initial_energy: float = 100.0, reserve_energy: float | None = None
              ) -> SOCPProfile:
        if not (len(distances) == len(requested_speeds_kmh) == len(curvatures)):
            raise ValueError("distance, speed and curvature grids must have equal length")
        if not distances:
            return SOCPProfile((), 0.0, True, 0.0, initial_energy, True)
        if any(float(b) <= float(a) for a, b in zip(distances, distances[1:])):
            raise ValueError("distance grid must be strictly increasing")
        n = len(distances)
        accels = list(requested_accels or [0.0] * n)
        if len(accels) != n:
            raise ValueError("requested acceleration grid has the wrong length")
        cfg = self.config
        reserve = cfg.reserve_energy if reserve_energy is None else max(0.0, reserve_energy)
        requested = [max(cfg.min_speed_kmh, min(cfg.max_speed_kmh, float(speed)))
                     for speed in requested_speeds_kmh]
        limits = [max(cfg.min_speed_kmh, self._curvature_speed_limit(float(curvature)))
                  for curvature in curvatures]
        speeds = [min(speed, limit) for speed, limit in zip(requested, limits)]

        # Project the spatial dynamics in both directions. Repeating the pass
        # makes the acceleration/braking cones consistent at every segment.
        for _ in range(3):
            for index in range(n - 1):
                ds = float(distances[index + 1]) - float(distances[index])
                reachable = math.sqrt(max(0.0, (speeds[index] / 3.6) ** 2 +
                                          2.0 * cfg.max_power_accel * ds)) * 3.6
                speeds[index + 1] = min(speeds[index + 1], reachable, limits[index + 1])
            for index in range(n - 2, -1, -1):
                ds = float(distances[index + 1]) - float(distances[index])
                reachable = math.sqrt(max(0.0, (speeds[index + 1] / 3.6) ** 2 +
                                          2.0 * cfg.max_brake_accel * ds)) * 3.6
                speeds[index] = min(speeds[index], reachable, limits[index])

        energy = max(0.0, float(initial_energy))
        points: list[SOCPPoint] = []
        objective = 0.0
        max_residual = 0.0
        reserve_ok = True
        for index, (distance, speed, curvature, requested_accel) in enumerate(
                zip(distances, speeds, curvatures, accels)):
            speed_ms = speed / 3.6
            lateral = speed_ms * speed_ms * abs(float(curvature))
            radius = cfg.friction_mu * cfg.gravity
            longitudinal_limit = math.sqrt(max(0.0, radius * radius - lateral * lateral))
            if index == 0:
                longitudinal = max(-min(cfg.max_brake_accel, longitudinal_limit),
                                   min(longitudinal_limit, float(requested_accel)))
            else:
                ds = float(distances[index]) - float(distances[index - 1])
                previous_ms = speeds[index - 1] / 3.6
                longitudinal = (speed_ms * speed_ms - previous_ms * previous_ms) / (2.0 * ds)
                longitudinal = max(-min(cfg.max_brake_accel, longitudinal_limit),
                                   min(longitudinal_limit, longitudinal))
            norm = math.hypot(longitudinal, lateral)
            cone_residual = max(0.0, norm - radius)
            speed_residual = max(0.0, speed - limits[index])
            if index > 0:
                ds = float(distances[index]) - float(distances[index - 1])
                energy -= cfg.energy_rate_per_m * ds * (0.5 + speed / 360.0)
            energy = max(0.0, energy)
            reserve_residual = max(0.0, reserve - energy)
            reserve_ok &= reserve_residual <= 1e-8
            objective += (speed - float(requested_speeds_kmh[index])) ** 2
            objective += (longitudinal - float(requested_accel)) ** 2
            max_residual = max(max_residual, cone_residual, speed_residual,
                               reserve_residual)
            points.append(SOCPPoint(float(distance), speed, float(curvature), lateral,
                                    longitudinal, radius, cone_residual,
                                    cone_residual <= 1e-8 and speed_residual <= 1e-8,
                                    energy, speed_residual, reserve_residual))
        feasible = max_residual <= 1e-8 and reserve_ok
        return SOCPProfile(tuple(points), objective, feasible, max_residual,
                           energy, reserve_ok)
