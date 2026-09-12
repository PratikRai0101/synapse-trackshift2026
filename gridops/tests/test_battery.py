"""Battery accounting, saturation and conservation tests."""

from __future__ import annotations

import math

import pytest

from gridops.contracts.state import BatteryParams, BatteryState, SaturationReason
from gridops.simulation.battery import (
    chemical_energy_j,
    integrate,
    max_transferable_power_w,
    open_circuit_voltage,
    resistance,
    soc_for_chemical_energy_j,
    solve_terminal_power,
    usable_energy_j,
)


@pytest.fixture()
def params() -> BatteryParams:
    return BatteryParams()


@pytest.fixture()
def state(params: BatteryParams) -> BatteryState:
    return BatteryState(soc=0.70, temp_k=params.coolant_temp_k)


def test_ocv_is_monotone_in_soc(params: BatteryParams) -> None:
    lo = BatteryState(0.2, params.coolant_temp_k)
    hi = BatteryState(0.8, params.coolant_temp_k)
    assert open_circuit_voltage(hi, params) > open_circuit_voltage(lo, params)


def test_resistance_is_positive(params: BatteryParams) -> None:
    s = BatteryState(0.5, params.coolant_temp_k + 500.0)
    assert resistance(s, params) >= params.resistance_floor_ohm


def test_voltage_identity_terminal_plus_loss(params: BatteryParams, state: BatteryState) -> None:
    """U_oc * I == P_term + I^2 R, with internal loss counted exactly once."""
    result = solve_terminal_power(120_000.0, state, params, dt_s=0.02)
    lhs = result.open_circuit_v * result.current_a
    rhs = result.power_w + result.internal_loss_w
    assert lhs == pytest.approx(rhs, rel=1e-9, abs=1e-6)


def test_chemical_energy_derivative_matches_ocv(params: BatteryParams) -> None:
    """dE_chem/dz == Q_C * U_oc(z) for the linear-OCV reference model."""
    z = 0.6
    h = 1e-6
    e_hi = chemical_energy_j(BatteryState(z + h, params.coolant_temp_k), params)
    e_lo = chemical_energy_j(BatteryState(z - h, params.coolant_temp_k), params)
    derivative = (e_hi - e_lo) / (2 * h)
    expected = params.capacity_c * open_circuit_voltage(
        BatteryState(z, params.coolant_temp_k), params
    )
    assert derivative == pytest.approx(expected, rel=1e-6)


def test_charge_round_trip_inverts_energy(params: BatteryParams) -> None:
    s = BatteryState(0.42, params.coolant_temp_k)
    energy = usable_energy_j(s, params)
    assert soc_for_chemical_energy_j(energy, params) == pytest.approx(0.42, rel=1e-9)


def test_discharge_decreases_charge_and_charge_increases_it(params: BatteryParams) -> None:
    s = BatteryState(0.70, params.coolant_temp_k)
    discharged = integrate(s, current_a=200.0, dt_s=1.0, params=params)
    charged = integrate(s, current_a=-200.0, dt_s=1.0, params=params)
    assert discharged.soc < s.soc < charged.soc
    assert discharged.charge_throughput_c > 0.0


def test_resistive_heating_raises_temperature(params: BatteryParams) -> None:
    s = BatteryState(0.70, params.coolant_temp_k)
    after = integrate(s, current_a=300.0, dt_s=1.0, params=params)
    assert after.temp_k > s.temp_k


def test_cooling_without_heat_lowers_temperature(params: BatteryParams) -> None:
    s = BatteryState(0.70, params.coolant_temp_k + 20.0)
    after = integrate(s, current_a=0.0, dt_s=5.0, params=params)
    assert after.temp_k < s.temp_k


def test_current_limit_saturates_an_excessive_request(params: BatteryParams, state: BatteryState) -> None:
    huge = 50_000_000.0
    result = solve_terminal_power(huge, state, params, dt_s=0.02)
    assert result.saturated
    assert result.current_a <= params.max_discharge_current_a + 1e-9
    assert result.power_w <= max_transferable_power_w(state, params) + 1e-6


def test_soc_floor_is_respected_without_post_clipping(params: BatteryParams) -> None:
    near_floor = BatteryState(soc=params.soc_min + 1e-4, temp_k=params.coolant_temp_k)
    result = solve_terminal_power(200_000.0, near_floor, params, dt_s=1.0)
    assert SaturationReason.SOC_FLOOR in result.reasons
    after = integrate(near_floor, result.current_a, 1.0, params)
    assert after.soc >= params.soc_min - 1e-9


def test_soc_ceiling_is_respected_when_charging(params: BatteryParams) -> None:
    near_ceiling = BatteryState(soc=params.soc_max - 1e-4, temp_k=params.coolant_temp_k)
    result = solve_terminal_power(-200_000.0, near_ceiling, params, dt_s=1.0)
    assert SaturationReason.SOC_CEILING in result.reasons
    after = integrate(near_ceiling, result.current_a, 1.0, params)
    assert after.soc <= params.soc_max + 1e-9


def test_recovery_has_negative_current(params: BatteryParams, state: BatteryState) -> None:
    result = solve_terminal_power(-80_000.0, state, params, dt_s=0.02)
    assert result.current_a < 0.0
    assert result.power_w < 0.0
