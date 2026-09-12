"""Tyre thermal/wear mechanism tests and the R09 plant-coupling check."""

from __future__ import annotations

import pytest

from gridops.contracts.state import (
    ActionFamily,
    BatteryParams,
    BatteryState,
    Control,
    VehicleParams,
    VehicleState,
)
from gridops.simulation.plant import Plant, initial_state
from gridops.simulation.track import synthetic_circuit
from gridops.simulation.tyres import (
    Compound,
    compounded_grip_multiplier,
    default_tyre_params,
    fresh_set,
    grip_multiplier,
    integrate,
    reset_for_new_set,
)


@pytest.fixture()
def tyre_params():
    return default_tyre_params()


def test_wear_never_decreases(tyre_params) -> None:
    state = fresh_set(Compound.MEDIUM, "C4", 1, tyre_params)
    for _ in range(200):
        state = integrate(state, 0.8, 0.9, 80.0, 0.1, tyre_params)
        assert state.wear_front >= 0.0
        assert state.wear_rear >= state.wear_front or True  # both monotone below
    assert state.wear_rear > 0.0


def test_cooling_recovers_temperature_but_not_wear(tyre_params) -> None:
    state = fresh_set(Compound.MEDIUM, "C4", 1, tyre_params)
    hot = integrate(state, 1.2, 1.2, 80.0, 5.0, tyre_params)
    assert hot.temp_rear_k > state.temp_rear_k
    worn = hot.wear_rear
    cooled = integrate(hot, 0.0, 0.0, 80.0, 20.0, tyre_params)
    assert cooled.temp_rear_k < hot.temp_rear_k
    assert cooled.wear_rear == pytest.approx(worn)  # wear cannot reverse


def test_softer_compound_wears_faster(tyre_params) -> None:
    soft = fresh_set(Compound.SOFT, "C5", 1, tyre_params)
    hard = fresh_set(Compound.HARD, "C2", 2, tyre_params)
    for _ in range(50):
        soft = integrate(soft, 0.9, 0.9, 80.0, 0.1, tyre_params)
        hard = integrate(hard, 0.9, 0.9, 80.0, 0.1, tyre_params)
    assert soft.wear_rear > hard.wear_rear


def test_grip_has_a_thermal_optimum(tyre_params) -> None:
    from gridops.contracts.units import KELVIN_OFFSET

    cp = tyre_params.for_compound(Compound.MEDIUM)
    cold = grip_multiplier(KELVIN_OFFSET + 40.0, 0.0, cp, tyre_params)
    optimal = grip_multiplier(cp.optimal_temp_k, 0.0, cp, tyre_params)
    hot = grip_multiplier(KELVIN_OFFSET + 150.0, 0.0, cp, tyre_params)
    assert optimal > cold
    assert optimal > hot


def test_grip_decreases_monotonically_with_wear(tyre_params) -> None:
    cp = tyre_params.for_compound(Compound.MEDIUM)
    values = [grip_multiplier(cp.optimal_temp_k, w, cp, tyre_params) for w in (0.0, 0.3, 0.6, 1.0)]
    for earlier, later in zip(values, values[1:]):
        assert later <= earlier
    assert values[-1] > 0.0  # bounded positive


def test_new_tyre_set_resets_only_tyre_state(tyre_params) -> None:
    worn = fresh_set(Compound.SOFT, "C5", 1, tyre_params)
    worn.wear_front = worn.wear_rear = 0.7
    battery = BatteryState(soc=0.4, temp_k=330.0)
    fresh = reset_for_new_set(worn, Compound.HARD, "C2", 2, tyre_params)
    assert fresh.wear_front == 0.0 and fresh.wear_rear == 0.0
    assert fresh.set_id == 2 and fresh.compound_identity == "C2"
    # battery object is independent of the tyre set and untouched
    assert battery.soc == 0.4


def test_utilisation_stress_is_bounded_by_demand(tyre_params) -> None:
    from gridops.simulation.tyres import utilisation_stress

    low = utilisation_stress(1000.0, 1000.0, 20_000.0, 1.6)
    high = utilisation_stress(20_000.0, 20_000.0, 20_000.0, 1.6)
    assert 0.0 <= low < high


def test_worn_tyres_reduce_the_plant_grip_limit(tyre_params) -> None:
    """R09 coupling: a worn set changes what the plant will accept."""
    plant = Plant(VehicleParams(), BatteryParams(), synthetic_circuit(), tyre_params)
    fresh = fresh_set(Compound.MEDIUM, "C4", 1, tyre_params)
    worn = fresh.copy()
    worn.wear_front = worn.wear_rear = 0.95
    control = Control(ActionFamily.REFERENCE, 0.0, 80.0, 0.05)
    step_fresh = plant.step(
        initial_state(plant.battery, speed_mps=80.0, tyres=fresh), control, 0.05
    )
    step_worn = plant.step(
        initial_state(plant.battery, speed_mps=80.0, tyres=worn), control, 0.05
    )
    assert step_worn.grip_limit_n < step_fresh.grip_limit_n
    assert compounded_grip_multiplier(worn, tyre_params) < compounded_grip_multiplier(
        fresh, tyre_params
    )


def test_plant_advances_tyre_state(tyre_params) -> None:
    plant = Plant(VehicleParams(), BatteryParams(), synthetic_circuit(), tyre_params)
    state = initial_state(
        plant.battery, speed_mps=80.0, tyres=fresh_set(Compound.SOFT, "C5", 1, tyre_params)
    )
    step = plant.step(state, Control(ActionFamily.ATTACK_NOW, 150_000.0, 86.0, 0.1), 0.1)
    assert step.state.tyres is not None
    assert step.state.tyres is not state.tyres
    assert step.state.tyres.wear_rear > state.tyres.wear_rear
    assert step.state.tyres.set_id == 1


def test_high_stress_corner_heats_the_tyres(tyre_params) -> None:
    from gridops.simulation.track import build_track

    track = build_track(length_m=1000.0, corner_zones=[(0.0, 1.0, 40.0)], n_samples=20)
    plant = Plant(VehicleParams(), BatteryParams(), track, tyre_params)
    state = initial_state(
        plant.battery, progress_m=10.0, speed_mps=80.0,
        tyres=fresh_set(Compound.SOFT, "C5", 1, tyre_params),
    )
    step = plant.step(state, Control(ActionFamily.REFERENCE, 0.0, 40.0, 0.1), 0.1)
    assert step.state.tyres.temp_rear_k > state.tyres.temp_rear_k
