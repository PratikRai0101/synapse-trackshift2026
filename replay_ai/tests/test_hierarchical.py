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


def test_lifecycle_dp_can_choose_replacement_for_degraded_pack():
    decision = SeasonLifecycleManager(races=10).decide(soh=0.1, temperature=95)
    assert decision.replace
    assert decision.soh == 1.0
