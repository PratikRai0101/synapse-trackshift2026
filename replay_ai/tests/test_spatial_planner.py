from src.intelligence.spatial_planner import TrackSample, SpatialTrajectoryPlanner


def test_spatial_reference_is_cone_feasible_across_track():
    track = [TrackSample(0, 0.001), TrackSample(50, 0.01), TrackSample(100, 0.04)]
    reference = SpatialTrajectoryPlanner().plan(track, 300, speed_gain_kmh=10)
    assert len(reference.speeds_kmh) == 3
    assert len(reference.kinetic_costates) == 3
    assert reference.envelope.feasible
    assert reference.envelope.max_residual <= 1e-8
    assert reference.speeds_kmh[-1] < reference.speeds_kmh[0]


def test_empty_track_returns_valid_empty_profile():
    reference = SpatialTrajectoryPlanner().plan([], 300)
    assert reference.distances_m == ()
    assert reference.envelope.feasible
