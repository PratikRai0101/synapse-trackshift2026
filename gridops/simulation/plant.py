"""Longitudinal action-responsive plant.

The plant owns truth and may saturate any request. It is the generative model
rolled out by the planner and evaluator; it is never handed to a deployable
controller object.

Declared simplifications for the first build:

- Longitudinal dynamics on a fixed path; lateral state is checked through the
  combined grip envelope, not integrated.
- Electrical deployment is limited by the battery solve; traction saturation
  clamps the resulting longitudinal force and is recorded as a grip violation.
- No slip-based tyre work; a declared utilisation proxy is used elsewhere.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..contracts.state import (
    BatteryParams,
    BatteryState,
    Control,
    SaturationReason,
    Track,
    VehicleParams,
    VehicleState,
    combined_drag_force,
    cornering_speed_limit_mps,
    downforce_n,
)
from .battery import solve_terminal_power, integrate as integrate_battery
from .tyres import (
    TyreParams,
    compounded_grip_multiplier,
    integrate as integrate_tyres,
    utilisation_stress,
)

MIN_TRACKING_SPEED_MPS = 3.0
SPEED_ERROR_GAIN_PER_S = 1.5
MAX_TRACKING_ACCEL_MPS2 = 12.0
MAX_LATERAL_RATE_MPS = 1.5
HALF_VEHICLE_WIDTH_M = 1.0


@dataclass
class PlantStep:
    state: VehicleState
    requested_p_k_dc_w: float
    realized_p_k_dc_w: float
    terminal_power_w: float
    current_a: float
    voltage_v: float
    engine_force_n: float
    brake_force_n: float
    longitudinal_force_n: float
    lateral_demand_n: float
    grip_limit_n: float
    grip_violation_n: float
    saturation: tuple[SaturationReason, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass
class Plant:
    vehicle: VehicleParams
    battery: BatteryParams
    track: Track
    tyre_params: TyreParams | None = None

    def mass_kg(self, state: VehicleState) -> float:
        return self.vehicle.mass_kg + state.fuel_kg

    def step(
        self,
        state: VehicleState,
        control: Control,
        dt_s: float,
    ) -> PlantStep:
        if dt_s <= 0.0:
            raise ValueError("dt_s must be positive")
        mass = self.mass_kg(state)
        v = state.speed_mps
        kappa = self.track.curvature_at(state.progress_m)
        grade = self.track.grade_at(state.progress_m)

        # --- battery: requested terminal power includes auxiliary load.
        p_term_req = control.p_k_dc_w + self.battery.aux_power_w
        power = solve_terminal_power(p_term_req, state.battery, self.battery, dt_s)
        realized_p_k_dc = power.power_w - self.battery.aux_power_w
        reasons = list(power.reasons)

        # --- MGU-K mechanical power and force at the wheels.
        if realized_p_k_dc >= 0.0:
            p_mech = self.vehicle.mgu_k_efficiency * realized_p_k_dc
        else:
            p_mech = realized_p_k_dc / self.vehicle.mgu_k_efficiency
        f_k = self._deployment_force(p_mech, v)

        # --- tracker: choose engine/brake to approach the target speed.
        f_drag = combined_drag_force(v, self.vehicle)
        f_roll = self.vehicle.rolling_resistance * mass * 9.80665
        f_grade = mass * 9.80665 * math.sin(grade)

        if control.target_speed_mps <= 0.0:
            f_engine, f_brake = 0.0, 0.0
        else:
            target = min(
                control.target_speed_mps,
                cornering_speed_limit_mps(state.progress_m, self.track, self.vehicle, mass),
            )
            a_cmd = SPEED_ERROR_GAIN_PER_S * (target - v)
            a_cmd = max(-MAX_TRACKING_ACCEL_MPS2, min(MAX_TRACKING_ACCEL_MPS2, a_cmd))
            required = mass * a_cmd - f_k + f_drag + f_roll + f_grade
            if required >= 0.0:
                f_engine = min(required, self.vehicle.max_engine_force_n)
                f_brake = 0.0
            else:
                f_engine = 0.0
                f_brake = min(-required, self.vehicle.max_brake_force_n)

        # --- combined grip envelope.
        fz = mass * 9.80665 + downforce_n(v, self.vehicle)
        f_lat = mass * v * v * abs(kappa)
        mu_eff = self.vehicle.mu_base
        if state.tyres is not None and self.tyre_params is not None:
            mu_eff = self.vehicle.mu_base * compounded_grip_multiplier(
                state.tyres, self.tyre_params
            )
        f_long_limit = math.sqrt(max(0.0, (mu_eff * fz) ** 2 - f_lat**2))
        f_x = f_engine + f_k - f_brake
        f_x_clamped = max(-f_long_limit, min(f_long_limit, f_x))
        violation = abs(f_x) - abs(f_x_clamped)
        if violation > 0.0:
            reasons.append(SaturationReason.GRIP_LIMIT)

        # --- integrate motion.
        f_net = f_x_clamped - f_drag - f_roll - f_grade
        a = f_net / mass
        v_new = max(0.0, v + a * dt_s)
        s_new = state.progress_m + 0.5 * (v + v_new) * dt_s

        # --- integrate battery and fuel.
        battery_new = integrate_battery(state.battery, power.current_a, dt_s, self.battery)
        fuel_new = state.fuel_kg
        if self.vehicle.fuel_burn_kg_per_s > 0.0 and f_engine > 0.0:
            fuel_new = max(0.0, fuel_new - self.vehicle.fuel_burn_kg_per_s * dt_s)

        # --- kinematic lateral tracking, clamped inside the track.
        half_track = self.track.width_at(s_new % self.track.length_m) / 2.0
        lateral_limit = max(0.0, half_track - HALF_VEHICLE_WIDTH_M)
        lateral_delta = control.lateral_target_m - state.lateral_m
        max_lateral_step = MAX_LATERAL_RATE_MPS * dt_s
        lateral_new = state.lateral_m + max(
            -max_lateral_step, min(max_lateral_step, lateral_delta)
        )
        lateral_new = max(-lateral_limit, min(lateral_limit, lateral_new))

        # --- tyre thermal state and irreversible wear.
        new_tyres = state.tyres
        if state.tyres is not None and self.tyre_params is not None:
            capacity = max(1.0, self.vehicle.mu_base * fz)
            stress_front = utilisation_stress(0.3 * f_x_clamped, f_lat, fz, self.vehicle.mu_base)
            stress_rear = utilisation_stress(0.7 * f_x_clamped, f_lat, fz, self.vehicle.mu_base)
            new_tyres = integrate_tyres(
                state.tyres, stress_front, stress_rear, v_new, dt_s, self.tyre_params
            )

        return PlantStep(
            state=VehicleState(s_new, v_new, fuel_new, battery_new, lateral_new, new_tyres),
            requested_p_k_dc_w=control.p_k_dc_w,
            realized_p_k_dc_w=realized_p_k_dc,
            terminal_power_w=power.power_w,
            current_a=power.current_a,
            voltage_v=power.voltage_v,
            engine_force_n=f_engine,
            brake_force_n=f_brake,
            longitudinal_force_n=f_x_clamped,
            lateral_demand_n=f_lat,
            grip_limit_n=f_long_limit,
            grip_violation_n=violation,
            saturation=tuple(dict.fromkeys(reasons)),
        )

    def _deployment_force(self, p_mech_w: float, speed_mps: float) -> float:
        """Map mechanical power to force without dividing by a tiny speed."""
        if abs(p_mech_w) < 1e-9:
            return 0.0
        v_eff = max(speed_mps, MIN_TRACKING_SPEED_MPS)
        force = p_mech_w / v_eff
        limit = self.vehicle.max_engine_force_n
        return max(-limit, min(limit, force))


def initial_state(
    battery: BatteryParams,
    progress_m: float = 0.0,
    speed_mps: float = 80.0,
    tyres=None,
) -> VehicleState:
    return VehicleState(
        progress_m=progress_m,
        speed_mps=speed_mps,
        fuel_kg=0.0,
        battery=BatteryState(soc=battery.soc_initial, temp_k=battery.coolant_temp_k),
        tyres=tyres,
    )
