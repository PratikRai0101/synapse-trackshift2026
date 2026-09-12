"""Short-horizon linear zone MPC for Level 1 execution.

The local vehicle model is linearized over a short horizon. The LP chooses a
bounded deployment fraction while tracking a speed zone and preserving a hard
battery reserve. Only the first action is applied, then the problem is solved
again at the next tick.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
from scipy.optimize import linprog


@dataclass(frozen=True)
class ZoneMPCConfig:
    horizon: int = 8
    dt_s: float = 0.01
    accel_per_power: float = 0.08
    drag_accel: float = 0.02
    energy_per_power: float = 0.015
    reserve_energy: float = 5.0
    energy_weight: float = 0.08


@dataclass(frozen=True)
class ZoneMPCResult:
    power_fraction: float
    predicted_speeds: tuple[float, ...]
    predicted_energy: tuple[float, ...]
    objective: float
    success: bool
    status: str


class ZoneMPC:
    """LP-based receding-horizon zone controller."""

    def __init__(self, config: ZoneMPCConfig | None = None) -> None:
        self.config = config or ZoneMPCConfig()

    def solve(self, speed_kmh: float, energy: float, target_speed_kmh: float,
              target_energy: float | None = None) -> ZoneMPCResult:
        cfg = self.config
        n = max(1, int(cfg.horizon))
        speed_error = float(target_speed_kmh) - float(speed_kmh)
        # Positive error rewards power; energy pricing opposes unnecessary burn.
        coefficient = cfg.energy_weight - speed_error * cfg.accel_per_power
        c = np.full(n, coefficient, dtype=float)
        # Hard cumulative reserve constraint: sum(u*dt*rate) <= energy-reserve.
        max_energy_use = max(0.0, float(energy) - cfg.reserve_energy)
        row = np.full(n, cfg.energy_per_power * cfg.dt_s)
        A_ub = [row]
        b_ub = [max_energy_use]
        # A speed zone is an upper bound on cumulative acceleration. If already
        # over target, this forces zero deployment through the bound.
        for step in range(1, n + 1):
            cumulative = np.zeros(n)
            cumulative[:step] = cfg.accel_per_power * cfg.dt_s
            allowed = (float(target_speed_kmh) - float(speed_kmh) +
                       cfg.drag_accel * cfg.dt_s * step)
            A_ub.append(cumulative)
            b_ub.append(max(0.0, allowed))
        result = linprog(c, A_ub=np.asarray(A_ub), b_ub=np.asarray(b_ub),
                         bounds=[(0.0, 1.0)] * n, method="highs")
        if not result.success:
            return ZoneMPCResult(0.0, (speed_kmh,), (energy,), 0.0, False,
                                 result.message)
        controls = result.x
        speeds = []
        energies = []
        speed = float(speed_kmh)
        stored = float(energy)
        for control in controls:
            speed += (cfg.accel_per_power * control - cfg.drag_accel) * cfg.dt_s
            stored -= cfg.energy_per_power * control * cfg.dt_s
            speeds.append(speed)
            energies.append(stored)
        return ZoneMPCResult(float(controls[0]), tuple(speeds), tuple(energies),
                             float(result.fun), True, result.message)
