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


def test_level1_attaches_mpc_action_to_driver_cue():
    command, result = FastExecutionController().track_zone(
        lambda_kin=-0.2, lambda_b=1.0, pedal_pct=100,
        target_speed_kmh=300, current_speed_kmh=250, energy=70,
    )
    assert result.success
    assert command.mpc_power_fraction == result.power_fraction
