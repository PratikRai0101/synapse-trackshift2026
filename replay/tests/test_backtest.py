"""Tests for the Race Engineer backtest harness (synthetic, offline)."""

from src.intelligence.backtest import (
    BacktestResult,
    _sample_race,
    run_backtest,
    sweep_thresholds,
)


def _frames(n=220, dt=0.2, start_lap=5):
    """Two cars: B starts ~0.9s behind A and closes to ~0.15s (a sustained
    attempt) so the gap-to-same-car conversion is measurable."""
    frames = []
    for i in range(n):
        t = i * dt
        lap = start_lap + int(t // 80.0)
        dist_a = 1000.0 + 55.56 * t
        gap_s = max(0.15, 0.9 - 0.08 * t)
        dist_b = dist_a - gap_s * 55.56
        frames.append(
            {
                "t": t,
                "lap": lap,
                "drivers": {
                    "AAA": {"x": 0, "y": 0, "dist": dist_a, "lap": lap, "speed": 200.0,
                            "throttle": 100.0, "brake": 0.0, "drs": 0, "tyre_life": 5.0, "in_pit": False},
                    "BBB": {"x": 0, "y": 0, "dist": dist_b, "lap": lap, "speed": 212.0,
                            "throttle": 100.0, "brake": 0.0, "drs": 12, "tyre_life": 5.0, "in_pit": False},
                },
            }
        )
    return frames


def test_sample_race_alignment():
    frames = _frames(n=40)
    codes, out, order, times = _sample_race(frames, stride=2)
    assert set(codes) == {"AAA", "BBB"}
    assert len(times) == len(order)
    # arrays align with the sampled timeline
    assert all(len(out[c]["t"]) == len(times) for c in codes)
    # B is behind A at the first sample
    assert order[0][0] == "AAA"


def test_backtest_detects_attack_conversion():
    result = run_backtest(_frames(), label="synthetic", total_laps=60)
    assert isinstance(result, BacktestResult)
    assert result.n_windows > 0
    assert result.n_attack > 0
    # The closing car should convert (reach <=0.3s) on ATTACK frames.
    assert result.attack_conversion > 0.0
    assert result.attack_conversion >= result.baseline_conversion
    assert "lift" in result.summary()


def test_backtest_empty_frames():
    result = run_backtest([], label="empty")
    assert result.n_windows == 0
    assert result.attack_conversion == 0.0


def test_sweep_returns_one_result_per_threshold():
    results = sweep_thresholds(_frames(), thresholds=(0.0, 20.0, 40.0), total_laps=60)
    assert len(results) == 3
    assert all(isinstance(r, BacktestResult) for r in results)
    # A stricter threshold cannot produce more ATTACK calls.
    assert results[0].n_attack >= results[-1].n_attack
