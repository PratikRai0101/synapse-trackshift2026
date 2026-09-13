"""Particle-based POMCP tactical search for hidden rival ERS state."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Mapping

from .hierarchical import ERSMode, HMMResult

ACTIONS = ("BURN", "HARVEST", "PROACTIVE TRAP")


@dataclass(frozen=True)
class SearchConfig:
    horizon: int = 5
    simulations: int = 256
    # Deprecated compatibility knob: old callers requested rollouts per root action.
    rollouts_per_action: int | None = None
    particles: int = 128
    seed: int = 17
    energy_cost_burn: float = 8.0
    energy_gain_harvest: float = 3.0
    continuation_weight: float = 0.08
    discount: float = 0.96
    exploration: float = 1.25
    progressive_widening_constant: float = 1.5
    progressive_widening_exponent: float = 0.5
    risk_aversion: float = 0.20
    transition_noise: float = 0.015


@dataclass(frozen=True)
class RivalParticle:
    mode: str
    gap_s: float
    energy: float


@dataclass
class _ActionStats:
    visits: int = 0
    returns: list[float] = field(default_factory=list)
    observations: dict[str, "_HistoryNode"] = field(default_factory=dict)

    @property
    def mean(self) -> float:
        return sum(self.returns) / len(self.returns) if self.returns else 0.0

    @property
    def variance(self) -> float:
        if len(self.returns) < 2:
            return 0.0
        mean = self.mean
        return sum((value - mean) ** 2 for value in self.returns) / (len(self.returns) - 1)

    @property
    def risk_adjusted(self) -> float:
        return self.mean


@dataclass
class _HistoryNode:
    visits: int = 0
    actions: dict[str, _ActionStats] = field(default_factory=dict)
    particles: list[RivalParticle] = field(default_factory=list)


@dataclass(frozen=True)
class SearchResult:
    action: str
    values: Mapping[str, float]
    rollouts: int
    sampled_modes: Mapping[str, int]
    particle_count: int = 0
    history_count: int = 0
    risk_values: Mapping[str, float] = field(default_factory=dict)


class ParticlePOMCP:
    """Online POMCP with hidden-mode particles and observation histories."""

    def __init__(self, config: SearchConfig | None = None) -> None:
        self.config = config or SearchConfig()
        self._rng = random.Random(self.config.seed)
        self._root = _HistoryNode()
        self._belief: list[RivalParticle] = []

    def _make_particles(self, belief: HMMResult, gap_s: float, energy: float) -> list[RivalParticle]:
        modes = list(belief.ers_probabilities)
        weights = [max(0.0, belief.ers_probabilities[mode]) for mode in modes]
        if sum(weights) <= 0.0:
            # `random.choices` raises "Total of weights must be greater than
            # zero". An upstream filter must never be able to blank the UI, so
            # fall back to an uninformative prior instead of throwing.
            weights = [1.0] * len(modes)
        count = max(1, self.config.particles)
        return [RivalParticle(self._rng.choices(modes, weights=weights, k=1)[0],
                              max(0.0, gap_s), max(0.0, energy))
                for _ in range(count)]

    def _transition_mode(self, mode: str, action: str) -> str:
        # Action-dependent hidden-state dynamics: a rival under pressure is more
        # likely to reveal depletion; harvesting tends to persist for a step.
        draw = self._rng.random()
        if action == "BURN" and mode == ERSMode.HIGH.value and draw < 0.12:
            return ERSMode.DERATE.value
        if action == "HARVEST" and mode == ERSMode.HARVEST.value and draw < 0.08:
            return ERSMode.MEDIUM.value
        if draw < self.config.transition_noise:
            return self._rng.choice(tuple(ERSMode)).value
        return mode

    def _generative_step(self, particle: RivalParticle, action: str) -> tuple[RivalParticle, str, float]:
        cfg = self.config
        mode = self._transition_mode(particle.mode, action)
        energy = particle.energy
        if action == "BURN" and energy > 5.0:
            energy -= cfg.energy_cost_burn
            closure = 0.18 if mode == ERSMode.DERATE.value else 0.04
        elif action == "HARVEST":
            energy += cfg.energy_gain_harvest
            closure = -0.10 if mode == ERSMode.HARVEST.value else -0.02
        else:
            closure = 0.08 if mode == ERSMode.DERATE.value else 0.0
        closure += self._rng.gauss(0.0, cfg.transition_noise)
        gap = max(0.0, particle.gap_s - closure)
        observation = self._observation_bucket(gap, mode)
        reward = (-gap - cfg.continuation_weight * (100.0 - energy) -
                  (0.15 if action == "BURN" and mode != ERSMode.DERATE.value else 0.0))
        return RivalParticle(mode, gap, max(0.0, min(100.0, energy))), observation, reward

    @staticmethod
    def _observation_bucket(gap: float, mode: str) -> str:
        # Public observation intentionally omits the mode; mode only shapes the
        # observed gap response. Bucketing keeps the history tree finite.
        return f"gap:{round(gap, 1):.1f}"

    def _action_limit(self, node: _HistoryNode) -> int:
        cfg = self.config
        return max(1, min(len(ACTIONS), int(
            cfg.progressive_widening_constant * max(1, node.visits) **
            cfg.progressive_widening_exponent)))

    def _select_action(self, node: _HistoryNode) -> str:
        allowed = list(node.actions)
        if len(allowed) < self._action_limit(node):
            remaining = [action for action in ACTIONS if action not in node.actions]
            return remaining[0] if remaining else ACTIONS[0]
        log_visits = math.log(max(1, node.visits))
        return max(
            allowed,
            key=lambda action: node.actions[action].mean +
            self.config.exploration * math.sqrt(log_visits /
                                                  max(1, node.actions[action].visits)),
        )

    def _simulate(self, node: _HistoryNode, particle: RivalParticle, depth: int) -> float:
        if depth >= self.config.horizon:
            return 0.0
        node.visits += 1
        action = self._select_action(node)
        stats = node.actions.setdefault(action, _ActionStats())
        next_particle, observation, immediate = self._generative_step(particle, action)
        child = stats.observations.setdefault(observation, _HistoryNode())
        child.particles.append(next_particle)
        if stats.visits == 0:
            continuation = 0.0
        else:
            continuation = self._simulate(child, next_particle, depth + 1)
        value = immediate + self.config.discount * continuation
        stats.visits += 1
        stats.returns.append(value)
        return value

    def _risk_value(self, stats: _ActionStats) -> float:
        # Mean minus a variance penalty is a transparent risk-sensitive proxy.
        return stats.mean - self.config.risk_aversion * math.sqrt(stats.variance)

    def search(self, belief: HMMResult, gap_s: float, energy: float) -> SearchResult:
        self._rng = random.Random(self.config.seed)
        self._root = _HistoryNode()
        self._belief = self._make_particles(belief, gap_s, energy)
        self._root.particles.extend(self._belief)
        simulations = (self.config.simulations if self.config.rollouts_per_action is None
                       else 3 * max(1, self.config.rollouts_per_action))
        for _ in range(max(1, simulations)):
            particle = self._rng.choice(self._belief)
            self._simulate(self._root, particle, 0)
        risk_values = {action: self._risk_value(self._root.actions[action])
                       for action in self._root.actions}
        values = {action: risk_values.get(action, float("-inf")) for action in ACTIONS}
        sampled = {mode: sum(p.mode == mode for p in self._belief)
                   for mode in belief.ers_probabilities}
        history_count = sum(len(stats.observations) for stats in self._root.actions.values())
        return SearchResult(max(values, key=values.get), values,
                            max(1, simulations), sampled,
                            len(self._belief), history_count, risk_values)


class BoundedPOMCP(ParticlePOMCP):
    """Compatibility alias for callers using the original reference name."""
