"""Second-order-cone performance envelope reference solver.

For a fixed speed/curvature grid, the tyre constraint is the SOC

    ||(a_longitudinal, a_lateral)||_2 <= mu * g

The solver projects requested longitudinal acceleration onto that cone while
respecting speed and braking bounds. This keeps the feasibility layer explicit
and testable without hiding constraints behind a generic optimizer. A cvxpy
implementation can replace the projection routine later while retaining this
contract.
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


@dataclass(frozen=True)
class SOCPProfile:
    points: tuple[SOCPPoint, ...]
    objective: float
    feasible: bool
    max_residual: float


class SOCPPerformanceEnvelope:
    """Projected SOC envelope over a spatial speed/curvature profile."""

    def __init__(self, config: SOCPConfig | None = None) -> None:
        self.config = config or SOCPConfig()

    def solve(self, distances: Sequence[float], requested_speeds_kmh: Sequence[float],
              curvatures: Sequence[float], requested_accels: Sequence[float] | None = None
              ) -> SOCPProfile:
        if not (len(distances) == len(requested_speeds_kmh) == len(curvatures)):
            raise ValueError("distance, speed and curvature grids must have equal length")
        if not distances:
            return SOCPProfile((), 0.0, True, 0.0)
        accels = requested_accels or [0.0] * len(distances)
        if len(accels) != len(distances):
            raise ValueError("requested acceleration grid has the wrong length")
        cfg = self.config
        radius = cfg.friction_mu * cfg.gravity
        points = []
        objective = 0.0
        for distance, requested_speed, curvature, requested_accel in zip(
                distances, requested_speeds_kmh, curvatures, accels):
            speed = max(cfg.min_speed_kmh, min(cfg.max_speed_kmh, float(requested_speed)))
            lateral = (speed / 3.6) ** 2 * abs(float(curvature))
            remaining_sq = radius * radius - lateral * lateral
            if remaining_sq < 0.0:
                # The requested speed itself violates the cone. Reduce speed to
                # the lateral-only limit before projecting longitudinal force.
                speed = min(speed, 3.6 * math.sqrt(radius / max(abs(curvature), 1e-12)))
                lateral = (speed / 3.6) ** 2 * abs(float(curvature))
                remaining_sq = max(0.0, radius * radius - lateral * lateral)
            longitudinal_limit = math.sqrt(remaining_sq)
            longitudinal = max(-cfg.max_brake_accel,
                               min(longitudinal_limit, float(requested_accel)))
            norm = math.hypot(longitudinal, lateral)
            residual = max(0.0, norm - radius)
            objective += (speed - float(requested_speed)) ** 2 + (
                longitudinal - float(requested_accel)) ** 2
            points.append(SOCPPoint(float(distance), speed, float(curvature), lateral,
                                    longitudinal, radius, residual, residual <= 1e-8))
        max_residual = max(point.cone_residual for point in points)
        return SOCPProfile(tuple(points), objective, max_residual <= 1e-8, max_residual)
