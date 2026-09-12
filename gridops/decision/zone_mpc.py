"""Block 4A — Zone MPC: a linear program that tracks an energy zone.

The tactical layer hands down a *zone* for kinetic energy and stored electrical
energy, not a single setpoint. The zone tracker minimises overshoot outside the
zone, which is a linear objective with linear dynamics, so the subproblem is an
LP and solves in milliseconds. Positive energy savings are not chased; the
tracker only cares about leaving the zone.

This is the fast supervisory layer. It is not a lateral controller and it does
not act on the tyres directly.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import cvxpy as cp
import numpy as np

from ..contracts.state import BatteryParams, Track, VehicleParams, combined_drag_force
from ..race_value.lap_map import usable_energy_j

J_PER_MJ = 1_000_000.0


@dataclass(frozen=True)
class EnergyZone:
    e_kin_low_j: float
    e_kin_high_j: float
    e_bat_low_j: float
    e_bat_high_j: float

    def __post_init__(self) -> None:
        if self.e_kin_low_j > self.e_kin_high_j:
            raise ValueError("kinetic zone must be ordered low <= high")
        if self.e_bat_low_j > self.e_bat_high_j:
            raise ValueError("battery zone must be ordered low <= high")


@dataclass
class ZonePlan:
    status: str
    is_dcp: bool
    p_k_dc_w: np.ndarray
    speed_mps: np.ndarray
    solve_time_s: float
    objective: float
    notes: tuple[str, ...] = ()

    @property
    def accepted(self) -> bool:
        return self.status in {"optimal", "optimal_inaccurate"} and len(self.p_k_dc_w) > 0

    def first_power_w(self) -> float:
        return float(self.p_k_dc_w[0]) if len(self.p_k_dc_w) else 0.0


class ZoneMPC:
    def __init__(
        self,
        track: Track,
        vehicle: VehicleParams,
        battery: BatteryParams,
        ds_m: float = 25.0,
        horizon_m: float = 300.0,
        solver: str = "CLARABEL",
    ) -> None:
        self.track = track
        self.vehicle = vehicle
        self.battery = battery
        self.ds_m = ds_m
        self.horizon_m = horizon_m
        self.solver = solver

    def solve(
        self,
        progress_m: float,
        speed_mps: float,
        battery_state,
        zone: EnergyZone,
        reference_speed_mps: float | None = None,
    ) -> ZonePlan:
        n = max(2, int(round(self.horizon_m / self.ds_m)))
        ds = self.horizon_m / n
        mass = self.vehicle.mass_kg
        v_ref = np.full(n, reference_speed_mps or speed_mps)
        f_res = np.array([combined_drag_force(float(v), self.vehicle) for v in v_ref])

        e = cp.Variable(n + 1, pos=True)
        p = cp.Variable(n, nonneg=True)
        f_brake = cp.Variable(n, nonneg=True)
        E = cp.Variable(n + 1)
        over_kin = cp.Variable(n + 1, nonneg=True)
        under_kin = cp.Variable(n + 1, nonneg=True)
        over_bat = cp.Variable(n + 1, nonneg=True)
        under_bat = cp.Variable(n + 1, nonneg=True)

        constraints = [
            e[0] == 0.5 * mass * speed_mps**2,
            E[0] == usable_energy_j(battery_state, self.battery),
            p <= self.battery.aux_power_w + 350_000.0,
            f_brake <= self.vehicle.max_brake_force_n,
        ]
        for k in range(n):
            v = float(v_ref[k])
            f_k = p[k] * self.vehicle.mgu_k_efficiency / v
            constraints += [
                e[k + 1] == e[k] + ds * (f_k - f_brake[k] - f_res[k]),
                E[k + 1]
                == E[k] - (ds / v) * (p[k] + self.battery.aux_power_w),
                e[k] <= zone.e_kin_high_j + over_kin[k],
                e[k] >= zone.e_kin_low_j - under_kin[k],
                E[k] <= zone.e_bat_high_j + over_bat[k],
                E[k] >= zone.e_bat_low_j - under_bat[k],
            ]
        objective = cp.Minimize(
            cp.sum(over_kin) + cp.sum(under_kin) + cp.sum(over_bat) + cp.sum(under_bat)
        )
        problem = cp.Problem(objective, constraints)
        is_dcp = bool(problem.is_dcp())
        start = time.perf_counter()
        notes: list[str] = []
        try:
            problem.solve(solver=getattr(cp, self.solver))
        except Exception as exc:
            notes.append(f"solver_error:{type(exc).__name__}")
        solve_time = time.perf_counter() - start

        status = problem.status or "unavailable"
        if not is_dcp:
            notes.append("dcp_check_failed")
        if p.value is None:
            return ZonePlan(
                status=status, is_dcp=is_dcp, p_k_dc_w=np.zeros(0),
                speed_mps=np.zeros(0), solve_time_s=solve_time,
                objective=float("nan"), notes=tuple(notes + ["no_solution"]),
            )
        p_val = np.asarray(p.value).ravel()
        e_val = np.asarray(e.value).ravel()
        return ZonePlan(
            status=status,
            is_dcp=is_dcp,
            p_k_dc_w=p_val,
            speed_mps=np.sqrt(np.maximum(2.0 * e_val * 1.0 / mass, 0.0)),
            solve_time_s=solve_time,
            objective=float(problem.value) if problem.value is not None else float("nan"),
            notes=tuple(notes),
        )
