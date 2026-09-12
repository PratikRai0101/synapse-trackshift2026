"""Closed-loop episode tests: determinism, responsiveness and anti-attrition."""

from __future__ import annotations

import random

import pytest

from gridops.contracts.records import DecisionInput
from gridops.contracts.state import ActionFamily, BatteryParams, VehicleParams
from gridops.decision.belief import RivalBelief
from gridops.evaluation.controllers import (
    AmbiguityAwareController,
    Decision,
    ReferenceController,
    StationaryPlanner,
)
from gridops.evaluation.runner import EpisodeConfig, EpisodeRunner
from gridops.race_value.lap_map import default_terminal_value
from gridops.simulation.rivals import RivalPolicy
from gridops.simulation.track import synthetic_circuit


class AlwaysAttackController:
    def decide(self, decision_input: DecisionInput, budget_s: float) -> Decision:
        return Decision(
            family=ActionFamily.ATTACK_NOW,
            p_k_dc_w=150_000.0,
            target_speed_mps=decision_input.ego_speed_mps + 6.0,
            status="RECOMMEND",
            reason_codes=["TEST_ALWAYS_ATTACK"],
        )

    def notify_gap_change(self, gap_closed_m: float) -> None:
        return None

    def notify_commitment_outcome(self, attacked: bool, gained: bool) -> None:
        return None


def _runner(duration_s: float = 15.0) -> EpisodeRunner:
    battery = BatteryParams()
    return EpisodeRunner(
        track=synthetic_circuit(),
        vehicle=VehicleParams(),
        battery=battery,
        terminal_value=default_terminal_value(battery),
        config=EpisodeConfig(
            duration_s=duration_s,
            dt_s=0.05,
            replan_interval_s=1.0,
            decision_budget_s=0.1,
        ),
    )


def test_episode_is_deterministic() -> None:
    runner = _runner()
    first = runner.run(ReferenceController(), rival_policy=RivalPolicy.MATCHING, seed=7)
    second = runner.run(ReferenceController(), rival_policy=RivalPolicy.MATCHING, seed=7)
    assert first.summary() == second.summary()


def test_aggressive_control_spends_more_energy() -> None:
    runner = _runner()
    baseline = runner.run(ReferenceController(), rival_policy=RivalPolicy.MATCHING, seed=1)
    attack = runner.run(AlwaysAttackController(), rival_policy=RivalPolicy.MATCHING, seed=1)
    assert attack.ego_energy_spent_j > baseline.ego_energy_spent_j


def test_rival_policy_changes_the_outcome() -> None:
    runner = _runner()
    matching = runner.run(AlwaysAttackController(), rival_policy=RivalPolicy.MATCHING, seed=2)
    conserving = runner.run(AlwaysAttackController(), rival_policy=RivalPolicy.CONSERVING, seed=2)
    assert matching.final_gap_m != conserving.final_gap_m


def test_stationary_planner_episode_completes() -> None:
    runner = _runner()
    controller = StationaryPlanner(runner.terminal_value, horizon=2, iterations=100)
    report = runner.run(controller, rival_policy=RivalPolicy.MATCHING, seed=3)
    assert report.decisions
    assert report.ego_final_energy_j > 0.0


def test_ambiguity_aware_controller_bounds_energy_against_a_strong_rival() -> None:
    """End-to-end anti-attrition: the guarded controller spends less than always-attack."""
    runner = _runner(duration_s=25.0)
    belief = RivalBelief.uniform()
    guarded = AmbiguityAwareController(
        terminal_value=runner.terminal_value,
        belief=belief,
        horizon=2,
        iterations=120,
        seed=11,
    )
    guarded_report = runner.run(guarded, rival_policy=RivalPolicy.MATCHING, seed=5)
    attack_report = runner.run(AlwaysAttackController(), rival_policy=RivalPolicy.MATCHING, seed=5)
    assert guarded_report.ego_energy_spent_j < attack_report.ego_energy_spent_j
    assert guarded_report.ego_final_energy_j > runner.terminal_value.reserve.floor_j
    assert all(
        decision["status"] in {"RECOMMEND", "RETAIN_REFERENCE", "FALLBACK", "UNAVAILABLE"}
        for decision in guarded_report.decisions
    )


def test_belief_shifts_toward_a_strong_rival_after_failed_attempts() -> None:
    belief = RivalBelief.uniform()
    before = belief.strong_rival_mass()
    for _ in range(3):
        belief.update_on_outcome(ego_attacked=True, gained=False)
    assert belief.strong_rival_mass() > before


def test_belief_shifts_toward_a_weak_rival_after_a_gain() -> None:
    belief = RivalBelief.uniform()
    before = belief.strong_rival_mass()
    for _ in range(3):
        belief.update_on_outcome(ego_attacked=True, gained=True)
    assert belief.strong_rival_mass() < before


def test_non_stationary_mixing_keeps_uncertainty() -> None:
    belief = RivalBelief.uniform()
    for _ in range(10):
        belief.update_on_outcome(ego_attacked=True, gained=False)
    belief.mix_for_non_stationarity()
    forecast = belief.capability_forecast()
    assert forecast["strong_rival_mass"] < 1.0
    assert len(forecast["policy_mass"]) > 1
