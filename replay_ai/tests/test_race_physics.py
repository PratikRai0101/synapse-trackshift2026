from src.intelligence.race_physics import (
    CarPose, DirtyAirModel, PassMonitor, PitStrategy, TrackGeometry,
)


def test_dirty_air_reduces_grip_inside_one_second():
    model = DirtyAirModel(max_grip_loss=0.2)
    assert model.grip_multiplier(0.5) < model.grip_multiplier(2.0)
    assert model.grip_multiplier(2.0) == 1.0


def test_pass_requires_clearance_and_order_change():
    monitor = PassMonitor()
    rival = CarPose("R", 100.0, lateral_m=0.0)
    ego_behind = CarPose("E", 94.0, lateral_m=2.0)
    first = monitor.evaluate(ego_behind, rival)
    assert not first.legal
    ego_ahead = CarPose("E", 106.0, lateral_m=3.0)
    second = monitor.evaluate(ego_ahead, rival)
    assert second.legal
    assert not second.contact


def test_contact_is_not_a_legal_pass():
    monitor = PassMonitor()
    rival = CarPose("R", 100.0, lateral_m=0.0)
    monitor.evaluate(CarPose("E", 94.0, 0.0), rival)
    result = monitor.evaluate(CarPose("E", 106.0, 0.0), rival)
    assert not result.legal
    assert result.contact


def test_pit_strategy_responds_to_wear_and_fuel():
    strategy = PitStrategy()
    assert strategy.decide(0.9, 10, 10).pit
    assert strategy.decide(0.2, 1, 5).pit
    assert not strategy.decide(0.2, 10, 2).pit


def test_declared_car_envelope_is_the_one_the_viewer_renders():
    """Lock the constant both sides share.

    The 3D viewer's mesh must fit this envelope
    (`replay/viewer3d/web/src/scene/carParts.ts`, `CAR_DIMENSIONS`). Contact is
    decided from these metres, so a change here needs the matching mesh change,
    otherwise the viewer can draw a touch the simulator does not model.
    """
    pose = CarPose("EGO", 0.0)
    assert (pose.length_m, pose.width_m) == (5.5, 2.0)


def test_contact_uses_the_declared_envelope_not_a_larger_one():
    monitor = PassMonitor(TrackGeometry(length_m=5000.0, width_m=2.0))
    # 2.4 m apart laterally: outside two 2.0 m cars side by side.
    clear = monitor.evaluate(CarPose("E", 100.0, -1.2), CarPose("R", 100.0, 1.2))
    assert not clear.contact
    # 1.6 m apart: inside the combined width, so the models would overlap.
    tight = monitor.evaluate(CarPose("E", 100.0, -0.8), CarPose("R", 100.0, 0.8))
    assert tight.contact
