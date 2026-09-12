"""Actuator-aware short-horizon MPC for Level 1 execution."""
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
    brake_accel: float = 0.12
    drag_accel: float = 0.02
    energy_per_power: float = 0.015
    regen_per_fraction: float = 0.010
    reserve_energy: float = 5.0
    energy_weight: float = 0.08
    brake_weight: float = 0.04
    regen_reward: float = 0.02
    max_power_rate_per_s: float = 8.0
    max_brake_rate_per_s: float = 10.0
    max_regen_fraction: float = 0.8
    battery_temperature: float = 70.0
    thermal_gain_per_power_s: float = 0.08
    cooling_rate_per_s: float = 0.03
    max_battery_temperature: float = 110.0


@dataclass(frozen=True)
class ZoneMPCResult:
    power_fraction: float
    predicted_speeds: tuple[float, ...]
    predicted_energy: tuple[float, ...]
    objective: float
    success: bool
    status: str
    regen_fraction: float = 0.0
    brake_fraction: float = 0.0
    predicted_temperatures: tuple[float, ...] = ()
    max_constraint_residual: float = 0.0
    actuator_limited: bool = False


class ZoneMPC:
    """Linear actuator-aware receding-horizon MPC.

    Decision variables are electric power, friction braking and regeneration
    for every horizon step. All constraints are explicit LP inequalities so the
    result exposes feasibility and residuals rather than hiding them.
    """

    def __init__(self, config: ZoneMPCConfig | None = None) -> None:
        self.config = config or ZoneMPCConfig()
        self.previous_power = 0.0
        self.previous_brake = 0.0
        self.previous_regen = 0.0

    @staticmethod
    def _index(channel: int, step: int, horizon: int) -> int:
        return channel * horizon + step

    def solve(self, speed_kmh: float, energy: float, target_speed_kmh: float,
              target_energy: float | None = None,
              battery_temperature: float | None = None) -> ZoneMPCResult:
        cfg = self.config
        n = max(1, int(cfg.horizon))
        channels = 3  # power, friction brake, regeneration
        variables = channels * n
        power, brake, regen = 0, 1, 2
        c = np.zeros(variables)
        speed_error = float(target_speed_kmh) - float(speed_kmh)
        c[power * n:(power + 1) * n] = cfg.energy_weight - speed_error * cfg.accel_per_power
        c[brake * n:(brake + 1) * n] = cfg.brake_weight
        c[regen * n:(regen + 1) * n] = -cfg.regen_reward
        A: list[np.ndarray] = []
        b: list[float] = []

        def row() -> np.ndarray:
            return np.zeros(variables)

        # Battery reserve and optional target reserve.
        reserve = max(cfg.reserve_energy, float(target_energy or 0.0))
        energy_row = row()
        for step in range(n):
            energy_row[power * n + step] = cfg.energy_per_power * cfg.dt_s
            energy_row[regen * n + step] = -cfg.regen_per_fraction * cfg.dt_s
        A.append(energy_row)
        b.append(max(0.0, float(energy) - reserve))

        # Speed-zone dynamics: cumulative acceleration cannot exceed target.
        for step in range(1, n + 1):
            speed_row = row()
            speed_row[power * n:power * n + step] = cfg.accel_per_power * cfg.dt_s
            speed_row[brake * n:brake * n + step] = -cfg.brake_accel * cfg.dt_s
            allowed = max(0.0, float(target_speed_kmh) - float(speed_kmh) +
                           cfg.drag_accel * cfg.dt_s * step)
            A.append(speed_row)
            b.append(allowed)

        # Power plus regeneration cannot exceed the battery inverter budget.
        for step in range(n):
            row_value = row()
            row_value[power * n + step] = 1.0
            row_value[regen * n + step] = 1.0
            A.append(row_value)
            b.append(1.0)

        # Rate limits make the first control physically reachable.
        for step in range(n):
            for channel, previous, rate in (
                (power, self.previous_power, cfg.max_power_rate_per_s),
                (brake, self.previous_brake, cfg.max_brake_rate_per_s),
                (regen, self.previous_regen, cfg.max_power_rate_per_s),
            ):
                upper = row(); lower = row()
                upper[channel * n + step] = 1.0
                lower[channel * n + step] = -1.0
                prior = previous if step == 0 else None
                if prior is not None:
                    A.extend((upper, lower))
                    b.extend((prior + rate * cfg.dt_s, -prior + rate * cfg.dt_s))
                else:
                    # Difference against the previous horizon variable.
                    upper[channel * n + step] = 1.0
                    lower[channel * n + step] = -1.0
                    upper[channel * n + step - 1] = -1.0
                    lower[channel * n + step - 1] = 1.0
                    A.extend((upper, lower))
                    b.extend((rate * cfg.dt_s, rate * cfg.dt_s))

        # Linearized battery temperature ceiling.
        start_temperature = (cfg.battery_temperature if battery_temperature is None
                             else float(battery_temperature))
        thermal_row = row()
        for step in range(n):
            thermal_row[power * n + step] = cfg.thermal_gain_per_power_s * cfg.dt_s
        A.append(thermal_row)
        b.append(cfg.max_battery_temperature - start_temperature)

        bounds = ([(0.0, 1.0)] * n + [(0.0, 1.0)] * n +
                  [(0.0, min(1.0, cfg.max_regen_fraction))] * n)
        result = linprog(c, A_ub=np.asarray(A), b_ub=np.asarray(b), bounds=bounds,
                         method="highs")
        if not result.success:
            return ZoneMPCResult(0.0, (speed_kmh,), (energy,), 0.0, False,
                                 result.message, actuator_limited=True)

        controls = result.x
        speeds: list[float] = []
        energies: list[float] = []
        temperatures: list[float] = []
        current_speed = float(speed_kmh)
        stored = float(energy)
        temperature = start_temperature
        for step in range(n):
            p = controls[power * n + step]
            br = controls[brake * n + step]
            rg = controls[regen * n + step]
            current_speed += (cfg.accel_per_power * p - cfg.brake_accel * br -
                              cfg.drag_accel) * cfg.dt_s
            stored += (-cfg.energy_per_power * p + cfg.regen_per_fraction * rg) * cfg.dt_s
            temperature += (cfg.thermal_gain_per_power_s * p -
                            cfg.cooling_rate_per_s * (temperature - 70.0)) * cfg.dt_s
            speeds.append(current_speed)
            energies.append(stored)
            temperatures.append(temperature)
        self.previous_power = float(controls[power * n])
        self.previous_brake = float(controls[brake * n])
        self.previous_regen = float(controls[regen * n])
        residuals = [max(0.0, reserve - min(energies, default=stored)),
                     max(0.0, max(temperatures, default=temperature) - cfg.max_battery_temperature)]
        return ZoneMPCResult(
            float(controls[power * n]), tuple(speeds), tuple(energies),
            float(result.fun), True, result.message,
            float(controls[regen * n]), float(controls[brake * n]),
            tuple(temperatures), max(residuals, default=0.0),
            bool(controls[brake * n] > 1e-8 or controls[regen * n] > 1e-8),
        )
