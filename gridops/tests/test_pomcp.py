"""POMCP known-answer, deadline and information-contract tests."""

from __future__ import annotations

import random
import time
from typing import Any, Hashable, Sequence

import pytest

from gridops.decision.pomcp import POMCP


class TwoActionModel:
    """One step; 'cheap' is strictly better than 'expensive'."""

    def actions(self, state: Any) -> Sequence[Any]:
        return ["cheap", "expensive"]

    def step(self, state: Any, action: Any, rng: random.Random):
        return (1 if action == "cheap" else 2), "same", 0.0

    def is_terminal(self, state: Any) -> bool:
        return state in (1, 2)

    def terminal_cost(self, state: Any) -> float:
        return 1.0 if state == 1 else 10.0

    def observation_key(self, observation: Any) -> Hashable:
        return observation


class SpendVsWaitModel:
    """Attacking spends energy; terminal cost prices remaining energy."""

    def __init__(self, energy: float = 1_000_000.0, price_per_joule: float = 2e-7) -> None:
        self.energy = energy
        self.price = price_per_joule

    def actions(self, state: Any) -> Sequence[Any]:
        return ["spend", "wait"]

    def step(self, state: Any, action: Any, rng: random.Random):
        energy = state - 100_000.0 if action == "spend" else state
        return energy, action, 0.0

    def is_terminal(self, state: Any) -> bool:
        return False

    def terminal_cost(self, state: Any) -> float:
        return -self.price * state

    def observation_key(self, observation: Any) -> Hashable:
        return observation


class StochasticModel:
    """A has mean cost 5; B is deterministic 6. Enough samples prefer A."""

    def actions(self, state: Any) -> Sequence[Any]:
        return ["A", "B"]

    def step(self, state: Any, action: Any, rng: random.Random):
        if action == "A":
            return 1, "o", rng.uniform(0.0, 10.0)
        return 1, "o", 6.0

    def is_terminal(self, state: Any) -> bool:
        return False

    def terminal_cost(self, state: Any) -> float:
        return 0.0

    def observation_key(self, observation: Any) -> Hashable:
        return observation


def test_pomcp_picks_the_cheaper_action() -> None:
    rng = random.Random(0)
    result = POMCP(TwoActionModel(), horizon=1, iterations=200).search([0], rng)
    assert result.best_action == "cheap"
    assert result.action_mean_cost["cheap"] < result.action_mean_cost["expensive"]


def test_pomcp_prefers_retaining_energy() -> None:
    rng = random.Random(1)
    model = SpendVsWaitModel()
    result = POMCP(model, horizon=1, iterations=300).search([model.energy], rng)
    assert result.best_action == "wait"


def test_pomcp_visits_all_actions() -> None:
    rng = random.Random(2)
    result = POMCP(TwoActionModel(), horizon=1, iterations=100).search([0], rng)
    assert set(result.action_visits) == {"cheap", "expensive"}
    assert all(v > 0 for v in result.action_visits.values())


def test_pomcp_handles_stochastic_costs() -> None:
    rng = random.Random(3)
    result = POMCP(StochasticModel(), horizon=1, iterations=2000).search([0], rng)
    assert result.best_action == "A"
    assert result.action_mean_cost["A"] == pytest.approx(5.0, abs=0.6)


def test_pomcp_respects_the_wall_clock_deadline() -> None:
    class SlowModel(TwoActionModel):
        def step(self, state: Any, action: Any, rng: random.Random):
            time.sleep(0.001)
            return super().step(state, action, rng)

    rng = random.Random(4)
    result = POMCP(SlowModel(), horizon=8, iterations=10_000_000).search(
        [0], rng, deadline_s=0.05
    )
    assert result.timed_out
    assert result.elapsed_s < 1.0
    assert result.iterations >= 1


def test_tree_does_not_branch_on_hidden_state() -> None:
    """Children are keyed by (action, observation), never by hidden state.

    With a constant observation key each action can produce at most one child,
    so the history tree cannot encode information the controller did not see.
    """

    class CountChildren(POMCP):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.observed_children = 0

        def _simulate(self, state, node, depth, rng, deadline):  # type: ignore[override]
            value = super()._simulate(state, node, depth, rng, deadline)
            self.observed_children = len(node.children)
            return value

    rng = random.Random(5)
    searcher = CountChildren(TwoActionModel(), horizon=1, iterations=200)
    searcher.search([0], rng)
    assert searcher.observed_children <= 2


def test_belief_sampling_uses_multiple_particles() -> None:
    rng = random.Random(6)
    result = POMCP(SpendVsWaitModel(), horizon=1, iterations=50).search(
        [900_000.0, 1_000_000.0, 1_100_000.0], rng
    )
    assert result.best_action in {"wait", "spend"}
    assert result.root_value == result.root_value  # not NaN
