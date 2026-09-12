from src.intelligence.socp_envelope import SOCPPerformanceEnvelope


def test_socp_profile_respects_second_order_cone():
    solver = SOCPPerformanceEnvelope()
    profile = solver.solve([0, 10], [300, 350], [0.02, 0.08], [8, 8])
    assert profile.feasible
    assert profile.max_residual <= 1e-8
    for point in profile.points:
        assert (point.longitudinal_accel ** 2 + point.lateral_accel ** 2) ** 0.5 <= point.cone_radius + 1e-8


def test_socp_rejects_non_monotonic_distance_grid():
    try:
        SOCPPerformanceEnvelope().solve([0, 0], [300, 300], [0.01, 0.01])
    except ValueError as error:
        assert "strictly increasing" in str(error)
    else:
        raise AssertionError("expected distance-grid validation")


def test_socp_tracks_energy_and_reserve_residual():
    profile = SOCPPerformanceEnvelope().solve(
        [0, 100, 200], [200, 200, 200], [0.001, 0.001, 0.001],
        initial_energy=1.0, reserve_energy=0.9,
    )
    assert profile.energy_remaining <= 1.0
    assert not profile.reserve_feasible
    assert profile.points[-1].reserve_residual > 0.0
