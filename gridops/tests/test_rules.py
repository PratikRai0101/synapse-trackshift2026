"""Rules engine: envelope breakpoints, unknown permissions and plant clamping."""

from __future__ import annotations

import pytest

from gridops.contracts.ruleset import (
    REASON_ELIGIBILITY_DENIED,
    REASON_ELIGIBILITY_UNKNOWN,
    Permission,
    Ruleset,
    default_ruleset,
    normal_power_limit_kw,
    overtake_power_limit_kw,
)
from gridops.contracts.state import (
    ActionFamily,
    BatteryParams,
    Control,
    SaturationReason,
    VehicleParams,
)
from gridops.simulation.plant import Plant, initial_state
from gridops.simulation.track import synthetic_circuit


def test_normal_envelope_breakpoints() -> None:
    assert normal_power_limit_kw(290.0) == pytest.approx(350.0)
    assert normal_power_limit_kw(337.5) == pytest.approx(112.5)
    assert normal_power_limit_kw(340.0) == pytest.approx(100.0)
    assert normal_power_limit_kw(344.0) == pytest.approx(20.0)
    assert normal_power_limit_kw(345.0) == pytest.approx(0.0)
    assert normal_power_limit_kw(360.0) == pytest.approx(0.0)


def test_overtake_envelope_keeps_power_higher_up_the_curve() -> None:
    assert overtake_power_limit_kw(337.5) == pytest.approx(350.0)
    assert overtake_power_limit_kw(350.0) == pytest.approx(100.0)
    assert overtake_power_limit_kw(355.0) == pytest.approx(0.0)
    # overtake is never below the normal envelope on the same speed
    for speed in (200.0, 300.0, 330.0, 340.0):
        assert overtake_power_limit_kw(speed) >= normal_power_limit_kw(speed)


def test_unknown_overtake_falls_back_with_a_reason() -> None:
    rules = default_ruleset()
    assert rules.overtake is Permission.UNKNOWN
    limit_w, reason = rules.deployment_limit_w(speed_mps=330.0 / 3.6, overtake_requested=True)
    assert reason == REASON_ELIGIBILITY_UNKNOWN
    expected, _ = rules.deployment_limit_w(speed_mps=330.0 / 3.6, overtake_requested=False)
    assert limit_w == pytest.approx(expected)


def test_granted_overtake_uses_the_restricted_envelope() -> None:
    rules = Ruleset(
        ruleset_id="r", edition="e", verified=True, overtake=Permission.GRANTED
    )
    limit_w, reason = rules.deployment_limit_w(speed_mps=330.0 / 3.6, overtake_requested=True)
    assert reason is None
    assert limit_w == pytest.approx(min(overtake_power_limit_kw(330.0), 350.0) * 1000.0, rel=1e-9)


def test_denied_overtake_reports_denial() -> None:
    rules = Ruleset(ruleset_id="r", edition="e", verified=True, overtake=Permission.DENIED)
    _, reason = rules.deployment_limit_w(speed_mps=300.0 / 3.6, overtake_requested=True)
    assert reason == REASON_ELIGIBILITY_DENIED


def test_unknown_mode_is_unavailable() -> None:
    rules = default_ruleset()
    available, reason = rules.mode_available("overtake")
    assert not available and reason == REASON_ELIGIBILITY_UNKNOWN
    available, reason = rules.mode_available("active_aero")
    assert not available and reason == REASON_ELIGIBILITY_UNKNOWN
    available, reason = rules.mode_available("not_a_mode")
    assert not available and reason == "UNKNOWN_MODE"


def test_plant_clamps_deployment_to_the_envelope() -> None:
    rules = default_ruleset()
    plant = Plant(VehicleParams(), BatteryParams(), synthetic_circuit(), None, rules)
    # 100 m/s = 360 km/h, above the normal envelope cutoff: no deployment allowed
    state = initial_state(plant.battery, speed_mps=100.0)
    step = plant.step(
        state,
        Control(ActionFamily.ATTACK_NOW, 150_000.0, 100.0, 0.05, 0.0, overtake=False),
        0.05,
    )
    assert SaturationReason.RULE_LIMIT in step.saturation
    assert step.realized_p_k_dc_w <= 1e-6


def test_plant_reports_a_restricted_mode_fallback() -> None:
    plant = Plant(VehicleParams(), BatteryParams(), synthetic_circuit(), None, default_ruleset())
    state = initial_state(plant.battery, speed_mps=80.0)
    step = plant.step(
        state,
        Control(ActionFamily.PROBE, 50_000.0, 84.0, 0.05, 0.0, overtake=True),
        0.05,
    )
    assert step.rule_reason == REASON_ELIGIBILITY_UNKNOWN
