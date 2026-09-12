"""One-resistance electrothermal battery with signed energy accounting.

Model (declared reduction, not an identified F1 pack)::

    dz/dt = -I / Q_C                     (I discharge-positive)
    V     = U_oc(z) - I R(T)
    P_term = V I = P_K,dc + P_aux,dc
    C_th dT/dt = I^2 R - H (T - T_coolant)

Chemical stored energy for the frozen-capacity reference-OCV model::

    E_chem(z) = Q_C * integral_{z_min}^{z} U_oc(q) dq
    dE_chem/dt = -U_oc I = -(P_term + I^2 R)

The last identity is the conservation test. MGU-K DC counters, battery-terminal
energy and chemical energy are distinct accounting roles; internal resistance
loss is counted exactly once.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..contracts.state import (
    BatteryParams,
    BatteryState,
    SaturationReason,
)


@dataclass(frozen=True)
class TerminalPowerResult:
    power_w: float
    current_a: float
    voltage_v: float
    open_circuit_v: float
    resistance_ohm: float
    saturated: bool
    reasons: tuple[SaturationReason, ...]

    @property
    def internal_loss_w(self) -> float:
        return self.current_a**2 * self.resistance_ohm


def open_circuit_voltage(state: BatteryState, params: BatteryParams) -> float:
    return params.ocv_min_v + params.ocv_slope_v * state.soc


def resistance(state: BatteryState, params: BatteryParams) -> float:
    """Positive resistance map. Linear temperature dependence is a declared
    synthetic assumption, not a fitted cell law; coefficient defaults to zero."""
    base = params.resistance_ohm
    if params.resistance_temp_coeff_per_k:
        base = base * (
            1.0 + params.resistance_temp_coeff_per_k
            * (state.temp_k - params.coolant_temp_k)
        )
    return max(params.resistance_floor_ohm, base)


def max_transferable_power_w(state: BatteryState, params: BatteryParams) -> float:
    u = open_circuit_voltage(state, params)
    r = resistance(state, params)
    if r <= 0.0:
        return float("inf")
    return u * u / (4.0 * r)


def solve_terminal_power(
    requested_power_w: float,
    state: BatteryState,
    params: BatteryParams,
    dt_s: float,
) -> TerminalPowerResult:
    """Return the physically admissible terminal power closest to the request.

    An inadmissible request is saturated and the binding reason is recorded.
    SOC headroom over ``dt_s`` is enforced *before* integration so SOC is never
    clipped after the fact.
    """
    u = open_circuit_voltage(state, params)
    r = resistance(state, params)
    reasons: list[SaturationReason] = []

    p_req = requested_power_w
    if r > 1e-12:
        disc = u * u - 4.0 * r * p_req
        if disc < 0.0:
            # discharge beyond the maximum power transfer point.
            p_req = u * u / (4.0 * r)
            disc = 0.0
            reasons.append(SaturationReason.POWER_LIMIT)
        i = (u - math.sqrt(disc)) / (2.0 * r)
    else:
        i = p_req / u

    # independent current bounds, each with a reason.
    upper: list[tuple[float, SaturationReason]] = [
        (params.max_discharge_current_a, SaturationReason.CURRENT_LIMIT)
    ]
    lower: list[tuple[float, SaturationReason]] = [
        (-params.max_charge_current_a, SaturationReason.CURRENT_LIMIT)
    ]
    if r > 1e-12:
        upper.append(((u - params.min_voltage_v) / r, SaturationReason.VOLTAGE_LIMIT))
        lower.append(((u - params.max_voltage_v) / r, SaturationReason.VOLTAGE_LIMIT))

    q = params.capacity_c
    if dt_s > 1e-12:
        upper.append(
            (((state.soc - params.soc_min) * q) / dt_s, SaturationReason.SOC_FLOOR)
        )
        lower.append(
            (((state.soc - params.soc_max) * q) / dt_s, SaturationReason.SOC_CEILING)
        )

    if state.temp_k >= params.max_temp_k and r > 1e-12:
        cooling = params.cooling_w_per_k * max(0.0, state.temp_k - params.coolant_temp_k)
        upper.append((math.sqrt((cooling + 1.0) / r), SaturationReason.THERMAL_LIMIT))

    i_hi, reason_hi = min(upper, key=lambda item: item[0])
    i_lo, reason_lo = max(lower, key=lambda item: item[0])

    i_act = min(max(i, i_lo), i_hi)
    if i_act > i + 1e-9:
        reasons.append(reason_lo)
    elif i_act < i - 1e-9:
        reasons.append(reason_hi)

    v = u - i_act * r
    p_act = v * i_act
    # deduplicate while preserving order
    seen: list[SaturationReason] = []
    for reason in reasons:
        if reason not in seen:
            seen.append(reason)
    return TerminalPowerResult(
        power_w=p_act,
        current_a=i_act,
        voltage_v=v,
        open_circuit_v=u,
        resistance_ohm=r,
        saturated=bool(seen),
        reasons=tuple(seen),
    )


def integrate(
    state: BatteryState, current_a: float, dt_s: float, params: BatteryParams
) -> BatteryState:
    """Advance charge and thermal state. No post-hoc SOC clipping."""
    q = params.capacity_c
    soc_new = state.soc - current_a * dt_s / q
    heat_w = current_a * current_a * resistance(state, params)
    cooling_w = params.cooling_w_per_k * (state.temp_k - params.coolant_temp_k)
    temp_new = state.temp_k + (heat_w - cooling_w) * dt_s / params.thermal_capacity_j_per_k
    return BatteryState(
        soc=soc_new,
        temp_k=temp_new,
        charge_throughput_c=state.charge_throughput_c + abs(current_a) * dt_s,
    )


def chemical_energy_j(state: BatteryState, params: BatteryParams) -> float:
    """Model-defined internal stored energy relative to ``soc_min`` (joules)."""
    q = params.capacity_c
    z, z_min = state.soc, params.soc_min
    u0, u1 = params.ocv_min_v, params.ocv_slope_v
    return q * (u0 * (z - z_min) + 0.5 * u1 * (z * z - z_min * z_min))


def usable_energy_j(state: BatteryState, params: BatteryParams) -> float:
    """Monotone non-decreasing in SOC. Used as the resource continuation input."""
    return chemical_energy_j(state, params)


def soc_for_chemical_energy_j(energy_j: float, params: BatteryParams) -> float:
    """Invert :func:`chemical_energy_j` for the linear-OCV model."""
    q = params.capacity_c
    u0, u1 = params.ocv_min_v, params.ocv_slope_v
    z_min = params.soc_min
    # 0.5 u1 z^2 + u0 z - (E/Q + u0 z_min + 0.5 u1 z_min^2) = 0
    c = energy_j / q + u0 * z_min + 0.5 * u1 * z_min * z_min
    if abs(u1) < 1e-12:
        return c / u0
    disc = u0 * u0 + 2.0 * u1 * c
    return (-u0 + math.sqrt(max(disc, 0.0))) / u1
