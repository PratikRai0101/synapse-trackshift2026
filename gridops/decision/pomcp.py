"""Partially Observable Monte Carlo Planning (POMCP).

History-tree search in belief space over a generative model, as in Silver &
Veness (2010). This is a search layer only: it inherits its cost, action set and
terminal condition from the caller. It does **not** guarantee stalemate
resolution or victory -- bounding indecision is the commitment module's job.

Requirements for a model:

- ``actions(state)``          finite action set
- ``step(state, a, rng)``     -> (next_state, observation, cost)
- ``is_terminal(state)``      horizon / absorbing condition
- ``terminal_cost(state)``    continuation value at the leaf
- ``observation_key(obs)``    hashable grouping of observations

Cost is minimised. Rollouts use ``rollout_action`` when supplied, else a random
action.
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass
from typing import Any, Callable, Hashable, Protocol, Sequence

Action = Any
State = Any
Observation = Any


class GenerativeModel(Protocol):
    def actions(self, state: State) -> Sequence[Action]: ...

    def step(
        self, state: State, action: Action, rng: random.Random
    ) -> tuple[State, Observation, float]: ...

    def is_terminal(self, state: State) -> bool: ...

    def terminal_cost(self, state: State) -> float: ...

    def observation_key(self, observation: Observation) -> Hashable: ...


class _Node:
    __slots__ = ("N", "V", "children", "action_N", "action_V", "belief")

    def __init__(self) -> None:
        self.N = 0
        self.V = 0.0
        self.children: dict[tuple[Action, Hashable], "_Node"] = {}
        self.action_N: dict[Action, int] = {}
        self.action_V: dict[Action, float] = {}
        self.belief: list[State] = []


@dataclass
class SearchResult:
    best_action: Action
    action_mean_cost: dict[Action, float]
    action_visits: dict[Action, int]
    iterations: int
    elapsed_s: float
    timed_out: bool
    root_value: float


class POMCP:
    def __init__(
        self,
        model: GenerativeModel,
        horizon: int,
        iterations: int,
        exploration: float = 1.0,
        gamma: float = 1.0,
        rollout_action: Callable[[State, random.Random], Action] | None = None,
    ) -> None:
        if horizon < 1:
            raise ValueError("horizon must be >= 1")
        if iterations < 1:
            raise ValueError("iterations must be >= 1")
        self.model = model
        self.horizon = horizon
        self.iterations = iterations
        self.exploration = exploration
        self.gamma = gamma
        self.rollout_action = rollout_action

    # -- public ------------------------------------------------------------
    def search(
        self,
        belief: Sequence[State],
        rng: random.Random,
        deadline_s: float | None = None,
    ) -> SearchResult:
        if not belief:
            raise ValueError("belief must contain at least one state")
        root = _Node()
        root.belief = list(belief)
        start = time.perf_counter()
        deadline = None if deadline_s is None else start + deadline_s
        iterations = 0
        timed_out = False

        for _ in range(self.iterations):
            if deadline is not None and time.perf_counter() >= deadline:
                timed_out = True
                break
            state = rng.choice(root.belief)
            self._simulate(state, root, self.horizon, rng, deadline)
            iterations += 1

        means = {
            a: (root.action_V[a] / root.action_N[a])
            for a in root.action_N
            if root.action_N[a] > 0
        }
        if not means:
            # no action was expanded (degenerate budget): fall back to first action
            fallback = self.model.actions(belief[0])[0]
            means = {fallback: float("inf")}
        best = min(means, key=lambda a: means[a])
        return SearchResult(
            best_action=best,
            action_mean_cost=means,
            action_visits=dict(root.action_N),
            iterations=iterations,
            elapsed_s=time.perf_counter() - start,
            timed_out=timed_out,
            root_value=root.V / root.N if root.N > 0 else float("nan"),
        )

    # -- internals ---------------------------------------------------------
    def _simulate(
        self,
        state: State,
        node: _Node,
        depth: int,
        rng: random.Random,
        deadline: float | None,
    ) -> float:
        if depth <= 0 or self.model.is_terminal(state):
            return self.model.terminal_cost(state)
        if deadline is not None and time.perf_counter() >= deadline:
            return self.model.terminal_cost(state)

        actions = list(self.model.actions(state))
        if not actions:
            return self.model.terminal_cost(state)

        if node.N == 0:
            for action in actions:
                node.action_N.setdefault(action, 0)
                node.action_V.setdefault(action, 0.0)
            value = self._rollout(state, depth, rng)
            node.N = 1
            node.V = value
            return value

        action = self._select(node, actions)
        next_state, observation, cost = self.model.step(state, action, rng)
        key = (action, self.model.observation_key(observation))
        child = node.children.get(key)
        if child is None:
            child = _Node()
            child.belief.append(next_state)
            node.children[key] = child
        elif len(child.belief) < 64:
            child.belief.append(next_state)  # particle reinvigoration

        total = cost + self.gamma * self._simulate(next_state, child, depth - 1, rng, deadline)

        node.N += 1
        node.action_N[action] = node.action_N.get(action, 0) + 1
        node.action_V[action] = node.action_V.get(action, 0.0) + total
        node.V += (total - node.V) / node.N
        return total

    def _select(self, node: _Node, actions: Sequence[Action]) -> Action:
        log_n = math.log(node.N + 1.0)
        best_action = actions[0]
        best_score = -math.inf
        for action in actions:
            n = node.action_N.get(action, 0)
            if n == 0:
                return action
            mean = node.action_V[action] / n
            score = -mean + self.exploration * math.sqrt(log_n / n)
            if score > best_score:
                best_score = score
                best_action = action
        return best_action

    def _rollout(self, state: State, depth: int, rng: random.Random) -> float:
        total = 0.0
        discount = 1.0
        for _ in range(depth):
            if self.model.is_terminal(state):
                break
            actions = self.model.actions(state)
            if not actions:
                break
            action = (
                self.rollout_action(state, rng)
                if self.rollout_action is not None
                else rng.choice(actions)
            )
            state, _observation, cost = self.model.step(state, action, rng)
            total += discount * cost
            discount *= self.gamma
        return total + self.model.terminal_cost(state)
