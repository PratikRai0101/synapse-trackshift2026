"""Controller adapters.

All controllers receive the same :class:`DecisionInput` and the same budget.
This is the seam the evaluator compares on: different methods, identical
information.

- ``ReferenceController``      retain the baseline
- ``StationaryPlanner``        B_stat: assumes a non-reacting rival (base paper)
- ``PosteriorMeanPlanner``     B_mean: expected response, one-step lookahead
- ``AmbiguityAwareController`` M: POMCP over a persistent belief, gated by the
  commitment rule, reserve guard and no-progress guard
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Protocol, Sequence

from ..contracts.records import DecisionInput
from ..contracts.state import ActionFamily
from ..decision.belief import RivalBelief
from ..decision.commitment import (
    REASON_INSUFFICIENT_RESERVE,
    REASON_NO_PROGRESS,
    REASON_NO_IMPROVEMENT,
    NoProgressGuard,
    ReserveGuard,
    conservative_improvement,
    should_commit,
)
from ..decision.pomcp import POMCP, SearchResult
from ..decision.planning import ConditionalConvexPlanner, PlannerConfig
from ..decision.tactical import (
    ACTION_POWER_W,
    ACTION_TARGET_SPEED_MPS,
    SPEND_J,
    TacticalModel,
    TacticalParams,
    TacticalState,
)
from ..race_value.lap_map import TerminalValue
from ..simulation.rivals import RivalPolicy, RivalPolicyConfig, rival_target_speed


@dataclass
class Decision:
    family: ActionFamily
    p_k_dc_w: float
    target_speed_mps: float
    status: str = "RETAIN_REFERENCE"
    reason_codes: list[str] = field(default_factory=list)
    action_values: dict[str, float] = field(default_factory=dict)
    runtime_s: float = 0.0
    search_iterations: int = 0
    timed_out: bool = False
    lateral_target_m: float = 0.0


class Controller(Protocol):
    def decide(self, decision_input: DecisionInput, budget_s: float) -> Decision: ...

    def notify_observation(self, rival_speed_mps: float) -> None: ...

    def notify_commitment_outcome(self, attacked: bool, gained: bool) -> None: ...


def _power_for_family(family: ActionFamily, params: TacticalParams) -> float:
    return ACTION_POWER_W.get(family, 0.0)


def _target_lateral(family: ActionFamily) -> float:
    """Pass offset: move alongside the rival before attempting a pass."""
    if family in (
        ActionFamily.ATTACK_NOW,
        ActionFamily.ATTACK_LATER,
        ActionFamily.PROBE,
    ):
        return 2.5
    return 0.0


def _target_speed(family: ActionFamily, current_speed: float) -> float:
    """Reference-paced target; the plant applies the cornering-speed cap."""
    return ACTION_TARGET_SPEED_MPS.get(family, 80.0)


class ReferenceController:
    def decide(self, decision_input: DecisionInput, budget_s: float) -> Decision:
        return Decision(
            family=ActionFamily.REFERENCE,
            p_k_dc_w=0.0,
            target_speed_mps=_target_speed(ActionFamily.REFERENCE, decision_input.ego_speed_mps),
            status="RETAIN_REFERENCE",
            reason_codes=["BASELINE"],
        )

    def notify_observation(self, rival_speed_mps: float) -> None:
        return None

    def notify_commitment_outcome(self, attacked: bool, gained: bool) -> None:
        return None


def _hypothesis_costs(
    decision_input: DecisionInput,
    families: Sequence[ActionFamily],
    policies: Sequence[RivalPolicy],
    terminal_value: TerminalValue,
    params: TacticalParams,
    closure_fn=None,
) -> dict[ActionFamily, list[float]]:
    """Cost of each family under each rival-policy hypothesis (deterministic)."""
    out: dict[ActionFamily, list[float]] = {}
    gap = decision_input.gap_m
    energy = decision_input.ego_usable_energy_j
    for family in families:
        costs: list[float] = []
        spend = SPEND_J.get(family, 0.0)
        for policy in policies:
            closure = _expected_closure(family, policy, closure_fn)
            residual_gap = max(0.0, gap - closure)
            costs.append(
                terminal_value.cost_s(max(0.0, energy - spend))
                + params.gap_price_s_per_m * residual_gap
            )
        out[family] = costs
    return out


def _expected_closure(
    family: ActionFamily, policy: RivalPolicy, closure_fn=None
) -> float:
    if closure_fn is not None:
        return float(closure_fn(family, policy))
    from ..decision.tactical import _CLOSE_DEFENSIVE, _CLOSE_WEAK

    table = _CLOSE_DEFENSIVE if policy in {
        RivalPolicy.MATCHING,
        RivalPolicy.AGGRESSIVE,
        RivalPolicy.DELAYED,
    } else _CLOSE_WEAK
    return table.get(family, 0.0)


class StationaryPlanner:
    """B_stat: the base paper's non-reacting-rival planner."""

    def __init__(self, terminal_value: TerminalValue, horizon: int, iterations: int) -> None:
        self.model = TacticalModel(terminal_value, horizon)
        self.iterations = iterations

    def decide(self, decision_input: DecisionInput, budget_s: float) -> Decision:
        start = time.perf_counter()
        rng = random.Random(0)
        state = TacticalState(
            energy_j=decision_input.ego_usable_energy_j,
            gap_m=decision_input.gap_m,
            policy=RivalPolicy.STATIONARY,
        )
        result = POMCP(self.model, self.model.horizon, self.iterations).search(
            [state], rng, deadline_s=budget_s
        )
        return _decision_from_search(result, decision_input, time.perf_counter() - start)

    def notify_observation(self, rival_speed_mps: float) -> None:
        return None

    def notify_commitment_outcome(self, attacked: bool, gained: bool) -> None:
        return None


class PosteriorMeanPlanner:
    """B_mean: one-step lookahead against the expected rival response."""

    def __init__(
        self, terminal_value: TerminalValue, defensive_probability: float = 0.5
    ) -> None:
        self.terminal_value = terminal_value
        self.defensive_probability = defensive_probability

    def decide(self, decision_input: DecisionInput, budget_s: float) -> Decision:
        start = time.perf_counter()
        families = list(SPEND_J)
        closure = {}
        for family in families:
            weak = _expected_closure(family, RivalPolicy.CONSERVING)
            strong = _expected_closure(family, RivalPolicy.MATCHING)
            closure[family] = (
                self.defensive_probability * strong
                + (1.0 - self.defensive_probability) * weak
            )
        costs = {}
        for family in families:
            residual = max(0.0, decision_input.gap_m - closure[family])
            costs[family] = self.terminal_value.cost_s(
                max(0.0, decision_input.ego_usable_energy_j - SPEND_J[family])
            ) + 0.02 * residual
        best = min(costs, key=lambda f: costs[f])
        return Decision(
            family=best,
            p_k_dc_w=_power_for_family(best, TacticalParams()),
            target_speed_mps=_target_speed(best, decision_input.ego_speed_mps),
            status="RECOMMEND",
            reason_codes=["POSTERIOR_MEAN"],
            action_values={f.value: c for f, c in costs.items()},
            runtime_s=time.perf_counter() - start,
            lateral_target_m=_target_lateral(best),
        )

    def notify_observation(self, rival_speed_mps: float) -> None:
        return None

    def notify_commitment_outcome(self, attacked: bool, gained: bool) -> None:
        return None


class ConvexPlannerController:
    """Executes the conditional convex deployment profile for a reference pace.

    The plan is validated against its own primal residuals before execution;
    an invalid or infeasible plan falls back to the reference and says so.
    """

    def __init__(
        self,
        planner: ConditionalConvexPlanner,
        base_speed_mps: float = 85.0,
    ) -> None:
        self.planner = planner
        self.base_speed_mps = base_speed_mps

    def decide(self, decision_input: DecisionInput, budget_s: float) -> Decision:
        start = time.perf_counter()
        mass_kg = self.planner.vehicle.mass_kg
        plan = self.planner.plan(
            progress_m=decision_input.ego_progress_m,
            speed_mps=decision_input.ego_speed_mps,
            usable_energy_j=decision_input.ego_usable_energy_j,
            base_speed_mps=self.base_speed_mps,
            mass_kg=mass_kg,
        )
        ok, problems = self.planner.validate_plan(plan)
        if not ok:
            return Decision(
                family=ActionFamily.REFERENCE,
                p_k_dc_w=0.0,
                target_speed_mps=_target_speed(
                    ActionFamily.REFERENCE, decision_input.ego_speed_mps
                ),
                status="FALLBACK",
                reason_codes=["PLAN_INVALID", *problems],
                runtime_s=time.perf_counter() - start,
            )
        next_speed = float(plan.speed_mps[1]) if len(plan.speed_mps) > 1 else self.base_speed_mps
        return Decision(
            family=ActionFamily.REFERENCE,
            p_k_dc_w=plan.first_power_w(),
            target_speed_mps=next_speed,
            status="RECOMMEND",
            reason_codes=["CONVEX_PROFILE"],
            action_values={},
            runtime_s=time.perf_counter() - start,
        )

    def notify_observation(self, rival_speed_mps: float) -> None:
        return None

    def notify_commitment_outcome(self, attacked: bool, gained: bool) -> None:
        return None


class AmbiguityAwareController:
    """M: POMCP over persistent ambiguity, gated by the commitment machinery."""

    def __init__(
        self,
        terminal_value: TerminalValue,
        belief: RivalBelief,
        horizon: int = 3,
        iterations: int = 400,
        commitment_margin_s: float = 0.02,
        error_allowance_s: float = 0.0,
        credible_epsilon: float = 0.05,
        ambiguity_threshold: float = 0.6,
        probe_cooldown_s: float = 4.0,
        planner: ConditionalConvexPlanner | None = None,
        closure_fn=None,
        response_fn=None,
        rival_config=None,
        seed: int = 0,
    ) -> None:
        self.terminal_value = terminal_value
        self.belief = belief
        self.horizon = horizon
        self.iterations = iterations
        self.commitment_margin_s = commitment_margin_s
        self.error_allowance_s = error_allowance_s
        self.credible_epsilon = credible_epsilon
        self.ambiguity_threshold = ambiguity_threshold
        self.probe_cooldown_s = probe_cooldown_s
        self.planner = planner
        self.closure_fn = closure_fn
        self.response_fn = response_fn
        self.rival_config = rival_config or RivalPolicyConfig()
        self.rng = random.Random(seed)
        self.reserve_guard = ReserveGuard(terminal_value.reserve)
        self.no_progress = NoProgressGuard(repeat_threshold=4, cooldown_s=3.0)
        self.last_gap_m: float | None = None
        self.pending_attack = False
        self.last_family = ActionFamily.REFERENCE
        self.last_probe_s = float("-inf")
        self.excluded_mass = 0.0
        self._last_lateral_m = 0.0

    def decide(self, decision_input: DecisionInput, budget_s: float) -> Decision:
        start = time.perf_counter()
        # layer 5: recurrence / cooldown
        tripped = self.no_progress.observe(
            decision_input.time_s,
            decision_input.ego_progress_m,
            decision_input.gap_m,
            decision_input.ego_usable_energy_j,
        )
        if self.no_progress.is_cooling(decision_input.time_s) or tripped:
            return self._retain(decision_input, REASON_NO_PROGRESS, start)

        # layer 1: search over the highest-density credible set
        credible, excluded_mass = self.belief.credible_set(self.credible_epsilon)
        self.excluded_mass = excluded_mass
        particles = [p for p in credible if p.weight > 0.0] or list(self.belief.particles)
        states = [
            TacticalState(
                energy_j=decision_input.ego_usable_energy_j,
                gap_m=decision_input.gap_m,
                policy=p.policy,
            )
            for p in particles
        ]
        model = TacticalModel(self.terminal_value, self.horizon, closure_fn=self.closure_fn)
        result = POMCP(model, self.horizon, self.iterations).search(
            states, self.rng, deadline_s=budget_s
        )
        best = result.best_action

        # layer 1 (pricing): worst-case improvement across retained hypotheses
        policies = [p.policy for p in particles]
        costs = _hypothesis_costs(
            decision_input, [ActionFamily.REFERENCE, best], policies, self.terminal_value,
            model.params, self.closure_fn,
        )
        improvement = conservative_improvement(
            costs[ActionFamily.REFERENCE], costs[best], self.error_allowance_s
        )
        if should_commit(improvement, self.commitment_margin_s):
            # layer 2: hard reserve floor
            projected = decision_input.ego_usable_energy_j - SPEND_J.get(best, 0.0)
            ok, reason = self.reserve_guard.check(projected)
            if not ok:
                return self._retain(
                    decision_input, reason or REASON_INSUFFICIENT_RESERVE, start, result
                )
            self.pending_attack = best in (ActionFamily.ATTACK_NOW, ActionFamily.ATTACK_LATER)
            self.last_family = best
            power, target, plan_problems = self._realize(best, decision_input)
            if power is None:
                return self._retain(
                    decision_input, "PLAN_INVALID", start, result, extra=plan_problems
                )
            self._last_lateral_m = _target_lateral(best)
            return Decision(
                family=best,
                p_k_dc_w=power,
                target_speed_mps=target,
                status="RECOMMEND",
                reason_codes=["GAIN_SURVIVES_SCENARIOS"] + (["CONVEX_PROFILE"] if self.planner else []),
                action_values={f.value: c for f, c in result.action_mean_cost.items()},
                runtime_s=time.perf_counter() - start,
                search_iterations=result.iterations,
                timed_out=result.timed_out,
                lateral_target_m=self._last_lateral_m,
            )

        # layer 4b: bounded information-gathering probe.
        # A purely worst-case commitment rule never acts, so it never collects
        # evidence and stays ambiguous forever. A cheap probe breaks that loop.
        ambiguity = self.belief.ambiguity_index()
        if (
            best is not ActionFamily.PROBE
            and ambiguity >= self.ambiguity_threshold
            and decision_input.time_s - self.last_probe_s >= self.probe_cooldown_s
        ):
            projected = decision_input.ego_usable_energy_j - SPEND_J[ActionFamily.PROBE]
            ok, _reason = self.reserve_guard.check(projected)
            if ok:
                self.last_probe_s = decision_input.time_s
                self.pending_attack = False
                self.last_family = ActionFamily.PROBE
                power, target, plan_problems = self._realize(ActionFamily.PROBE, decision_input)
                if power is None:
                    return self._retain(
                        decision_input, "PLAN_INVALID", start, result, extra=plan_problems
                    )
                self._last_lateral_m = _target_lateral(ActionFamily.PROBE)
                return Decision(
                    family=ActionFamily.PROBE,
                    p_k_dc_w=power,
                    target_speed_mps=target,
                    status="RECOMMEND",
                    reason_codes=["AMBIGUOUS_CAPABILITY"]
                    + (["CONVEX_PROFILE"] if self.planner else []),
                    action_values={f.value: c for f, c in result.action_mean_cost.items()},
                    runtime_s=time.perf_counter() - start,
                    search_iterations=result.iterations,
                    timed_out=result.timed_out,
                    lateral_target_m=self._last_lateral_m,
                )

        return self._retain(decision_input, REASON_NO_IMPROVEMENT, start, result)

    def _realize(
        self, family: ActionFamily, decision_input: DecisionInput
    ) -> tuple[float | None, float | None, tuple[str, ...]]:
        """Realize a selected family as an actual convex deployment profile.

        Returns ``(power, target_speed, problems)``; ``power is None`` means the
        plan failed residual validation and the caller must fall back.
        """
        target = _target_speed(family, decision_input.ego_speed_mps)
        if self.planner is None:
            return _power_for_family(family, TacticalParams()), target, ()
        # Attack families must hold pace, so they use a tight lower trust bound
        # and therefore actually deploy; other families may trade speed away.
        lower_trust = {
            ActionFamily.ATTACK_NOW: 4.0,
            ActionFamily.ATTACK_LATER: 4.5,
            ActionFamily.PROBE: 4.0,
            ActionFamily.DEFEND: 3.5,
        }.get(family)
        plan = self.planner.plan(
            progress_m=decision_input.ego_progress_m,
            speed_mps=decision_input.ego_speed_mps,
            usable_energy_j=decision_input.ego_usable_energy_j,
            base_speed_mps=target,
            mass_kg=self.planner.vehicle.mass_kg,
            lower_trust_dv_mps=lower_trust,
        )
        ok, problems = self.planner.validate_plan(plan)
        if not ok:
            return None, None, tuple(problems)
        next_speed = float(plan.speed_mps[1]) if len(plan.speed_mps) > 1 else target
        return plan.first_power_w(), next_speed, ()

    def _retain(
        self,
        decision_input: DecisionInput,
        reason: str,
        start: float,
        result: SearchResult | None = None,
        extra: tuple[str, ...] = (),
    ) -> Decision:
        self.pending_attack = False
        self.last_family = ActionFamily.REFERENCE
        return Decision(
            family=ActionFamily.REFERENCE,
            p_k_dc_w=0.0,
            target_speed_mps=_target_speed(ActionFamily.REFERENCE, decision_input.ego_speed_mps),
            status="RETAIN_REFERENCE" if reason != "PLAN_INVALID" else "FALLBACK",
            reason_codes=[reason, *extra],
            action_values=(
                {f.value: c for f, c in result.action_mean_cost.items()} if result else {}
            ),
            runtime_s=time.perf_counter() - start,
            search_iterations=result.iterations if result else 0,
            timed_out=result.timed_out if result else False,
            # Hold the side offset while alongside, so the ego does not steer
            # back into a rival it is passing; recentre once clearly clear.
            lateral_target_m=(
                self._last_lateral_m if abs(decision_input.gap_m) < 8.0 else 0.0
            ),
        )

    # -- causal feedback ---------------------------------------------------
    def notify_observation(self, rival_speed_mps: float) -> None:
        """Update the belief from the rival's public speed response."""
        policies = {p.policy for p in self.belief.particles}
        if self.response_fn is not None:
            expected = {p: self.response_fn(self.last_family, p) for p in policies}
        else:
            config = self.rival_config
            expected = {
                p: rival_target_speed(
                    p, self.last_family, 0.0, config.reaction_delay_s, config
                )
                for p in policies
            }
        self.belief.update_on_observation(rival_speed_mps, expected)
        self.belief.mix_for_non_stationarity()

    def notify_commitment_outcome(self, attacked: bool, gained: bool) -> None:
        self.belief.update_on_outcome(attacked, gained)


def _decision_from_search(
    result: SearchResult, decision_input: DecisionInput, elapsed: float
) -> Decision:
    family = result.best_action
    return Decision(
        family=family,
        p_k_dc_w=_power_for_family(family, TacticalParams()),
        target_speed_mps=_target_speed(family, decision_input.ego_speed_mps),
        status="RECOMMEND",
        reason_codes=["STATIONARY_RIVAL_PLANNER"],
        action_values={f.value: c for f, c in result.action_mean_cost.items()},
        runtime_s=elapsed,
        search_iterations=result.iterations,
        timed_out=result.timed_out,
        lateral_target_m=_target_lateral(family),
    )
