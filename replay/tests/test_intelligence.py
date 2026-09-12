"""Tests for the AI Motorsport Intelligence decision core."""

import math

from src.intelligence.energy import (
    EnergyEstimator,
    MODE_ATTACK,
    MODE_BALANCED,
    MODE_HARVEST,
    MODE_LIFT_COAST,
    deploy_rate,
    harvest_rate,
    recommend_deployment_mode,
)
from src.intelligence.overtake import (
    VERDICT_AVOID,
    VERDICT_HIGH,
    evaluate_overtake_window,
)
from src.intelligence.race_engineer import RaceEngineer


# --- energy rates ----------------------------------------------------------

def test_deploy_requires_throttle_and_speed():
    assert deploy_rate(50, 200) == 0.0      # not enough throttle
    assert deploy_rate(100, 20) == 0.0      # too slow
    assert deploy_rate(100, 200) > 0.0
    assert deploy_rate(100, 200) >= deploy_rate(85, 200)


def test_harvest_braking_beats_coasting():
    braking = harvest_rate(0, 1, 200)
    coasting = harvest_rate(0, 0, 200)
    assert braking > coasting > 0.0
    assert harvest_rate(100, 0, 200) == 0.0  # on power -> no harvest


def test_energy_series_harvests_under_braking():
    est = EnergyEstimator()
    samples = [
        {"t": 0.0, "lap": 1, "throttle": 0, "brake": 1, "speed": 250},
        {"t": 1.0, "lap": 1, "throttle": 0, "brake": 1, "speed": 150},
    ]
    snaps = est.estimate_series(samples)
    assert snaps[-1].soc > 100.0 - 1e-9  # harvested, clamped at budget
    assert snaps[-1].harvest > 0.0


def test_energy_series_drains_under_deployment():
    est = EnergyEstimator()
    samples = [
        {"t": 0.0, "lap": 1, "throttle": 100, "brake": 0, "speed": 300},
        {"t": 5.0, "lap": 1, "throttle": 100, "brake": 0, "speed": 300},
    ]
    snaps = est.estimate_series(samples)
    assert snaps[-1].soc < 100.0
    assert snaps[-1].deploy > 0.0
    assert snaps[-1].balance < 0.0


def test_energy_persists_across_lap_boundary():
    # The battery is a real state: it must NOT magically refill at a lap line.
    est = EnergyEstimator()
    samples = [
        {"t": 0.0, "lap": 1, "throttle": 100, "brake": 0, "speed": 300},
        {"t": 10.0, "lap": 1, "throttle": 100, "brake": 0, "speed": 300},
        {"t": 10.04, "lap": 2, "throttle": 100, "brake": 0, "speed": 300},
    ]
    snaps = est.estimate_series(samples)
    assert snaps[-1].lap == 2
    assert snaps[-1].soc <= snaps[1].soc  # continued draining, no refill


def test_deploy_throttles_as_battery_falls():
    est = EnergyEstimator()
    full = [
        {"t": 0.0, "lap": 1, "throttle": 100, "brake": 0, "speed": 300},
        {"t": 1.0, "lap": 1, "throttle": 100, "brake": 0, "speed": 300},
    ]
    low = [
        {"t": 0.0, "lap": 1, "throttle": 100, "brake": 0, "speed": 300},
    ]
    full_deploy = est.estimate_series(full)[-1].deploy
    low_est = EnergyEstimator(start_soc=6.0)
    low_deploy = low_est.estimate_series(low)[-1].deploy
    assert low_deploy < full_deploy


def test_energy_soc_stays_within_bounds():
    est = EnergyEstimator()
    samples = [
        {"t": float(i), "lap": 1, "throttle": 100, "brake": 0, "speed": 320}
        for i in range(0, 200)
    ]
    snaps = est.estimate_series(samples)
    assert all(0.0 <= s.soc <= 100.0 for s in snaps)


def test_step_energy_matches_batch_estimator():
    from src.intelligence.energy import step_energy

    dt = 0.2
    rows = []
    for i in range(120):
        # mix of deploy, brake and coast
        throttle = 100 if i % 3 != 0 else 0
        brake = 1 if i % 5 == 0 else 0
        rows.append({"t": i * dt, "lap": 1 + i // 60,
                     "throttle": throttle, "brake": brake, "speed": 240.0})
    batch = EnergyEstimator().estimate_series(rows)

    soc = 100.0
    prev_t = None
    for i, r in enumerate(rows):
        step = 0.0 if prev_t is None else r["t"] - prev_t
        prev_t = r["t"]
        soc, _, _ = step_energy(soc, step, r["throttle"], r["brake"], r["speed"])
        assert abs(soc - batch[i].soc) < 1e-9


# --- deployment recommendation --------------------------------------------

def test_mode_lift_coast_when_critical():
    assert recommend_deployment_mode(5).mode == MODE_LIFT_COAST


def test_mode_harvest_when_low():
    assert recommend_deployment_mode(25).mode == MODE_HARVEST


def test_mode_attack_in_window_with_energy():
    advice = recommend_deployment_mode(
        80, gap_ahead_s=0.4, overtake_score=30, drs=True
    )
    assert advice.mode == MODE_ATTACK
    assert advice.urgency > 0.0


def test_mode_balanced_when_no_window():
    assert recommend_deployment_mode(80, gap_ahead_s=5.0).mode == MODE_BALANCED


def test_no_attack_without_positive_score():
    assert recommend_deployment_mode(80, gap_ahead_s=0.4, overtake_score=-10).mode == MODE_BALANCED


# --- overtake assessment ---------------------------------------------------

def test_overtake_high_reward_close_with_drs():
    a = evaluate_overtake_window(
        gap_ahead_s=0.2, speed_delta_kmh=15, drs=True, soc=90,
        tyre_life=2, laps_remaining=20, position=2,
    )
    assert a.reward > a.risk
    assert a.verdict == VERDICT_HIGH
    assert 0.0 <= a.probability <= 1.0
    assert math.isclose(a.score, a.reward - a.risk)


def test_overtake_avoid_when_energy_spent():
    a = evaluate_overtake_window(
        gap_ahead_s=0.9, speed_delta_kmh=0, drs=True, soc=5,
        tyre_life=26, laps_remaining=1, position=12,
    )
    assert a.risk > a.reward
    assert a.verdict == VERDICT_AVOID


def test_overtake_no_gap_is_all_reward_zero():
    a = evaluate_overtake_window(gap_ahead_s=None, drs=False)
    assert a.reward == 0.0


# --- race engineer integration --------------------------------------------

def test_race_engineer_builds_full_report():
    eng = RaceEngineer()
    samples = [
        {"t": 0.0, "lap": 1, "throttle": 100, "brake": 0, "speed": 300},
        {"t": 2.0, "lap": 1, "throttle": 100, "brake": 0, "speed": 300},
    ]
    energy = eng.estimate_energy(samples)[-1]
    report = eng.build_report(
        code="LEC",
        energy=energy,
        gap_ahead_s=0.5,
        speed_delta_kmh=10,
        drs=True,
        tyre_life=5,
        laps_remaining=15,
        position=3,
    )
    assert report.code == "LEC"
    assert report.overtake is not None
    assert report.advice.mode in {MODE_ATTACK, MODE_BALANCED, MODE_HARVEST, MODE_LIFT_COAST}
    assert any(f.label == "DRS" for f in report.compliance)
    d = report.as_dict()
    assert d["code"] == "LEC" and "energy" in d and "compliance" in d


def test_compliance_flags_neutralised():
    flags = RaceEngineer.compliance_flags(soc=50, gap_ahead_s=0.5, drs=False, track_status="4")
    assert any(f.state == "warn" and f.label == "Track status" for f in flags)
