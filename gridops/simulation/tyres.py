"""Tyre compound thermal state and irreversible wear.

Required model (spec section 5): one effective temperature and one wear proxy
per axle, with compound-specific parameter sets. The optional surface/bulk
split is not implemented.

::

    C_c dT/dt = chi_c P_heat - H_c (T - T_env)
    dw/dt     = k_c f_c(u) g_c(T) >= 0

Because the plant does not model slip, ``u`` is a declared dimensionless
**force-utilisation stress**, not measured contact-patch work. It is the
fraction of the available grip envelope currently demanded. Cooling may restore
thermal grip but can never reduce accumulated wear.

Compound HARD/MEDIUM/SOFT are event-relative labels; the actual compound
identity (for example ``C3``) is stored separately.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum

from ..contracts.units import KELVIN_OFFSET


class Compound(str, Enum):
    HARD = "hard"
    MEDIUM = "medium"
    SOFT = "soft"


@dataclass
class TyreSetState:
    """Per-axle thermal and wear state belonging to one physical tyre set."""

    compound: Compound
    compound_identity: str
    set_id: int
    temp_front_k: float
    temp_rear_k: float
    wear_front: float = 0.0
    wear_rear: float = 0.0
    laps_used: float = 0.0

    def copy(self) -> "TyreSetState":
        return TyreSetState(
            compound=self.compound,
            compound_identity=self.compound_identity,
            set_id=self.set_id,
            temp_front_k=self.temp_front_k,
            temp_rear_k=self.temp_rear_k,
            wear_front=self.wear_front,
            wear_rear=self.wear_rear,
            laps_used=self.laps_used,
        )


@dataclass(frozen=True)
class CompoundParams:
    """Declared synthetic compound family, not Pirelli calibration."""

    grip_peak: float
    optimal_temp_k: float
    temp_width_k: float
    wear_rate_per_s: float
    wear_temp_sensitivity_per_k: float
    thermal_capacity_j_per_k: float
    cooling_w_per_k: float
    heat_reference_w: float


@dataclass(frozen=True)
class TyreParams:
    environment_temp_k: float = KELVIN_OFFSET + 35.0
    reference_speed_mps: float = 80.0
    heat_exponent: float = 2.0
    wear_penalty: float = 0.55
    min_grip_multiplier: float = 0.2
    fresh_temp_k: float = KELVIN_OFFSET + 80.0
    wear_rate_scale: float = 1.0
    compounds: dict[Compound, CompoundParams] = field(default_factory=dict)

    def for_compound(self, compound: Compound) -> CompoundParams:
        return self.compounds[compound]


def default_tyre_params() -> TyreParams:
    """Synthetic compound families. Softer = more grip, faster wear."""
    return TyreParams(
        compounds={
            Compound.HARD: CompoundParams(
                grip_peak=1.00,
                optimal_temp_k=KELVIN_OFFSET + 105.0,
                temp_width_k=35.0,
                wear_rate_per_s=1.2e-5,
                wear_temp_sensitivity_per_k=0.004,
                thermal_capacity_j_per_k=45_000.0,
                cooling_w_per_k=55.0,
                heat_reference_w=28_000.0,
            ),
            Compound.MEDIUM: CompoundParams(
                grip_peak=1.06,
                optimal_temp_k=KELVIN_OFFSET + 95.0,
                temp_width_k=28.0,
                wear_rate_per_s=2.0e-5,
                wear_temp_sensitivity_per_k=0.006,
                thermal_capacity_j_per_k=42_000.0,
                cooling_w_per_k=58.0,
                heat_reference_w=30_000.0,
            ),
            Compound.SOFT: CompoundParams(
                grip_peak=1.12,
                optimal_temp_k=KELVIN_OFFSET + 88.0,
                temp_width_k=22.0,
                wear_rate_per_s=3.4e-5,
                wear_temp_sensitivity_per_k=0.009,
                thermal_capacity_j_per_k=38_000.0,
                cooling_w_per_k=62.0,
                heat_reference_w=32_000.0,
            ),
        }
    )


def fresh_set(
    compound: Compound,
    compound_identity: str,
    set_id: int,
    params: TyreParams,
) -> TyreSetState:
    return TyreSetState(
        compound=compound,
        compound_identity=compound_identity,
        set_id=set_id,
        temp_front_k=params.fresh_temp_k,
        temp_rear_k=params.fresh_temp_k,
        wear_front=0.0,
        wear_rear=0.0,
        laps_used=0.0,
    )


def utilisation_stress(
    longitudinal_force_n: float,
    lateral_force_n: float,
    normal_load_n: float,
    mu: float,
) -> float:
    """Dimensionless force-utilisation stress in ``[0, ~1.5]``.

    This is a surrogate for grip demand, not measured contact-patch work.
    """
    capacity = max(1.0, mu * normal_load_n)
    return math.hypot(longitudinal_force_n, lateral_force_n) / capacity


def heat_input_w(
    stress: float, speed_mps: float, compound_params: CompoundParams, params: TyreParams
) -> float:
    speed_factor = 0.5 + 0.5 * max(0.0, speed_mps) / params.reference_speed_mps
    return compound_params.heat_reference_w * (max(0.0, stress) ** params.heat_exponent) * speed_factor


def grip_multiplier(
    temp_k: float, wear: float, compound_params: CompoundParams, params: TyreParams
) -> float:
    """Bounded positive grip map: thermal optimum times monotone wear penalty."""
    z = (temp_k - compound_params.optimal_temp_k) / compound_params.temp_width_k
    thermal = math.exp(-0.5 * z * z)
    wear_factor = max(params.min_grip_multiplier, 1.0 - params.wear_penalty * max(0.0, wear))
    return compound_params.grip_peak * thermal * wear_factor


def integrate(
    state: TyreSetState,
    stress_front: float,
    stress_rear: float,
    speed_mps: float,
    dt_s: float,
    params: TyreParams,
) -> TyreSetState:
    """Advance thermal state and non-decreasing wear. No post-hoc clipping."""
    cp = params.for_compound(state.compound)
    if dt_s <= 0.0:
        raise ValueError("dt_s must be positive")

    def _next_temp(temp_k: float, stress: float) -> float:
        heat = heat_input_w(stress, speed_mps, cp, params)
        cooling = cp.cooling_w_per_k * (temp_k - params.environment_temp_k)
        return temp_k + (heat - cooling) * dt_s / cp.thermal_capacity_j_per_k

    def _next_wear(wear: float, stress: float, temp_k: float) -> float:
        temperature_factor = max(
            0.0, 1.0 + cp.wear_temp_sensitivity_per_k * (temp_k - params.environment_temp_k)
        )
        rate = (
            cp.wear_rate_per_s
            * params.wear_rate_scale
            * max(0.0, stress) ** params.heat_exponent
            * temperature_factor
        )
        return min(1.0, max(wear, wear + rate * dt_s))

    new_state = TyreSetState(
        compound=state.compound,
        compound_identity=state.compound_identity,
        set_id=state.set_id,
        temp_front_k=_next_temp(state.temp_front_k, stress_front),
        temp_rear_k=_next_temp(state.temp_rear_k, stress_rear),
        wear_front=_next_wear(state.wear_front, stress_front, state.temp_front_k),
        wear_rear=_next_wear(state.wear_rear, stress_rear, state.temp_rear_k),
        laps_used=state.laps_used,
    )
    return new_state


def compounded_grip_multiplier(state: TyreSetState, params: TyreParams) -> float:
    """Conservative single multiplier for the combined envelope: the worse axle."""
    cp = params.for_compound(state.compound)
    front = grip_multiplier(state.temp_front_k, state.wear_front, cp, params)
    rear = grip_multiplier(state.temp_rear_k, state.wear_rear, cp, params)
    return min(front, rear)


def reset_for_new_set(
    state: TyreSetState, new_compound: Compound, compound_identity: str, set_id: int, params: TyreParams
) -> TyreSetState:
    """Fit a new set: reset thermal and wear priors, keep nothing else.

    Battery state, fuel mass and driver context are not part of this object and
    are therefore untouched by a tyre change.
    """
    return fresh_set(new_compound, compound_identity, set_id, params)
