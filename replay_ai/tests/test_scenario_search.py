from src.intelligence.control_layers import BoundedScenarioPlanner
from src.intelligence.hierarchical import FeatureExtractor, FortyStateHMM, RivalTelemetry
from src.intelligence.scenario_search import BoundedPOMCP, SearchConfig


def result():
    features = FeatureExtractor().update(RivalTelemetry(300, 100, 0, 0.8))
    return FortyStateHMM().update(features)


def test_search_is_deterministic_and_values_all_root_actions():
    config = SearchConfig(horizon=3, rollouts_per_action=20, seed=4)
    first = BoundedPOMCP(config).search(result(), gap_s=0.5, energy=70)
    second = BoundedPOMCP(config).search(result(), gap_s=0.5, energy=70)
    assert first == second
    assert set(first.values) == {"BURN", "HARVEST", "PROACTIVE TRAP"}
    assert first.rollouts == 60


def test_planner_exposes_search_values_and_keeps_safety_gate():
    plan = BoundedScenarioPlanner().plan(result(), 300, 0.5, 70)
    assert plan.search_values is not None
    assert plan.command in {"BURN", "HARVEST", "PROACTIVE TRAP"}
