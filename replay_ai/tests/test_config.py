"""Tests for model configuration and calibration plumbing."""

import os

from src.intelligence.config import DEFAULT_CONFIG, ModelConfig, load_config
from src.intelligence.backtest import BacktestResult, calibrate, select_operating_point
from src.intelligence.energy import EnergyEstimator, recommend_deployment_mode, step_energy
from src.intelligence.overtake import evaluate_overtake_window


def test_config_defaults_roundtrip():
    cfg = ModelConfig()
    assert ModelConfig.from_dict(cfg.to_dict()) == cfg


def test_config_from_dict_ignores_unknown_keys():
    cfg = ModelConfig.from_dict({"deploy_rate": 2.0, "nonsense": 5})
    assert cfg.deploy_rate == 2.0
    assert not hasattr(cfg, "nonsense")


def test_config_save_and_load(tmp_path):
    path = str(tmp_path / "cfg.json")
    ModelConfig(attack_min_score=42.0).save(path)
    loaded = ModelConfig.load(path)
    assert loaded.attack_min_score == 42.0


def test_load_config_missing_returns_defaults(tmp_path):
    cfg = load_config(str(tmp_path / "missing.json"))
    assert cfg == ModelConfig()


def test_config_changes_attack_decision():
    # A very high threshold should suppress ATTACK for a weak window.
    strict = ModelConfig(attack_min_score=999.0)
    advice = recommend_deployment_mode(
        soc=100.0, gap_ahead_s=0.5, overtake_score=20.0, config=strict
    )
    assert advice.mode == "BALANCED"
    loose = recommend_deployment_mode(
        soc=100.0, gap_ahead_s=0.5, overtake_score=20.0,
        config=ModelConfig(attack_min_score=0.0),
    )
    assert loose.mode == "ATTACK"


def test_config_changes_energy_rates():
    # Doubling the deploy rate should drain more over the same inputs.
    slow, _, _ = step_energy(100.0, 1.0, 100, 0, 250, config=ModelConfig(deploy_rate=1.0))
    fast, _, _ = step_energy(100.0, 1.0, 100, 0, 250, config=ModelConfig(deploy_rate=2.0))
    assert fast < slow


def test_estimator_uses_config():
    cfg = ModelConfig(soc_soft_ceil=30.0)
    est = EnergyEstimator(config=cfg)
    assert est.soft_ceil == 30.0
    assert est.lap_budget == cfg.lap_budget


def _result(threshold, lift, recall):
    return BacktestResult(
        label="x", horizon_s=8.0, attack_min_score=threshold, n_driver_samples=0,
        n_windows=0, n_attack=0, n_baseline=0, n_harvest=0, n_conversions=0,
        attack_conversion=0.0, baseline_conversion=0.0, harvest_conversion=0.0,
        lift=lift, recall=recall, mean_closure_attack=0.0,
        mean_closure_baseline=0.0, mean_energy_per_conversion=0.0,
    )


def test_select_operating_point_respects_recall_floor():
    results = [_result(0, 9.0, 0.5), _result(20, 7.0, 0.9), _result(50, 3.0, 0.95)]
    best = select_operating_point(results, min_recall=0.8, objective="lift")
    assert best.attack_min_score == 20  # 9.0 lift excluded by low recall


def test_select_operating_point_falls_back_when_none_pass():
    results = [_result(0, 1.0, 0.1), _result(20, 2.0, 0.2)]
    best = select_operating_point(results, min_recall=0.99)
    assert best.attack_min_score == 20  # best of all when none meet the floor


def _frames(n=220, dt=0.2):
    frames = []
    for i in range(n):
        t = i * dt
        lap = 5 + int(t // 80)
        dist_a = 1000.0 + 55.56 * t
        gap_s = max(0.15, 0.9 - 0.08 * t)
        dist_b = dist_a - gap_s * 55.56
        frames.append({
            "t": t, "lap": lap,
            "drivers": {
                "AAA": {"x": 0, "y": 0, "dist": dist_a, "lap": lap, "speed": 200.0,
                        "throttle": 100.0, "brake": 0.0, "drs": 0, "tyre_life": 5.0, "in_pit": False},
                "BBB": {"x": 0, "y": 0, "dist": dist_b, "lap": lap, "speed": 212.0,
                        "throttle": 100.0, "brake": 0.0, "drs": 12, "tyre_life": 5.0, "in_pit": False},
            },
        })
    return frames


def test_calibrate_returns_config_with_chosen_threshold():
    best, cfg, results = calibrate(
        _frames(), thresholds=(0.0, 20.0, 40.0), min_recall=0.5, total_laps=60
    )
    assert len(results) == 3
    assert best is not None
    assert cfg.attack_min_score == best.attack_min_score
