"""Tactical generative model for POMCP.

A cheap surrogate over discrete action families at a decision point. The full
nonlinear plant validates the selected plan; this model only ranks candidates.
Keeping the surrogate cheap is what allows thousands of rollouts.

The terminal cost prices both residual gap and remaining usable energy. That is
the property that makes a futile attack strictly worse than retaining reference.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Hashable, Sequence

from ..contracts.state import ActionFamily
from ..race_value.lap_map import TerminalValue
from ..simulation.rivals import RivalPolicy


FAMILIES: tuple[ActionFamily, ...] = (
    ActionFamily.REFERENCE,
    ActionFamily.ATTACK_NOW,
    ActionFamily.ATTACK_LATER,
    ActionFamily.DEFEND,
    ActionFamily.CONSERVE,
    ActionFamily.PROBE,
)

_DEFENSIVE = frozenset(
    {RivalPolicy.MATCHING, RivalPolicy.AGGRESSIVE, RivalPolicy.DELAYED}
)

#: Declared synthetic energy cost per family (joules).
SPEND_J: dict[ActionFamily, float] = {
    ActionFamily.REFERENCE: 0.0,
    ActionFamily.ATTACK_NOW: 120_000.0,
    ActionFamily.ATTACK_LATER: 40_000.0,
    ActionFamily.DEFEND: 150_000.0,
    ActionFamily.CONSERVE: 0.0,
    ActionFamily.PROBE: 50_000.0,
}

#: Gap closure in metres against a weak rival / against a defensive rival.
_CLOSE_WEAK: dict[ActionFamily, float] = {
    ActionFamily.REFERENCE: 0.0,
    ActionFamily.ATTACK_NOW: 3.0,
    ActionFamily.ATTACK_LATER: 1.0,
    ActionFamily.DEFEND: 0.0,
    ActionFamily.CONSERVE: 0.0,
    ActionFamily.PROBE: 1.5,
}
_CLOSE_DEFENSIVE: dict[ActionFamily, float] = {
    ActionFamily.REFERENCE: 0.0,
    ActionFamily.ATTACK_NOW: 0.0,
    ActionFamily.ATTACK_LATER: 0.0,
    ActionFamily.DEFEND: 0.0,
    ActionFamily.CONSERVE: 0.0,
    ActionFamily.PROBE: 0.0,
}


@dataclass
class TacticalState:
    energy_j: float
    gap_m: float               # positive = ego behind by this many metres
    policy: RivalPolicy
    step: int = 0


@dataclass(frozen=True)
class TacticalParams:
    gap_price_s_per_m: float = 0.02
    noise_m: float = 1.5
    pass_gap_m: float = 0.0

    def spend_j(self, family: ActionFamily) -> float:
        return SPEND_J.get(family, 0.0)


class TacticalModel:
    """Implements the :class:`GenerativeModel` protocol."""

    def __init__(
        self,
        terminal_value: TerminalValue,
        horizon: int,
        params: TacticalParams | None = None,
    ) -> None:
        self.terminal_value = terminal_value
        self.horizon = horizon
        self.params = params or TacticalParams()

    def actions(self, state: TacticalState) -> Sequence[ActionFamily]:
        return FAMILIES

    def step(
        self, state: TacticalState, action: ActionFamily, rng: random.Random
    ) -> tuple[TacticalState, float, float]:
        spend = self.params.spend_j(action)
        energy = max(0.0, state.energy_j - spend)
        closure = self._closure(action, state.policy) + rng.gauss(0.0, self.params.noise_m)
        closure = max(0.0, closure)
        gap = max(0.0, state.gap_m - closure)
        next_state = TacticalState(energy_j=energy, gap_m=gap, policy=state.policy, step=state.step + 1)
        observation = round(closure)
        return next_state, float(observation), 0.0

    def is_terminal(self, state: TacticalState) -> bool:
        return state.step >= self.horizon or state.gap_m <= self.params.pass_gap_m

    def terminal_cost(self, state: TacticalState) -> float:
        return (
            self.terminal_value.cost_s(state.energy_j)
            + self.params.gap_price_s_per_m * state.gap_m
        )

    def observation_key(self, observation: float) -> Hashable:
        return observation

    def _closure(self, action: ActionFamily, policy: RivalPolicy) -> float:
        table = _CLOSE_DEFENSIVE if policy in _DEFENSIVE else _CLOSE_WEAK
        return table.get(action, 0.0)
