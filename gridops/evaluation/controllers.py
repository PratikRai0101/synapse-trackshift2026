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
from ..decision.tactical import SPEND_J, TacticalModel, TacticalParams, TacticalState
from ..race_value.lap_map import TerminalValue
from ..simulation.rivals import RivalPolicy


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


class Controller(Protocol):
    def decide(self, decision_input: DecisionInput, budget_s: float) -> Decision: ...

    def notify_gap_change(self, gap_closed_m: float) -> None: ...

    def notify_commitment_outcome(self, attacked: bool, gained: bool) -> None: ...


def _power_for_family(family: ActionFamily, params: TacticalParams) -> float:
    if family is ActionFamily.REFERENCE:
        return 0.0
    if family is ActionFamily.CONSERVE:
        return 15_000.0
    if family is ActionFamily.DEFEND:
        return 120_000.0
    if family is ActionFamily.PROBE:
        return 50_000.0
    return 150_000.0


def _target_speed(family: ActionFamily, current_speed: float) -> float:
    """Reference-paced target; the plant applies the cornering-speed cap."""
    base = 80.0
    if family is ActionFamily.CONSERVE:
        return base - 6.0
    if family is ActionFamily.PROBE:
        return base + 4.0
    if family in (ActionFamily.ATTACK_NOW, ActionFamily.ATTACK_LATER):
        return base + 6.0
    if family is ActionFamily.DEFEND:
        return base + 4.0
    return base


class ReferenceController:
    def decide(self, decision_input: DecisionInput, budget_s: float) -> Decision:
        return Decision(
            family=ActionFamily.REFERENCE,
            p_k_dc_w=0.0,
            target_speed_mps=_target_speed(ActionFamily.REFERENCE, decision_input.ego_speed_mps),
            status="RETAIN_REFERENCE",
            reason_codes=["BASELINE"],
        )

    def notify_gap_change(self, gap_closed_m: float) -> None:
        return None

    def notify_commitment_outcome(self, attacked: bool, gained: bool) -> None:
        return None


def _hypothesis_costs(
    decision_input: DecisionInput,
    families: Sequence[ActionFamily],
    policies: Sequence[RivalPolicy],
    terminal_value: TerminalValue,
    params: TacticalParams,
) -> dict[ActionFamily, list[float]]:
    """Cost of each family under each rival-policy hypothesis (deterministic)."""
    out: dict[ActionFamily, list[float]] = {}
    gap = decision_input.gap_m
    energy = decision_input.ego_usable_energy_j
    for family in families:
        costs: list[float] = []
        spend = SPEND_J.get(family, 0.0)
        for policy in policies:
            closure = _expected_closure(family, policy)
            residual_gap = max(0.0, gap - closure)
            costs.append(
                terminal_value.cost_s(max(0.0, energy - spend))
                + params.gap_price_s_per_m * residual_gap
            )
        out[family] = costs
    return out


def _expected_closure(family: ActionFamily, policy: RivalPolicy) -> float:
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

    def notify_gap_change(self, gap_closed_m: float) -> None:
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
        )

    def notify_gap_change(self, gap_closed_m: float) -> None:
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
        self.rng = random.Random(seed)
        self.reserve_guard = ReserveGuard(terminal_value.reserve)
        self.no_progress = NoProgressGuard(repeat_threshold=4, cooldown_s=3.0)
        self.last_gap_m: float | None = None
        self.pending_attack = False
        self.last_family = ActionFamily.REFERENCE
        self.last_probe_s = float("-inf")
        self.excluded_mass = 0.0

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
        model = TacticalModel(self.terminal_value, self.horizon)
        result = POMCP(model, self.horizon, self.iterations).search(
            states, self.rng, deadline_s=budget_s
        )
        best = result.best_action

        # layer 1 (pricing): worst-case improvement across retained hypotheses
        policies = [p.policy for p in particles]
        costs = _hypothesis_costs(
            decision_input, [ActionFamily.REFERENCE, best], policies, self.terminal_value,
            model.params,
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
            return Decision(
                family=best,
                p_k_dc_w=_power_for_family(best, model.params),
                target_speed_mps=_target_speed(best, decision_input.ego_speed_mps),
                status="RECOMMEND",
                reason_codes=["GAIN_SURVIVES_SCENARIOS"],
                action_values={f.value: c for f, c in result.action_mean_cost.items()},
                runtime_s=time.perf_counter() - start,
                search_iterations=result.iterations,
                timed_out=result.timed_out,
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
                return Decision(
                    family=ActionFamily.PROBE,
                    p_k_dc_w=_power_for_family(ActionFamily.PROBE, model.params),
                    target_speed_mps=_target_speed(
                        ActionFamily.PROBE, decision_input.ego_speed_mps
                    ),
                    status="RECOMMEND",
                    reason_codes=["AMBIGUOUS_CAPABILITY"],
                    action_values={f.value: c for f, c in result.action_mean_cost.items()},
                    runtime_s=time.perf_counter() - start,
                    search_iterations=result.iterations,
                    timed_out=result.timed_out,
                )

        return self._retain(decision_input, REASON_NO_IMPROVEMENT, start, result)

    def _retain(
        self,
        decision_input: DecisionInput,
        reason: str,
        start: float,
        result: SearchResult | None = None,
    ) -> Decision:
        self.pending_attack = False
        self.last_family = ActionFamily.REFERENCE
        return Decision(
            family=ActionFamily.REFERENCE,
            p_k_dc_w=0.0,
            target_speed_mps=_target_speed(ActionFamily.REFERENCE, decision_input.ego_speed_mps),
            status="RETAIN_REFERENCE",
            reason_codes=[reason],
            action_values=(
                {f.value: c for f, c in result.action_mean_cost.items()} if result else {}
            ),
            runtime_s=time.perf_counter() - start,
            search_iterations=result.iterations if result else 0,
            timed_out=result.timed_out if result else False,
        )

    # -- causal feedback ---------------------------------------------------
    def notify_gap_change(self, gap_closed_m: float) -> None:
        expected = {
            policy: _expected_closure(self.last_family, policy)
            for policy in {p.policy for p in self.belief.particles}
        }
        self.belief.update_on_observation(gap_closed_m, expected)
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
    )
