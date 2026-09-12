"""Action responsiveness, grip and energy behaviour of the plant."""

from __future__ import annotations

import pytest

from gridops.contracts.state import (
    ActionFamily,
    BatteryParams,
    BatteryState,
    Control,
    SaturationReason,
    VehicleParams,
    VehicleState,
)
from gridops.simulation.plant import Plant, initial_state
from gridops.simulation.track import build_track, synthetic_circuit


@pytest.fixture()
def plant() -> Plant:
    return Plant(VehicleParams(), BatteryParams(), synthetic_circuit())


def _control(power: float, target: float, family=ActionFamily.ATTACK_NOW) -> Control:
    return Control(family=family, p_k_dc_w=power, target_speed_mps=target, horizon_s=0.5)


def test_progress_advances(plant: Plant) -> None:
    start = initial_state(plant.battery, progress_m=0.0, speed_mps=80.0)
    step = plant.step(start, _control(100_000.0, 80.0), dt_s=0.5)
    assert step.state.progress_m > start.progress_m
    assert step.state.speed_mps > 0.0


def test_action_changes_future_motion(plant: Plant) -> None:
    """R01: a feasible action must change the future state."""
    start = initial_state(plant.battery, progress_m=0.0, speed_mps=80.0)
    low = plant.step(start, _control(0.0, 100.0), dt_s=0.5)
    high = plant.step(start, _control(200_000.0, 100.0), dt_s=0.5)
    assert high.state.speed_mps > low.state.speed_mps + 0.5
    assert high.state.progress_m > low.state.progress_m


def test_deployment_drains_battery(plant: Plant) -> None:
    start = initial_state(plant.battery, speed_mps=80.0)
    step = plant.step(start, _control(150_000.0, 80.0), dt_s=0.5)
    assert step.state.battery.soc < start.battery.soc
    assert step.current_a > 0.0


def test_recovery_charges_battery(plant: Plant) -> None:
    start = initial_state(plant.battery, speed_mps=80.0)
    start.battery.soc = 0.5
    step = plant.step(start, _control(-150_000.0, 80.0), dt_s=0.5)
    assert step.state.battery.soc > start.battery.soc
    assert step.current_a < 0.0


def test_zero_power_coasts_down(plant: Plant) -> None:
    start = initial_state(plant.battery, speed_mps=80.0)
    step = plant.step(start, _control(0.0, 0.0), dt_s=0.5)
    assert step.state.speed_mps < start.speed_mps


def test_steady_cruise_is_stationary(plant: Plant) -> None:
    start = initial_state(plant.battery, speed_mps=80.0)
    step = plant.step(start, _control(100_000.0, 80.0), dt_s=0.5)
    assert step.state.speed_mps == pytest.approx(80.0, rel=1e-6)


def test_grip_limit_is_recorded_in_a_tight_corner() -> None:
    track = build_track(length_m=1_000.0, corner_zones=[(0.0, 1.0, 50.0)], n_samples=20)
    plant = Plant(VehicleParams(), BatteryParams(), track)
    start = initial_state(plant.battery, progress_m=10.0, speed_mps=80.0)
    step = plant.step(start, _control(0.0, 40.0), dt_s=0.1)
    assert step.grip_violation_n > 0.0
    assert SaturationReason.GRIP_LIMIT in step.saturation
    assert abs(step.longitudinal_force_n) <= 1e-9


def test_requested_and_realized_power_are_separated(plant: Plant) -> None:
    start = initial_state(plant.battery, speed_mps=80.0)
    step = plant.step(start, _control(10_000_000.0, 80.0), dt_s=0.02)
    assert step.requested_p_k_dc_w == 10_000_000.0
    assert step.realized_p_k_dc_w < step.requested_p_k_dc_w
    assert step.saturation
