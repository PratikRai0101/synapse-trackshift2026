from src.intelligence.control_layers import (
    BoundedScenarioPlanner, FastExecutionController, PerformanceEnvelope,
)
from src.intelligence.hierarchical import FeatureExtractor, FortyStateHMM, RivalTelemetry


def hmm_result():
    extractor = FeatureExtractor()
    hmm = FortyStateHMM()
    return hmm.update(extractor.update(RivalTelemetry(300, 100, 0, 0.8)))


def test_envelope_caps_speed_in_a_corner():
    point = PerformanceEnvelope().point(10.0, curvature=0.08, requested_speed_kmh=350)
    assert point.speed_limit_kmh < 350
    assert point.feasible
    assert point.longitudinal_accel_limit >= 0


def test_scenario_planner_returns_all_candidate_actions_and_profile():
    plan = BoundedScenarioPlanner().plan(hmm_result(), 300, 0.6, 70)
    assert plan.command in {"BURN", "HARVEST", "PROACTIVE TRAP"}
    assert len(plan.reference_speed_kmh) == 5
    assert {action.command for action in plan.action_scores} == {
        "BURN", "HARVEST", "PROACTIVE TRAP"
    }
    assert plan.envelope.feasible


def test_level1_respects_driver_pedal_in_grip_limited_region():
    controller = FastExecutionController()
    command = controller.command(-2.0, 0.5, pedal_pct=60, target_speed_kmh=250,
                                 current_speed_kmh=240)
    assert command.constrained
    assert command.electric_power_fraction == 0.0
    assert command.engine_power_fraction == 0.6


def test_level1_can_issue_regen_cue():
    command = FastExecutionController().command(-0.1, 1.0, 100, 200, 250)
    assert command.cue == "REGEN BRAKE"
    assert command.regen_fraction == 1.0
