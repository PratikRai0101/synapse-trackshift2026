"""Block 3A — 40-state event-aware HMM over rival mode and reserve.

The hidden state is a *factored* pair::

    x = (mode, reserve_bucket)     5 modes x 8 buckets = 40 states

The point of the extra dimension is the identifiability problem the whole
project is about: a low-reserve rival that is *trying* to defend and a
high-reserve rival that is *choosing* to coast produce similar observable
responses. The reserve factor lets the posterior represent both, rather than
forcing a false choice between them.

Emissions are Gaussian on the observed rival speed response, with the mean
scaled by a declared capability factor, so a depleted rival cannot look as fast
as a full one even under the same mode.

This is a structured 40-state filter, not a reproduction of any specific paper.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Sequence

from ..simulation.rivals import RivalPolicy
from .belief import DEFENSIVE, WEAK, RivalParticle

MODES: tuple[RivalPolicy, ...] = (
    RivalPolicy.CONSERVING,
    RivalPolicy.IGNORING,
    RivalPolicy.STATIONARY,
    RivalPolicy.MATCHING,
    RivalPolicy.AGGRESSIVE,
)

RESERVE_BUCKETS: tuple[float, ...] = (0.05, 0.17, 0.29, 0.41, 0.53, 0.65, 0.77, 0.89)

N_STATES = len(MODES) * len(RESERVE_BUCKETS)


@dataclass
class HMM40Config:
    self_transition: float = 0.88
    reserve_stay: float = 0.85
    reserve_drain: float = 0.10
    reserve_recover: float = 0.05
    emission_sigma_mps: float = 0.8
    stationary: bool = False
    capability_at_zero_reserve: float = 0.40


class HMMBelief40:
    """Forward-filtering HMM over 40 (mode, reserve) states."""

    def __init__(self, config: HMM40Config | None = None) -> None:
        self.config = config or HMM40Config()
        n = N_STATES
        self._posterior = [1.0 / n] * n
        self.transition = self._build_transition()

    # -- structure ---------------------------------------------------------
    @property
    def modes(self) -> tuple[RivalPolicy, ...]:
        return MODES

    @staticmethod
    def _mode_index(state: int) -> int:
        return state // len(RESERVE_BUCKETS)

    @staticmethod
    def _reserve_index(state: int) -> int:
        return state % len(RESERVE_BUCKETS)

    def _build_transition(self) -> list[list[float]]:
        n_modes = len(MODES)
        n_res = len(RESERVE_BUCKETS)
        cfg = self.config
        mode_stay = 1.0 if cfg.stationary else cfg.self_transition
        mode_off = 0.0 if cfg.stationary else (1.0 - mode_stay) / (n_modes - 1)

        def mode_prob(src: int, dst: int) -> float:
            return mode_stay if src == dst else mode_off

        def reserve_prob(src: int, dst: int) -> float:
            if src == dst:
                return cfg.reserve_stay
            if dst == src - 1:
                return cfg.reserve_drain
            if dst == src + 1:
                return cfg.reserve_recover
            return 0.0

        matrix = [[0.0] * N_STATES for _ in range(N_STATES)]
        for s in range(N_STATES):
            ms, rs = self._mode_index(s), self._reserve_index(s)
            for d in range(N_STATES):
                md, rd = self._mode_index(d), self._reserve_index(d)
                matrix[s][d] = mode_prob(ms, md) * reserve_prob(rs, rd)
        return matrix

    # -- inference ---------------------------------------------------------
    def _capability(self, state: int) -> float:
        reserve = RESERVE_BUCKETS[self._reserve_index(state)]
        return self.config.capability_at_zero_reserve + (
            1.0 - self.config.capability_at_zero_reserve
        ) * reserve

    def predict(self) -> list[float]:
        return [
            sum(self._posterior[s] * self.transition[s][d] for s in range(N_STATES))
            for d in range(N_STATES)
        ]

    def update_on_observation(
        self, observed_gap_closed_m: float, expected_by_policy: dict[RivalPolicy, float]
    ) -> None:
        prior = self.predict()
        sigma = max(1e-6, self.config.emission_sigma_mps)
        posterior = [0.0] * N_STATES
        for state in range(N_STATES):
            mode = MODES[self._mode_index(state)]
            mean = expected_by_policy.get(mode, 0.0) * self._capability(state)
            residual = observed_gap_closed_m - mean
            posterior[state] = prior[state] * math.exp(-0.5 * (residual / sigma) ** 2)
        total = sum(posterior)
        self._posterior = prior if total <= 1e-12 else [p / total for p in posterior]
        self._normalize()

    def update_on_outcome(self, ego_attacked: bool, gained: bool) -> None:
        """No-op: the observation carries the evidence; avoid double counting."""
        return None

    def mix_for_non_stationarity(self) -> None:
        """No-op: non-stationarity lives in the transition matrix."""
        return None

    # -- mode-marginal summaries ------------------------------------------
    def policy_mass(self) -> dict[RivalPolicy, float]:
        masses = {mode: 0.0 for mode in MODES}
        for state in range(N_STATES):
            masses[MODES[self._mode_index(state)]] += self._posterior[state]
        return masses

    @property
    def particles(self) -> tuple[RivalParticle, ...]:
        particles: list[RivalParticle] = []
        for mode_index, mode in enumerate(MODES):
            weight = 0.0
            reserve_weighted = 0.0
            for state in range(N_STATES):
                if self._mode_index(state) != mode_index:
                    continue
                w = self._posterior[state]
                weight += w
                reserve_weighted += w * RESERVE_BUCKETS[self._reserve_index(state)]
            reserve = reserve_weighted / weight if weight > 1e-12 else 0.5
            particles.append(
                RivalParticle(
                    policy=mode, reserve_fraction=reserve, car_scale=1.0, weight=weight
                )
            )
        return tuple(particles)

    def strong_rival_mass(self) -> float:
        return sum(self.policy_mass()[m] for m in MODES if m in DEFENSIVE)

    def credible_set(self, epsilon: float = 0.05) -> tuple[list[RivalParticle], float]:
        ordered = sorted(self.particles, key=lambda p: p.weight, reverse=True)
        kept: list[RivalParticle] = []
        cumulative = 0.0
        for particle in ordered:
            kept.append(particle)
            cumulative += particle.weight
            if cumulative >= 1.0 - epsilon:
                break
        return kept, max(0.0, 1.0 - cumulative)

    def ambiguity_index(self) -> float:
        masses = [w for w in self.policy_mass().values() if w > 1e-9]
        if len(masses) <= 1:
            return 0.0
        entropy = -sum(m * math.log(m) for m in masses)
        return entropy / math.log(len(MODES))

    def capability_forecast(self) -> dict[str, float]:
        masses = self.policy_mass()
        reserves = sorted(RESERVE_BUCKETS)
        return {
            "policy_mass": {m.value: w for m, w in masses.items()},
            "reserve_median": reserves[len(reserves) // 2],
            "reserve_p10": reserves[0],
            "reserve_p90": reserves[-1],
            "strong_rival_mass": self.strong_rival_mass(),
            "ambiguity_index": self.ambiguity_index(),
            "states": float(N_STATES),
        }

    def sample(self, rng: random.Random) -> RivalParticle:
        particles = list(self.particles)
        return rng.choices(particles, weights=[p.weight for p in particles], k=1)[0]

    # -- internals ---------------------------------------------------------
    def _normalize(self) -> None:
        total = sum(self._posterior)
        if total <= 0.0:
            self._posterior = [1.0 / N_STATES] * N_STATES
            return
        self._posterior = [p / total for p in self._posterior]
