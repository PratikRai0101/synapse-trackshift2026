"""Conditional convex deployment planner.

Solves a spatial-grid subproblem with frozen local predictions, then hands the
profile to the nonlinear plant for validation. It does **not** claim global
optimality of the coupled problem: coefficients (speed, grip, wake, thermal)
are frozen per solve and the trust region bounds the mismatch.

Formulation (deploy regime, ``p >= 0``; friction braking absorbs deceleration)::

    e_{k+1} = e_k + ds (F_ICE + F_K - F_brake - F_res)
    F_K     = eta * p_k / v_ref,k
    E_{k+1} = E_k - (ds / v_ref,k) * alpha * (p_k + p_aux)
    || [F_x / r_x, F_y / r_y] ||_2 <= mu F_z(v_ref)      (second-order cone)
    v_ref - dv <= v_k <= v_ref + dv                       (trust region)

    minimise  sum ds sqrt(m/2) e_k^{-1/2} + V_terminal(E_N)

Energies are solved in megajoules to keep the conic problem well conditioned.
Recovery is a separate enumerated regime, not a simultaneous charge/discharge
variable pair.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Callable

import cvxpy as cp
import numpy as np

from ..contracts.state import (
    BatteryParams,
    Track,
    VehicleParams,
    combined_drag_force,
    cornering_speed_limit_mps,
    normal_load_n,
)
from ..race_value.lap_map import TerminalValue

J_PER_MJ = 1_000_000.0


@dataclass(frozen=True)
class PlannerConfig:
    ds_m: float = 50.0
    horizon_m: float = 500.0
    trust_dv_mps: float = 8.0
    rx: float = 1.0
    ry: float = 1.2
    p_max_w: float = 350_000.0
    min_speed_mps: float = 12.0
    chemical_alpha: float = 1.0
    solver: str = "CLARABEL"
    residual_tolerance: float = 1e-3


@dataclass
class ConvexPlan:
    s_m: np.ndarray
    speed_mps: np.ndarray
    p_k_dc_w: np.ndarray
    terminal_energy_j: float
    predicted_time_s: float
    is_dcp: bool
    status: str
    solve_time_s: float
    max_dynamics_residual_mj: float
    max_grip_residual_n: float
    max_power_violation_w: float
    deployed_energy_j: float
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def accepted(self) -> bool:
        return self.status in {"optimal", "optimal_inaccurate"}

    def first_power_w(self) -> float:
        return float(self.p_k_dc_w[0]) if len(self.p_k_dc_w) else 0.0


class ConditionalConvexPlanner:
    def __init__(
        self,
        track: Track,
        vehicle: VehicleParams,
        battery: BatteryParams,
        terminal_value: TerminalValue,
        config: PlannerConfig | None = None,
    ) -> None:
        self.track = track
        self.vehicle = vehicle
        self.battery = battery
        self.terminal_value = terminal_value
        self.config = config or PlannerConfig()

    def reference_speed(self, s_m: float, base_speed_mps: float, mass_kg: float) -> float:
        limit = cornering_speed_limit_mps(s_m, self.track, self.vehicle, mass_kg)
        return max(self.config.min_speed_mps, min(base_speed_mps, limit))

    def plan(
        self,
        progress_m: float,
        speed_mps: float,
        usable_energy_j: float,
        base_speed_mps: float,
        mass_kg: float | None = None,
        lower_trust_dv_mps: float | None = None,
    ) -> ConvexPlan:
        """Plan a deployment profile.

        ``lower_trust_dv_mps`` tightens only the *lower* speed bound relative to
        the corner-limited reference. An attack uses a small value so the plan
        must hold pace and therefore deploy, instead of trading speed away for
        energy. The reference is already corner-limited, so corners stay legal.
        """
        cfg = self.config
        dv_lo = cfg.trust_dv_mps if lower_trust_dv_mps is None else lower_trust_dv_mps
        mass = mass_kg if mass_kg is not None else self.vehicle.mass_kg
        n = max(2, int(round(cfg.horizon_m / cfg.ds_m)))
        ds = cfg.horizon_m / n
        s = progress_m + ds * np.arange(n + 1)

        v_ref = np.array(
            [self.reference_speed(float(sk), base_speed_mps, mass) for sk in s[:n]]
        )
        kappa = np.array([self.track.curvature_at(float(sk)) for sk in s[:n]])
        grade = np.array([self.track.grade_at(float(sk)) for sk in s[:n]])
        f_res = np.array(
            [
                combined_drag_force(float(v), self.vehicle)
                + self.vehicle.rolling_resistance * mass * 9.80665
                + mass * 9.80665 * math.sin(float(g))
                for v, g in zip(v_ref, grade)
            ]
        )
        fz = np.array([normal_load_n(float(v), self.vehicle, mass) for v in v_ref])

        # --- variables (energies in MJ) ---
        e = cp.Variable(n + 1, pos=True)
        p = cp.Variable(n, nonneg=True)
        f_ice = cp.Variable(n, nonneg=True)
        f_brake = cp.Variable(n, nonneg=True)
        E = cp.Variable(n + 1)

        time_surrogate = cp.sum(
            ds * math.sqrt(mass / (2.0 * J_PER_MJ)) * cp.power(e[:n], -0.5)
        )
        a = self.terminal_value.seconds_per_joule * J_PER_MJ
        soft_mj = self.terminal_value.reserve.soft_floor_j / J_PER_MJ
        floor_mj = self.terminal_value.reserve.floor_j / J_PER_MJ
        terminal = -a * E[n] + a * self.terminal_value.shortfall_multiplier * cp.pos(
            soft_mj - E[n]
        )
        objective = cp.Minimize(time_surrogate + terminal)

        constraints: list = [
            e[0] == 0.5 * mass * speed_mps**2 / J_PER_MJ,
            E[0] == usable_energy_j / J_PER_MJ,
            E >= floor_mj,
            p <= cfg.p_max_w,
            f_ice <= self.vehicle.max_engine_force_n,
            f_brake <= self.vehicle.max_brake_force_n,
        ]
        for k in range(n):
            v = float(v_ref[k])
            f_k = p[k] * self.vehicle.mgu_k_efficiency / v
            f_x = f_ice[k] + f_k - f_brake[k]
            f_y = 2.0 * kappa[k] * e[k] * J_PER_MJ
            constraints += [
                e[k + 1] == e[k] + ds * (f_x - f_res[k]) / J_PER_MJ,
                E[k + 1]
                == E[k]
                - (ds / v) * cfg.chemical_alpha * (p[k] + self.battery.aux_power_w) / J_PER_MJ,
                cp.SOC(
                    self.vehicle.mu_base * fz[k],
                    cp.hstack([f_x / cfg.rx, f_y / cfg.ry]),
                ),
            ]
            if k >= 1:
                # The trust region constrains planned states, not the measured
                # initial state, which is fixed by the current speed.
                constraints += [
                    e[k] <= 0.5 * mass * (v + cfg.trust_dv_mps) ** 2 / J_PER_MJ,
                    e[k] >= 0.5 * mass * max(cfg.min_speed_mps, v - dv_lo) ** 2
                    / J_PER_MJ,
                ]

        problem = cp.Problem(objective, constraints)
        is_dcp = bool(problem.is_dcp())
        start = time.perf_counter()
        notes: list[str] = []
        try:
            problem.solve(solver=getattr(cp, cfg.solver))
        except Exception as exc:  # solver/backend failure must be surfaced
            notes.append(f"solver_error:{type(exc).__name__}")
        solve_time = time.perf_counter() - start

        status = problem.status or "unavailable"
        if not is_dcp:
            notes.append("dcp_check_failed")
        if status in {"optimal_inaccurate", "infeasible_inaccurate"}:
            notes.append("inaccurate_solution")

        if p.value is None or e.value is None:
            empty = np.zeros(n)
            return ConvexPlan(
                s_m=s, speed_mps=np.zeros(n + 1), p_k_dc_w=empty,
                terminal_energy_j=float("nan"), predicted_time_s=float("nan"),
                is_dcp=is_dcp, status=status, solve_time_s=solve_time,
                max_dynamics_residual_mj=float("nan"), max_grip_residual_n=float("nan"),
                max_power_violation_w=float("nan"), deployed_energy_j=float("nan"),
                notes=tuple(notes + ["no_solution"]),
            )

        e_val = np.asarray(e.value).ravel()
        p_val = np.asarray(p.value).ravel()
        f_ice_val = np.asarray(f_ice.value).ravel()
        f_brake_val = np.asarray(f_brake.value).ravel()

        # --- residuals, measured not assumed ---
        f_k = p_val * self.vehicle.mgu_k_efficiency / v_ref
        dynamics = e_val[1:] - (
            e_val[:-1] + ds * (f_ice_val + f_k - f_brake_val - f_res) / J_PER_MJ
        )
        grip = np.array(
            [
                math.hypot(
                    (f_ice_val[k] + f_k[k] - f_brake_val[k]) / cfg.rx,
                    (2.0 * kappa[k] * e_val[k] * J_PER_MJ) / cfg.ry,
                )
                - self.vehicle.mu_base * fz[k]
                for k in range(n)
            ]
        )
        power_violation = float(np.max(np.maximum(p_val - cfg.p_max_w, 0.0)))
        speed_val = np.sqrt(np.maximum(2.0 * e_val * J_PER_MJ / mass, 0.0))
        dt = ds / np.maximum(speed_val[:n], cfg.min_speed_mps)

        return ConvexPlan(
            s_m=s,
            speed_mps=speed_val,
            p_k_dc_w=p_val,
            terminal_energy_j=float(E.value[n]) * J_PER_MJ,
            predicted_time_s=float(np.sum(dt)),
            is_dcp=is_dcp,
            status=status,
            solve_time_s=solve_time,
            max_dynamics_residual_mj=float(np.max(np.abs(dynamics))),
            max_grip_residual_n=float(np.max(grip)),
            max_power_violation_w=power_violation,
            deployed_energy_j=float(np.sum(p_val * dt)),
            notes=tuple(notes),
        )

    def validate_plan(self, plan: ConvexPlan) -> tuple[bool, list[str]]:
        """Check solver residual tolerances; do not trust the status flag alone."""
        cfg = self.config
        problems: list[str] = []
        if not plan.accepted:
            problems.append(f"status={plan.status}")
        if plan.max_dynamics_residual_mj > cfg.residual_tolerance:
            problems.append("dynamics_residual")
        if plan.max_grip_residual_n > cfg.residual_tolerance:
            problems.append("grip_residual")
        if plan.max_power_violation_w > cfg.residual_tolerance:
            problems.append("power_bound")
        return (not problems), problems
