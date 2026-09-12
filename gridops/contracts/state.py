"""Physical state, parameter and control contracts.

Sign conventions (frozen at G0):

- ``p_k_dc_w`` is MGU-K DC power at the declared accounting location.
  Positive = deployment (battery discharge). Negative = recovery (charge).
- Current ``I`` is discharge-positive.
- ``progress_m`` increases in the direction of travel along a fixed path.
- Fuel mass decreases as it is burned.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from .units import KELVIN_OFFSET

if TYPE_CHECKING:  # avoid a runtime import cycle with the tyre model
    from ..simulation.tyres import TyreSetState


class ActionFamily(str, Enum):
    REFERENCE = "reference"
    ATTACK_NOW = "attack_now"
    ATTACK_LATER = "attack_later"
    DEFEND = "defend"
    CONSERVE = "conserve"
    PROBE = "probe"


class SaturationReason(str, Enum):
    NONE = "none"
    POWER_LIMIT = "power_limit"
    CURRENT_LIMIT = "current_limit"
    VOLTAGE_LIMIT = "voltage_limit"
    SOC_FLOOR = "soc_floor"
    SOC_CEILING = "soc_ceiling"
    THERMAL_LIMIT = "thermal_limit"
    GRIP_LIMIT = "grip_limit"
    RULE_LIMIT = "rule_limit"


@dataclass(frozen=True)
class BatteryParams:
    """One-resistance electrothermal battery abstraction.

    Synthetic reference-cell family, not an identified F1 pack. Capacity is in
    ampere-hours; ``capacity_retention`` (h_Q) and resistance growth (h_R) are
    separate health quantities. Health is frozen within a race episode.
    """

    capacity_ah: float = 1.8
    capacity_retention: float = 1.0
    resistance_ohm: float = 0.02
    resistance_temp_coeff_per_k: float = 0.0
    resistance_floor_ohm: float = 0.005
    ocv_min_v: float = 550.0
    ocv_slope_v: float = 250.0
    max_discharge_current_a: float = 700.0
    max_charge_current_a: float = 500.0
    min_voltage_v: float = 480.0
    max_voltage_v: float = 900.0
    soc_min: float = 0.05
    soc_max: float = 0.95
    soc_initial: float = 0.70
    thermal_capacity_j_per_k: float = 90_000.0
    cooling_w_per_k: float = 60.0
    coolant_temp_k: float = KELVIN_OFFSET + 30.0
    max_temp_k: float = KELVIN_OFFSET + 70.0
    aux_power_w: float = 5_000.0

    @property
    def capacity_c(self) -> float:
        from .units import AH_TO_COULOMB

        return self.capacity_ah * self.capacity_retention * AH_TO_COULOMB


@dataclass
class BatteryState:
    soc: float
    temp_k: float
    charge_throughput_c: float = 0.0

    def copy(self) -> "BatteryState":
        return BatteryState(self.soc, self.temp_k, self.charge_throughput_c)


@dataclass
class VehicleState:
    progress_m: float
    speed_mps: float
    fuel_kg: float
    battery: BatteryState
    lateral_m: float = 0.0
    tyres: "TyreSetState | None" = None

    def copy(self) -> "VehicleState":
        return VehicleState(
            self.progress_m,
            self.speed_mps,
            self.fuel_kg,
            self.battery.copy(),
            self.lateral_m,
            self.tyres.copy() if self.tyres is not None else None,
        )


@dataclass(frozen=True)
class VehicleParams:
    """Declared reference car model. Not a Haas digital twin."""

    mass_kg: float = 798.0
    max_engine_force_n: float = 6_500.0
    max_brake_force_n: float = 20_000.0
    drag_area_m2: float = 1.50
    air_density_kg_m3: float = 1.225
    rolling_resistance: float = 0.015
    downforce_coeff: float = 2.20
    mu_base: float = 1.60
    mgu_k_efficiency: float = 0.92
    fuel_burn_kg_per_s: float = 0.0


@dataclass
class Control:
    """A candidate control interval.

    ``target_speed_mps`` is the tracker's reference; the plant owns the actual
    engine/brake split and may saturate it. ``lateral_target_m`` is the
    kinematically tracked lateral offset from the centreline.
    """

    family: ActionFamily
    p_k_dc_w: float
    target_speed_mps: float
    horizon_s: float = 1.0
    lateral_target_m: float = 0.0
    overtake: bool = False


@dataclass(frozen=True)
class TrackSample:
    s_m: float
    curvature_1_per_m: float
    grade_rad: float = 0.0
    width_m: float = 14.0


@dataclass(frozen=True)
class Track:
    length_m: float
    samples: tuple[TrackSample, ...]

    def curvature_at(self, s_m: float) -> float:
        return _interp(s_m, self.samples, lambda t: t.curvature_1_per_m)

    def grade_at(self, s_m: float) -> float:
        return _interp(s_m, self.samples, lambda t: t.grade_rad)

    def width_at(self, s_m: float) -> float:
        return _interp(s_m, self.samples, lambda t: t.width_m)


def _interp(s_m: float, samples: tuple[TrackSample, ...], get) -> float:
    if not samples:
        return 0.0
    n = len(samples)
    if n == 1:
        return get(samples[0])
    # samples are evenly spaced over [0, length]; allow wrap for lap tracks.
    span = samples[-1].s_m if samples[-1].s_m > 0 else 1.0
    x = (s_m % (span + (samples[1].s_m - samples[0].s_m))) if span > 0 else 0.0
    idx = 0
    while idx < n - 2 and samples[idx + 1].s_m <= x:
        idx += 1
    a, b = samples[idx], samples[idx + 1]
    if b.s_m <= a.s_m:
        return get(a)
    t = (x - a.s_m) / (b.s_m - a.s_m)
    return get(a) * (1.0 - t) + get(b) * t


def combined_drag_force(speed_mps: float, vehicle: VehicleParams) -> float:
    return 0.5 * vehicle.air_density_kg_m3 * vehicle.drag_area_m2 * speed_mps**2


def downforce_n(speed_mps: float, vehicle: VehicleParams) -> float:
    return vehicle.downforce_coeff * speed_mps**2


def normal_load_n(speed_mps: float, vehicle: VehicleParams, mass_kg: float) -> float:
    return mass_kg * 9.80665 + downforce_n(speed_mps, vehicle)


def cornering_speed_limit_mps(
    s_m: float, track: Track, vehicle: VehicleParams, mass_kg: float
) -> float:
    """Largest speed at which lateral demand fits the grip envelope."""
    kappa = abs(track.curvature_at(s_m))
    if kappa < 1e-9:
        return 200.0
    # mu * F_z = m v^2 kappa  =>  v = sqrt(mu*F_z/(m*kappa)); F_z depends on v^2.
    # Solve iteratively because downforce raises F_z with speed.
    v = 50.0
    for _ in range(20):
        fz = normal_load_n(v, vehicle, mass_kg)
        v_new = math.sqrt(vehicle.mu_base * fz / (mass_kg * kappa))
        if abs(v_new - v) < 1e-4:
            return v_new
        v = v_new
    return v
