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


def test_ambiguity_aware_uses_convex_planner_when_provided() -> None:
    """With a planner, recommended power comes from the convex profile."""
    from gridops.decision.planning import ConditionalConvexPlanner, PlannerConfig

    runner = _runner()
    planner = ConditionalConvexPlanner(
        runner.track, runner.vehicle, runner.battery, runner.terminal_value, PlannerConfig()
    )
    belief = RivalBelief.uniform()
    with_planner = AmbiguityAwareController(
        runner.terminal_value, belief, horizon=2, iterations=120, planner=planner, seed=4
    )
    report = runner.run(with_planner, rival_policy=RivalPolicy.CONSERVING, seed=5)
    planned = [
        d for d in report.decisions if "CONVEX_PROFILE" in d["reason_codes"]
    ]
    assert planned, report.decisions
    assert all(d["status"] in {"RECOMMEND", "RETAIN_REFERENCE", "FALLBACK"} for d in report.decisions)


def test_planner_failure_falls_back_with_a_reason() -> None:
    class AlwaysInvalidPlanner:
        vehicle = VehicleParams()

        def plan(self, **kwargs):
            from gridops.decision.planning import ConvexPlan
            import numpy as np

            return ConvexPlan(
                s_m=np.zeros(3), speed_mps=np.zeros(3), p_k_dc_w=np.zeros(2),
                terminal_energy_j=0.0, predicted_time_s=0.0, is_dcp=True,
                status="infeasible", solve_time_s=0.0,
                max_dynamics_residual_mj=1.0, max_grip_residual_n=1.0,
                max_power_violation_w=1.0, deployed_energy_j=0.0,
            )

        def validate_plan(self, plan):
            return False, ["status=infeasible"]

    runner = _runner()
    controller = AmbiguityAwareController(
        runner.terminal_value, RivalBelief.uniform(), horizon=2, iterations=120,
        planner=AlwaysInvalidPlanner(), seed=6,
    )
    report = runner.run(controller, rival_policy=RivalPolicy.CONSERVING, seed=5)
    fallbacks = [d for d in report.decisions if d["status"] == "FALLBACK"]
    assert fallbacks
    assert any("PLAN_INVALID" in d["reason_codes"] for d in fallbacks)


def test_r09_worn_tyres_degrade_the_episode_outcome() -> None:
    """R09: a worn set reduces grip, so pace falls and saturation rises."""
    from gridops.simulation.tyres import default_tyre_params

    battery = BatteryParams()

    def run(wear: float):
        cfg = EpisodeConfig(
            duration_s=25.0, dt_s=0.05, replan_interval_s=1.0,
            decision_budget_s=0.1, initial_wear=wear,
        )
        runner = EpisodeRunner(
            synthetic_circuit(), VehicleParams(), battery,
            default_terminal_value(battery), cfg,
            tyre_params=default_tyre_params(),
        )
        return runner.run(ReferenceController(), rival_policy=RivalPolicy.MATCHING, seed=1)

    fresh = run(0.0)
    worn = run(0.9)
    assert worn.ego_final_progress_m < fresh.ego_final_progress_m
    assert worn.saturation_counts.get("grip_limit", 0) > fresh.saturation_counts.get(
        "grip_limit", 0
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
