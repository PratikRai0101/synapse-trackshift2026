"""Compact curvature-aware ego vehicle plant for closed-loop validation."""
from __future__ import annotations

import math
from dataclasses import dataclass

from .race_physics import DirtyAirModel


@dataclass(frozen=True)
class PlantConfig:
    mass_kg: float = 800.0
    gravity: float = 9.81
    tyre_mu: float = 1.45
    max_power_accel: float = 8.0
    drag_accel: float = 0.02
    brake_accel: float = 12.0
    energy_rate: float = 1.2
    regen_rate: float = 0.7
    thermal_gain: float = 0.08
    cooling_rate: float = 0.03
    base_battery_resistance: float = 1.0
    temperature_resistance_coeff: float = 0.004
    wear_resistance_coeff: float = 0.25
    wear_rate: float = 0.0004
    initial_fuel_kg: float = 100.0
    fuel_burn_kg_per_s: float = 0.02
    slipstream_drag_reduction: float = 0.18
    pit_stop_duration_s: float = 22.0
    pit_fuel_kg: float = 80.0


@dataclass
class PlantState:
    speed_kmh: float = 280.0
    energy: float = 70.0
    battery_temperature: float = 70.0
    tyre_temperature: float = 85.0
    tyre_wear: float = 0.0
    distance_m: float = 0.0
    fuel_mass_kg: float = 100.0
    pit_time_s: float = 0.0
    pit_stops: int = 0


@dataclass(frozen=True)
class PlantStep:
    speed_kmh: float
    energy: float
    battery_temperature: float
    tyre_temperature: float
    tyre_wear: float
    distance_m: float
    longitudinal_accel: float
    lateral_accel: float
    grip_limited: bool
    battery_resistance: float


class VehiclePlant:
    """Integrate one ego state while enforcing a combined tyre cone."""

    def __init__(self, state: PlantState | None = None,
                 config: PlantConfig | None = None) -> None:
        self.state = state or PlantState()
        self.config = config or PlantConfig()
        self.dirty_air = DirtyAirModel()

    def pit_stop(self, new_tyre_temperature: float = 85.0) -> None:
        """Apply a pit-stop event: replace tyres and restore fuel mass."""
        state = self.state
        cfg = self.config
        state.tyre_wear = 0.0
        state.tyre_temperature = new_tyre_temperature
        state.fuel_mass_kg = cfg.pit_fuel_kg
        state.pit_time_s += cfg.pit_stop_duration_s
        state.pit_stops += 1

    def step(self, power_fraction: float, dt_s: float, curvature: float = 0.0,
             brake_fraction: float = 0.0, regen_fraction: float = 0.0,
             slipstream_gap_s: float | None = None,
             dirty_air_gap_s: float | None = None,
             ahead_active_aero: float = 1.0) -> PlantStep:
        cfg = self.config
        state = self.state
        dt = max(0.0, float(dt_s))
        power = max(0.0, min(1.0, float(power_fraction)))
        brake = max(0.0, min(1.0, float(brake_fraction)))
        regen = max(0.0, min(1.0, float(regen_fraction)))
        speed_ms = max(0.0, state.speed_kmh / 3.6)
        mass_factor = cfg.mass_kg / max(cfg.mass_kg + state.fuel_mass_kg, 1.0)
        drag = cfg.drag_accel
        if slipstream_gap_s is not None and slipstream_gap_s <= 1.0:
            drag *= max(0.0, 1.0 - cfg.slipstream_drag_reduction)
        dirty_multiplier = (self.dirty_air.grip_multiplier(dirty_air_gap_s, ahead_active_aero)
                            if dirty_air_gap_s is not None else 1.0)
        grip = (cfg.tyre_mu * cfg.gravity * dirty_multiplier *
                max(0.35, 1.0 - 0.35 * state.tyre_wear))
        if abs(float(curvature)) > 1e-9:
            speed_ms = min(speed_ms, math.sqrt(grip / abs(float(curvature))))
        lateral = speed_ms * speed_ms * abs(float(curvature))
        available_sq = max(0.0, grip * grip - lateral * lateral)
        available_longitudinal = math.sqrt(available_sq)
        battery_resistance = (cfg.base_battery_resistance +
                              cfg.temperature_resistance_coeff *
                              max(0.0, state.battery_temperature - 70.0) +
                              cfg.wear_resistance_coeff * state.tyre_wear)
        requested = (cfg.max_power_accel * mass_factor * power /
                     max(battery_resistance, 1e-6) - drag)
        requested -= cfg.brake_accel * brake
        longitudinal = max(-cfg.brake_accel,
                           min(available_longitudinal, requested))
        grip_limited = abs(requested) > abs(longitudinal) + 1e-9
        speed_ms = max(0.0, speed_ms + longitudinal * dt)
        state.speed_kmh = speed_ms * 3.6
        state.distance_m += speed_ms * dt
        state.fuel_mass_kg = max(0.0, state.fuel_mass_kg -
                                  cfg.fuel_burn_kg_per_s * max(power, 0.2) * dt)
        net_energy = (-cfg.energy_rate * power + cfg.regen_rate * regen) * dt
        state.energy = max(0.0, min(100.0, state.energy + net_energy))
        state.battery_temperature += (cfg.thermal_gain * abs(net_energy) -
                                      cfg.cooling_rate * (state.battery_temperature - 70.0)) * dt
        state.battery_temperature = max(20.0, min(120.0, state.battery_temperature))
        state.tyre_temperature += (abs(longitudinal) * 0.02 -
                                   0.04 * (state.tyre_temperature - 85.0)) * dt
        state.tyre_wear = min(1.0, state.tyre_wear +
                              cfg.wear_rate * (abs(longitudinal) + lateral) * dt)
        return PlantStep(state.speed_kmh, state.energy, state.battery_temperature,
                         state.tyre_temperature, state.tyre_wear, state.distance_m,
                         longitudinal, lateral, grip_limited, battery_resistance)
