import pytest

from src.intelligence.socp_envelope import SOCPPerformanceEnvelope


def test_socp_profile_respects_second_order_cone():
    solver = SOCPPerformanceEnvelope()
    profile = solver.solve([0, 10], [300, 350], [0.02, 0.08], [8, 8])
    assert profile.feasible
    assert profile.max_residual <= 1e-8
    assert profile.points[1].speed_kmh < 350
    for point in profile.points:
        assert (point.longitudinal_accel ** 2 + point.lateral_accel ** 2) ** 0.5 <= point.cone_radius + 1e-8


def test_socp_rejects_mismatched_grids():
    with pytest.raises(ValueError):
        SOCPPerformanceEnvelope().solve([0], [300, 301], [0.01])


def test_empty_socp_profile_is_valid():
    profile = SOCPPerformanceEnvelope().solve([], [], [])
    assert profile.feasible
    assert profile.points == ()
