"""Commitment machinery: the anti-attrition core.

A commitment is a **finite contract**: an objective, an energy budget, an expiry
and a success criterion. When it expires without meeting the criterion it is
recorded as futile, the belief should shift toward a stronger rival, and the
next attempt is priced higher. That is what bounds the ego/rival exchange.

Three guards, in order of how much work they do:

1. pricing   -- ``conservative_improvement`` over hypotheses (terminal value)
2. constraint -- ``ReserveGuard`` hard floor
3. anti-churn -- ``NoProgressGuard`` recurrence detection
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence

from ..contracts.state import ActionFamily
from ..race_value.lap_map import ReserveBand


REASON_INSUFFICIENT_RESERVE = "INSUFFICIENT_RESERVE"
REASON_NO_IMPROVEMENT = "NO_IMPROVEMENT"
REASON_NO_PROGRESS = "NO_PROGRESS"
REASON_COOLDOWN = "COOLDOWN"


def conservative_improvement(
    reference_costs: Sequence[float],
    candidate_costs: Sequence[float],
    error_allowance: float = 0.0,
) -> float:
    """Worst-case paired improvement ``min_theta (J_ref - J_cand) - eps``.

    ``error_allowance`` is a declared model-error allowance, not a confidence
    certificate. Both sequences must be aligned on the same hypotheses.
    """
    if len(reference_costs) != len(candidate_costs):
        raise ValueError("reference and candidate costs must align on hypotheses")
    if not reference_costs:
        raise ValueError("at least one hypothesis is required")
    gains = [r - c for r, c in zip(reference_costs, candidate_costs)]
    return min(gains) - error_allowance


def should_commit(improvement: float, margin: float) -> bool:
    return improvement > margin


def cvar_improvement(
    reference_costs: Sequence[float],
    candidate_costs: Sequence[float],
    alpha: float = 0.2,
    error_allowance: float = 0.0,
) -> float:
    """Mean of the ``alpha`` worst paired gains (lower is more conservative).

    ``alpha=1`` reduces to the posterior mean improvement. This is a different
    criterion from the worst-case commitment rule, not a substitute for it.
    """
    if len(reference_costs) != len(candidate_costs):
        raise ValueError("reference and candidate costs must align on hypotheses")
    if not reference_costs:
        raise ValueError("at least one hypothesis is required")
    if not 0.0 < alpha <= 1.0:
        raise ValueError("alpha must be in (0, 1]")
    gains = sorted(r - c for r, c in zip(reference_costs, candidate_costs))
    k = max(1, math.ceil(alpha * len(gains)))
    return sum(gains[:k]) / k - error_allowance


def regret_by_action(
    candidate_costs_by_action: dict[str, Sequence[float]],
) -> dict[str, list[float]]:
    """Per-hypothesis regret of each action relative to the best action."""
    actions = list(candidate_costs_by_action)
    if not actions:
        return {}
    n = len(candidate_costs_by_action[actions[0]])
    for action in actions:
        if len(candidate_costs_by_action[action]) != n:
            raise ValueError("all actions must align on hypotheses")
    best_per_hypothesis = [
        min(candidate_costs_by_action[action][i] for action in actions) for i in range(n)
    ]
    return {
        action: [
            candidate_costs_by_action[action][i] - best_per_hypothesis[i] for i in range(n)
        ]
        for action in actions
    }


def minimax_regret(
    candidate_costs_by_action: dict[str, Sequence[float]],
) -> tuple[str | None, dict[str, float]]:
    """Action minimising the worst per-hypothesis regret, and the regrets."""
    regret = regret_by_action(candidate_costs_by_action)
    if not regret:
        return None, {}
    worst = {action: max(values) for action, values in regret.items()}
    best_action = min(worst, key=lambda action: worst[action])
    return best_action, worst


@dataclass
class Commitment:
    candidate_id: str
    family: ActionFamily
    objective: str
    energy_budget_j: float
    opened_at_s: float
    expires_at_s: float
    success_position_delta_m: float = 0.0
    energy_spent_j: float = 0.0
    resolved: bool = False
    success: bool = False

    def is_futile(self) -> bool:
        return self.resolved and not self.success

    @property
    def expired(self) -> bool:
        return self.resolved


class CommitmentLedger:
    """Tracks finite, expiring commitments and their resource cost."""

    def __init__(self, max_concurrent: int = 1, max_futile_energy_j: float | None = None) -> None:
        self.max_concurrent = max_concurrent
        self.max_futile_energy_j = max_futile_energy_j
        self._active: list[Commitment] = []
        self._history: list[Commitment] = []

    def open(self, commitment: Commitment) -> bool:
        if self.futile_budget_exhausted():
            return False
        if len(self._active) >= self.max_concurrent:
            return False
        self._active.append(commitment)
        return True

    def record_spend(self, energy_j: float) -> None:
        if energy_j <= 0.0:
            return
        for commitment in self._active:
            commitment.energy_spent_j += energy_j

    def tick(self, now_s: float, position_delta_m: float) -> list[Commitment]:
        """Expire due commitments and return those newly resolved."""
        resolved: list[Commitment] = []
        still_active: list[Commitment] = []
        for commitment in self._active:
            achieved = position_delta_m >= commitment.success_position_delta_m
            if now_s >= commitment.expires_at_s:
                commitment.resolved = True
                commitment.success = achieved
                self._history.append(commitment)
                resolved.append(commitment)
            else:
                still_active.append(commitment)
        self._active = still_active
        return resolved

    def abort(self, commitment: Commitment, now_s: float) -> None:
        if commitment in self._active:
            self._active.remove(commitment)
        commitment.resolved = True
        commitment.success = False
        self._history.append(commitment)

    @property
    def active(self) -> tuple[Commitment, ...]:
        return tuple(self._active)

    @property
    def history(self) -> tuple[Commitment, ...]:
        return tuple(self._history)

    @property
    def attempts(self) -> int:
        return len(self._history) + len(self._active)

    @property
    def failures(self) -> int:
        return sum(1 for c in self._history if c.is_futile())

    @property
    def futile_energy_j(self) -> float:
        return sum(c.energy_spent_j for c in self._history if c.is_futile())

    @property
    def failure_rate(self) -> float:
        resolved = len(self._history)
        return (self.failures / resolved) if resolved else 0.0

    def futile_budget_exhausted(self, max_futile_energy_j: float | None = None) -> bool:
        limit = self.max_futile_energy_j if max_futile_energy_j is None else max_futile_energy_j
        if limit is None:
            return False
        return self.futile_energy_j >= limit


@dataclass
class ReserveGuard:
    """Hard floor. Backstop against a mis-specified terminal value."""

    band: ReserveBand

    def check(self, projected_usable_energy_j: float) -> tuple[bool, str | None]:
        if projected_usable_energy_j < self.band.floor_j:
            return False, REASON_INSUFFICIENT_RESERVE
        return True, None

    def clamp_budget(self, current_usable_energy_j: float, desired_spend_j: float) -> float:
        headroom = max(0.0, current_usable_energy_j - self.band.floor_j)
        return min(max(0.0, desired_spend_j), headroom)


@dataclass
class NoProgressGuard:
    """Detects repeated tactical configurations and forces a cooldown."""

    repeat_threshold: int = 3
    cooldown_s: float = 10.0
    position_bucket_m: float = 5.0
    gap_bucket_s: float = 0.5
    energy_bucket_j: float = 50_000.0
    _last_key: tuple[int, int, int] | None = field(default=None, init=False)
    _repeats: int = field(default=0, init=False)
    _cooldown_until_s: float = field(default=float("-inf"), init=False)
    trips: int = field(default=0, init=False)

    def _bucket(self, position_m: float, gap_s: float, energy_j: float) -> tuple[int, int, int]:
        return (
            int(position_m // self.position_bucket_m),
            int(gap_s // self.gap_bucket_s),
            int(energy_j // self.energy_bucket_j),
        )

    def observe(self, now_s: float, position_m: float, gap_s: float, energy_j: float) -> bool:
        key = self._bucket(position_m, gap_s, energy_j)
        if key == self._last_key:
            self._repeats += 1
        else:
            self._last_key = key
            self._repeats = 1
        if self._repeats >= self.repeat_threshold:
            self._cooldown_until_s = now_s + self.cooldown_s
            self._repeats = 0
            self.trips += 1
            return True
        return False

    def is_cooling(self, now_s: float) -> bool:
        return now_s < self._cooldown_until_s
