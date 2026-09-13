from src.intelligence.race_physics import CarPose, PassMonitor


def test_longitudinal_separation_is_not_contact_in_the_same_lane():
    result = PassMonitor().evaluate(CarPose("E", 90), CarPose("R", 100))
    assert not result.contact


def test_side_by_side_clearance_is_not_contact():
    result = PassMonitor().evaluate(CarPose("E", 100, -2), CarPose("R", 100, 2))
    assert not result.contact


def test_actual_overlap_is_contact():
    assert PassMonitor().evaluate(CarPose("E", 99), CarPose("R", 100)).contact


def test_same_lane_tunnelling_is_contact_even_if_endpoints_are_clear():
    monitor = PassMonitor()
    monitor.evaluate(CarPose("E", 90), CarPose("R", 100))
    assert monitor.evaluate(CarPose("E", 110), CarPose("R", 100)).contact
