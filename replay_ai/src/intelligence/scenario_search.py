"""Bounded POMCP-style tactical scenario search.

This is a compact online POMDP baseline: sample a hidden ERS mode from the
current belief, roll out candidate action sequences through a generative rival
model, and retain continuation energy value. It is intentionally bounded and
transparent; the full research implementation can replace the rollout model.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Mapping

from .hierarchical import ERSMode, HMMResult

ACTIONS = ("BURN", "HARVEST", "PROACTIVE TRAP")


@dataclass(frozen=True)
class SearchConfig:
    horizon: int = 5
    rollouts_per_action: int = 64
    seed: int = 17
    energy_cost_burn: float = 8.0
    energy_gain_harvest: float = 3.0
    continuation_weight: float = 0.08


@dataclass(frozen=True)
class SearchResult:
    action: str
    values: Mapping[str, float]
    rollouts: int
    sampled_modes: Mapping[str, int]


class BoundedPOMCP:
    """Root-action Monte Carlo search with hidden-mode sampling."""

    def __init__(self, config: SearchConfig | None = None) -> None:
        self.config = config or SearchConfig()

    def search(self, belief: HMMResult, gap_s: float, energy: float) -> SearchResult:
        cfg = self.config
        rng = random.Random(cfg.seed)
        modes = list(belief.ers_probabilities)
        weights = [belief.ers_probabilities[mode] for mode in modes]
        values = {action: 0.0 for action in ACTIONS}
        sampled = {mode: 0 for mode in modes}
        for root in ACTIONS:
            for _ in range(max(1, cfg.rollouts_per_action)):
                hidden = rng.choices(modes, weights=weights, k=1)[0]
                sampled[hidden] += 1
                current_gap = max(0.0, gap_s)
                current_energy = max(0.0, energy)
                total = 0.0
                action = root
                for depth in range(cfg.horizon):
                    if action == "BURN" and current_energy > 5.0:
                        current_energy -= cfg.energy_cost_burn
                        closure = 0.18 if hidden == ERSMode.DERATE.value else 0.04
                    elif action == "HARVEST":
                        current_energy += cfg.energy_gain_harvest
                        closure = -0.10 if hidden == ERSMode.HARVEST.value else -0.02
                    else:
                        closure = 0.08 if hidden == ERSMode.DERATE.value else 0.0
                    current_gap = max(0.0, current_gap - closure)
                    # Smaller gap is valuable; reserve energy has continuation
                    # value and prevents the search from preferring futile burns.
                    total += -current_gap - cfg.continuation_weight * (100.0 - current_energy)
                    action = ACTIONS[rng.randrange(len(ACTIONS))]
                values[root] += total
        values = {action: value / max(1, cfg.rollouts_per_action)
                  for action, value in values.items()}
        return SearchResult(max(values, key=values.get), values,
                            len(ACTIONS) * max(1, cfg.rollouts_per_action), sampled)
