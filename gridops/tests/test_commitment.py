"""Anti-attrition tests: pricing, reserve floor and recurrence guards.

The headline test is ``test_ablation_*``: removing the terminal resource value
reproduces the futile-exchange failure the method is meant to prevent.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from gridops.contracts.state import ActionFamily, BatteryParams, BatteryState
from gridops.decision.commitment import (
    REASON_INSUFFICIENT_RESERVE,
    Commitment,
    CommitmentLedger,
    NoProgressGuard,
    ReserveGuard,
    conservative_improvement,
    should_commit,
)
from gridops.race_value.lap_map import (
    default_terminal_value,
    usable_energy_for_soc,
)


@pytest.fixture()
def battery() -> BatteryParams:
    return BatteryParams()


def test_terminal_value_is_non_increasing_in_energy(battery: BatteryParams) -> None:
    value = default_terminal_value(battery, seconds_per_megajoule=0.20)
    energies = [0.0, 0.25, 0.5, 0.75, 1.0]  # fractions of usable range
    full = usable_energy_for_soc(battery.soc_max, battery)
    costs = [value.cost_s(f * full) for f in energies]
    for earlier, later in zip(costs, costs[1:]):
        assert later <= earlier + 1e-12


def test_futile_attack_has_negative_worst_case_improvement(battery: BatteryParams) -> None:
    value = default_terminal_value(battery)
    start = usable_energy_for_soc(0.70, battery)
    spent = 100_000.0
    ref = value.cost_s(start)
    cand = value.cost_s(start - spent)
    improvement = conservative_improvement([ref], [cand])
    assert improvement < 0.0
    assert not should_commit(improvement, margin=0.0)


def test_attack_with_real_gain_can_clear_the_margin(battery: BatteryParams) -> None:
    value = default_terminal_value(battery)
    start = usable_energy_for_soc(0.70, battery)
    spent = 100_000.0
    ref = value.cost_s(start)
    cand = value.cost_s(start - spent) - 0.5  # 0.5 s modelled position gain
    improvement = conservative_improvement([ref], [cand])
    assert should_commit(improvement, margin=0.1)


def test_worst_case_over_hypotheses_rejects_maybe_it_works(battery: BatteryParams) -> None:
    """Mean gain positive, but under the strong-rival hypothesis it is negative."""
    reference = [0.0, 0.0]
    candidate = [-0.30, 0.05]
    mean_gain = sum(r - c for r, c in zip(reference, candidate)) / len(reference)
    assert mean_gain > 0
    assert conservative_improvement(reference, candidate) < 0
    assert not should_commit(conservative_improvement(reference, candidate), 0.0)


def test_reserve_guard_blocks_bankruptcy(battery: BatteryParams) -> None:
    value = default_terminal_value(battery)
    guard = ReserveGuard(value.reserve)
    ok_below, reason = guard.check(value.reserve.floor_j - 1.0)
    assert not ok_below and reason == REASON_INSUFFICIENT_RESERVE
    ok_above, reason_above = guard.check(value.reserve.floor_j + 1.0)
    assert ok_above and reason_above is None


def test_reserve_guard_clamps_spend_to_headroom(battery: BatteryParams) -> None:
    value = default_terminal_value(battery)
    guard = ReserveGuard(value.reserve)
    available = value.reserve.floor_j + 30_000.0
    assert guard.clamp_budget(available, 500_000.0) == pytest.approx(30_000.0)
    assert guard.clamp_budget(available, 1_000.0) == pytest.approx(1_000.0)


def test_no_progress_guard_trips_and_cools_down() -> None:
    guard = NoProgressGuard(repeat_threshold=3, cooldown_s=10.0)
    assert not guard.observe(0.0, 100.0, 1.0, 999_000.0)
    assert not guard.observe(1.0, 100.5, 1.1, 999_500.0)
    assert guard.observe(2.0, 100.2, 1.2, 998_000.0)
    assert guard.trips == 1
    assert guard.is_cooling(5.0)
    assert not guard.is_cooling(12.0)


def test_ledger_expiry_accumulates_futile_energy() -> None:
    ledger = CommitmentLedger()
    commitment = Commitment(
        candidate_id="attack-now",
        family=ActionFamily.ATTACK_NOW,
        objective="pass",
        energy_budget_j=200_000.0,
        opened_at_s=0.0,
        expires_at_s=2.0,
        success_position_delta_m=10.0,
    )
    assert ledger.open(commitment)
    ledger.record_spend(500_000.0)
    resolved = ledger.tick(now_s=2.5, position_delta_m=0.0)
    assert resolved and resolved[0].is_futile()
    assert ledger.futile_energy_j == pytest.approx(500_000.0)
    assert ledger.attempts == 1
    assert ledger.failure_rate == pytest.approx(1.0)


def test_successful_commitment_is_not_futile() -> None:
    ledger = CommitmentLedger()
    commitment = Commitment(
        candidate_id="attack-now",
        family=ActionFamily.ATTACK_NOW,
        objective="pass",
        energy_budget_j=200_000.0,
        opened_at_s=0.0,
        expires_at_s=2.0,
        success_position_delta_m=10.0,
    )
    ledger.open(commitment)
    ledger.record_spend(150_000.0)
    ledger.tick(now_s=2.5, position_delta_m=25.0)
    assert ledger.futile_energy_j == 0.0
    assert ledger.failures == 0


def test_futile_budget_exhaustion_blocks_new_commitments() -> None:
    ledger = CommitmentLedger(max_futile_energy_j=100_000.0)
    first = Commitment("a", ActionFamily.ATTACK_NOW, "pass", 0.0, 0.0, 1.0, 10.0)
    ledger.open(first)
    ledger.record_spend(120_000.0)
    ledger.tick(now_s=1.5, position_delta_m=0.0)
    second = Commitment("b", ActionFamily.ATTACK_NOW, "pass", 0.0, 2.0, 3.0, 10.0)
    assert not ledger.open(second)


# --------------------------------------------------------------------------
# Ablation: reproduce the futile-exchange failure mode.
# --------------------------------------------------------------------------

@dataclass
class _ExchangeResult:
    final_energy_j: float
    futile_energy_j: float
    attempts: int


def _run_exchange(
    battery: BatteryParams,
    *,
    priced: bool,
    belief_updates: bool,
    cycles: int = 60,
    spend_per_attack_j: float = 100_000.0,
    initial_gain_s: float = 0.05,
    reward_s: float = 5.0,
    margin_s: float = 0.001,
) -> _ExchangeResult:
    """Two-car attrition loop where every attack fails (position delta 0).

    ``priced``           -- include terminal resource cost in the decision.
    ``belief_updates``   -- shrink the perceived gain after a failed attempt.
    """
    value = default_terminal_value(battery)
    ledger = CommitmentLedger()
    energy = usable_energy_for_soc(battery.soc_initial, battery)
    p_gain = initial_gain_s / reward_s  # implied probability of a real gain
    frozen = 0.0

    for cycle in range(cycles):
        now = float(cycle)
        expected_reward = p_gain * reward_s
        if priced:
            ref = value.cost_s(energy)
            cand = value.cost_s(energy - spend_per_attack_j) - expected_reward
            improvement = conservative_improvement([ref], [cand])
            commit = should_commit(improvement, margin=margin_s)
        else:
            commit = expected_reward > margin_s

        if not commit:
            continue

        commitment = Commitment(
            candidate_id=f"attack-{cycle}",
            family=ActionFamily.ATTACK_NOW,
            objective="pass",
            energy_budget_j=spend_per_attack_j,
            opened_at_s=now,
            expires_at_s=now + 1.0,
            success_position_delta_m=10.0,
        )
        ledger.open(commitment)
        energy -= spend_per_attack_j
        ledger.record_spend(spend_per_attack_j)
        ledger.tick(now_s=now + 1.5, position_delta_m=0.0)
        if belief_updates:
            p_gain *= 0.6  # failed attack is evidence of a stronger rival

    return _ExchangeResult(energy, ledger.futile_energy_j, ledger.attempts)


def test_ablation_without_pricing_depletes_the_battery(battery: BatteryParams) -> None:
    """The failure mode: unpriced attacks burn the whole reserve."""
    myopic = _run_exchange(battery, priced=False, belief_updates=False)
    assert myopic.futile_energy_j > 3_000_000.0
    assert myopic.final_energy_j < usable_energy_for_soc(0.10, battery)


def test_pricing_prevents_the_futile_exchange(battery: BatteryParams) -> None:
    """When the modelled gain is below the energy opportunity cost, pricing
    rejects the attack outright; the unpriced ablation keeps spending."""
    priced = _run_exchange(battery, priced=True, belief_updates=False, initial_gain_s=0.005)
    myopic = _run_exchange(battery, priced=False, belief_updates=False, initial_gain_s=0.005)
    assert priced.futile_energy_j == 0.0
    assert myopic.futile_energy_j > 3_000_000.0
    assert priced.attempts == 0


def test_pricing_holds_the_soft_reserve_floor(battery: BatteryParams) -> None:
    """Even a probability-weighted attack stops at the soft reserve floor."""
    value = default_terminal_value(battery)
    priced = _run_exchange(battery, priced=True, belief_updates=False)
    myopic = _run_exchange(battery, priced=False, belief_updates=False)
    assert priced.final_energy_j >= value.reserve.soft_floor_j - 1.0
    assert myopic.final_energy_j < value.reserve.floor_j
    assert priced.futile_energy_j < myopic.futile_energy_j


def test_belief_update_bounds_the_number_of_attempts(battery: BatteryParams) -> None:
    without = _run_exchange(battery, priced=False, belief_updates=False)
    with_update = _run_exchange(battery, priced=False, belief_updates=True)
    assert with_update.attempts < without.attempts
    assert with_update.attempts <= 8
