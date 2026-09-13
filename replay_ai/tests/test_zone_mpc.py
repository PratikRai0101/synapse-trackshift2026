from src.intelligence.control_layers import FastExecutionController
from src.intelligence.zone_mpc import ZoneMPC, ZoneMPCConfig


def test_zone_mpc_returns_bounded_first_action_and_reserves_energy():
    result = ZoneMPC().solve(250.0, 70.0, 300.0)
    assert result.success
    assert 0.0 <= result.power_fraction <= 1.0
    assert all(energy >= 5.0 - 1e-8 for energy in result.predicted_energy)
    assert all(speed <= 300.0 + 1e-8 for speed in result.predicted_speeds)


def test_zone_mpc_zeroes_power_when_already_over_speed_zone():
    result = ZoneMPC().solve(320.0, 70.0, 250.0)
    assert result.success
    assert result.power_fraction == 0.0


def test_actuator_aware_mpc_exposes_regen_brake_thermal_and_residuals():
    config = ZoneMPCConfig(battery_temperature=70.0)
    result = ZoneMPC(config).solve(320.0, 70.0, 250.0)
    assert result.success
    assert result.brake_fraction >= 0.0
    assert result.regen_fraction >= 0.0
    assert len(result.predicted_temperatures) == config.horizon
    assert result.max_constraint_residual <= 1e-8


def test_mpc_rate_limits_first_power_command():
    controller = ZoneMPC(ZoneMPCConfig(max_power_rate_per_s=1.0))
    controller.previous_power = 0.0
    result = controller.solve(200.0, 70.0, 350.0)
    assert result.success
    assert result.power_fraction <= 0.01 + 1e-8


def test_level1_attaches_mpc_action_to_driver_cue():
    command, result = FastExecutionController().track_zone(
        lambda_kin=-0.2, lambda_b=1.0, pedal_pct=100,
        target_speed_kmh=300, current_speed_kmh=250, energy=70,
    )
    assert result.success
    assert command.mpc_power_fraction == result.power_fraction


def test_power_bounds_carry_tactical_intent_into_execution():
    """Level 2 intent must reach the plant when physics allows it."""
    deploy = ZoneMPC(ZoneMPCConfig(max_power_rate_per_s=20.0)).solve(
        275.0, 70.0, 320.0, power_bounds=(0.7, 1.0), elapsed_s=0.1)
    assert deploy.success
    assert deploy.power_fraction >= 0.7

    coast = ZoneMPC(ZoneMPCConfig(max_power_rate_per_s=20.0)).solve(
        275.0, 70.0, 320.0, power_bounds=(0.0, 0.1), elapsed_s=0.1)
    assert coast.success
    assert coast.power_fraction <= 0.1


def test_deployment_floor_is_clamped_when_the_brake_cannot_cancel_it():
    """A contradictory request returns bounded power, never a failed solve."""
    result = ZoneMPC(ZoneMPCConfig(max_power_rate_per_s=20.0)).solve(
        275.0, 70.0, 250.0, power_bounds=(0.7, 1.0))
    assert result.success
    assert result.power_fraction <= 0.7


def test_power_floor_is_clamped_to_what_the_rate_limit_can_reach():
    """An aggressive request must not make the LP infeasible."""
    result = ZoneMPC(ZoneMPCConfig(max_power_rate_per_s=1.0)).solve(
        275.0, 70.0, 320.0, power_bounds=(1.0, 1.0))
    assert result.success
    assert result.power_fraction <= 0.01 + 1e-9
