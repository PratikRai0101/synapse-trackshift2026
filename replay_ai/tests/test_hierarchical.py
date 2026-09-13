import pytest

from src.intelligence.hierarchical import (
    ERSMode, FortyStateHMM, FeatureExtractor, MotorsportIntelligence, RivalTelemetry, STATES,
    SeasonLifecycleManager,
)


def test_hmm_has_exact_forty_states_and_normalized_belief():
    hmm = FortyStateHMM()
    assert len(STATES) == 40
    features = FeatureExtractor().update(RivalTelemetry(320, 100, 0, 0.8, 1.0))
    result = hmm.update(features)
    assert len(result.belief) == 40
    assert abs(sum(result.belief.values()) - 1.0) < 1e-9
    assert abs(sum(result.ers_probabilities.values()) - 1.0) < 1e-9
    assert set(result.ers_probabilities) == {m.value for m in ERSMode}


def test_feature_baseline_uses_prior_laps_in_the_same_sector():
    extractor = FeatureExtractor(window=5)
    extractor.update(RivalTelemetry(300, 100, 0, 1.0, sector=0, lap=1))
    extractor.update(RivalTelemetry(200, 100, 0, 1.0, sector=1, lap=1))
    # Moving to lap two seals lap one into the causal baseline.
    same_sector = extractor.update(
        RivalTelemetry(290, 100, 0, 1.0, sector=0, lap=2))
    assert same_sector.dv_baseline == -10.0
    assert same_sector.throttle_clip == 1.0
    other_sector = extractor.update(
        RivalTelemetry(200, 100, 0, 1.0, sector=1, lap=2))
    assert other_sector.dv_baseline == 0.0


def test_feature_extractor_measures_super_clip_duration():
    extractor = FeatureExtractor()
    # Seal lap one so sector 0 has a fast baseline in history.
    extractor.update(RivalTelemetry(320, 100, 0, 0.8, sector=0, lap=1, time_s=5.0))
    extractor.update(RivalTelemetry(320, 100, 0, 0.8, sector=0, lap=2, time_s=6.0))
    # Full throttle but far off the baseline: the clip now accumulates time.
    first = extractor.update(RivalTelemetry(290, 100, 0, 0.8, sector=0, lap=2, time_s=6.5))
    second = extractor.update(RivalTelemetry(290, 100, 0, 0.8, sector=0, lap=2, time_s=7.0))
    assert first.clip_seconds == 0.5
    assert second.clip_seconds == 1.0
    # Back on the baseline pace, the duration resets.
    cleared = extractor.update(RivalTelemetry(320, 100, 0, 0.8, sector=0, lap=2, time_s=7.5))
    assert cleared.clip_seconds == 0.0


def test_observation_updates_only_from_current_public_sample():
    model = MotorsportIntelligence()
    first = model.observe(RivalTelemetry(300, 100, 0, 1.0), own_speed_kmh=295)
    second = model.observe(RivalTelemetry(250, 100, 0, 0.9), own_speed_kmh=295)
    assert first.command in {"HARVEST", "BURN", "PROACTIVE TRAP"}
    assert second.command in {"HARVEST", "BURN", "PROACTIVE TRAP"}
    assert model.last_hmm is not None


def test_runtime_metrics_report_replanned_layers():
    model = MotorsportIntelligence()
    model.observe(RivalTelemetry(300, 100, 0, 1.0, lap=1), own_soc=60)
    metrics = model.runtime_metrics()

    assert "HMM" in metrics["replanned_layers"]
    assert "L2" in metrics["replanned_layers"]
    # No lap map artifact is loaded here, so Level 3 never replans.
    assert "L3" not in metrics["replanned_layers"]


def test_lifecycle_dp_can_choose_replacement_for_degraded_pack():
    decision = SeasonLifecycleManager(races=10).decide(soh=0.1, temperature=95)
    assert decision.replace
    assert decision.soh == 1.0


def test_belief_stays_a_valid_distribution_under_extreme_feature_errors():
    """Regression: a large gap swing underflowed every likelihood to zero.

    The old code did `total = sum(weighted) or 1.0`, which normalised an
    all-zero vector into an all-zero posterior. Downstream that raised
    "Total of weights must be greater than zero" inside the particle search and
    blanked the race-engineer panel for the rest of the session.
    """
    from src.intelligence.hierarchical import FortyStateHMM, RivalTelemetry

    hmm = FortyStateHMM()
    for dgap in (0.0, 0.5, 11.9, 60.0, -60.0):
        result = hmm.observe(RivalTelemetry(300, 100, 0, dgap, lap=1))
        probabilities = result.ers_probabilities
        assert sum(probabilities.values()) == pytest.approx(1.0)
        assert all(value > 0.0 for value in probabilities.values())
        assert sum(result.belief.values()) == pytest.approx(1.0)


def test_belief_floor_bounds_confidence_instead_of_collapsing_to_a_point_mass():
    from src.intelligence.hierarchical import FortyStateHMM, RivalTelemetry

    hmm = FortyStateHMM(belief_floor=0.02)
    result = hmm.observe(RivalTelemetry(300, 100, 0, 60.0, lap=1))
    # Each ERS mode spans 10 of the 40 states, so the uniform mixture puts a
    # 0.25 * floor floor under every marginal.
    assert min(result.ers_probabilities.values()) >= 0.25 * 0.02 - 1e-9
    assert max(result.ers_probabilities.values()) < 1.0 - 1e-9


def test_planner_and_search_survive_an_all_zero_belief():
    """Defence in depth: a bad belief must degrade, not crash the render loop."""
    from types import SimpleNamespace

    from src.intelligence.control_layers import BoundedScenarioPlanner
    from src.intelligence.scenario_search import ParticlePOMCP, SearchConfig

    zero = SimpleNamespace(
        ers_probabilities={"H": 0.0, "M": 0.0, "Lharvest": 0.0, "Lderate": 0.0}
    )
    result = ParticlePOMCP(SearchConfig(simulations=16)).search(zero, 1.0, 50.0)
    assert result.action in {"BURN", "HARVEST", "PROACTIVE TRAP"}
    plan = BoundedScenarioPlanner().plan(zero, 300.0, 1.0, 50.0)
    assert plan.command in {"BURN", "HARVEST", "PROACTIVE TRAP"}


def test_degenerate_transition_row_does_not_empty_the_filter():
    from src.intelligence.hierarchical import (
        ERSMode, FortyStateHMM, RivalTelemetry,
    )

    hmm = FortyStateHMM(mode_transition={mode.value: {} for mode in ERSMode})
    result = hmm.observe(RivalTelemetry(300, 100, 0, 0.0, lap=1))
    assert sum(result.ers_probabilities.values()) == pytest.approx(1.0)
