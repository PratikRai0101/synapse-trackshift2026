"""Compact discrete-mode HMM belief over rival response regimes.

This is the lightweight HMM baseline the specification names, and an alternative
inference backend to the particle ensemble. It exposes the same interface the
controller uses, so M can run on either backend and the two can be compared on
identical information and compute.

Model::

    b^-_t(x') = sum_x P(x' | x, context) b_{t-1}(x)     (predict)
    b_t(x')  proportional to P(o_t | x', context) b^-_t(x')   (update)

The transition matrix encodes non-stationarity (the opponent regime can switch).
Setting ``stationary=True`` reproduces the base-paper assumption of a fixed
regime and is the comparator for the non-stationary claim.

Emissions are Gaussian on the observed gap closure, with the expected closure
per (action, mode) supplied by the caller. The filter is plain forward
filtering; there is no Viterbi smoothing and no learned emission table.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Sequence

from ..simulation.rivals import RivalPolicy
from .belief import DEFENSIVE, WEAK, RivalParticle


#: Nominal reserve encoding per mode; used only where the tactical layer needs a
#: number. It is not a rival SOC estimate and is never displayed as one.
_NOMINAL_RESERVE: dict[RivalPolicy, float] = {
    RivalPolicy.CONSERVING: 0.70,
    RivalPolicy.STATIONARY: 0.50,
    RivalPolicy.IGNORING: 0.50,
    RivalPolicy.MATCHING: 0.45,
    RivalPolicy.AGGRESSIVE: 0.30,
}


@dataclass
class HMMConfig:
    modes: tuple[RivalPolicy, ...] = (
        RivalPolicy.CONSERVING,
        RivalPolicy.IGNORING,
        RivalPolicy.MATCHING,
        RivalPolicy.AGGRESSIVE,
    )
    self_transition: float = 0.90
    stationary: bool = False
    emission_sigma_m: float = 1.5
    prior: tuple[float, ...] | None = None


class HMMBelief:
    """Forward-filtering HMM with the same surface as :class:`RivalBelief`."""

    def __init__(self, config: HMMConfig | None = None) -> None:
        self.config = config or HMMConfig()
        n = len(self.config.modes)
        if n == 0:
            raise ValueError("at least one mode is required")
        if self.config.prior is not None:
            if len(self.config.prior) != n:
                raise ValueError("prior length must match modes")
            self._posterior = list(self.config.prior)
        else:
            self._posterior = [1.0 / n] * n
        self._normalize()
        self.transition = self._build_transition()

    # -- construction ------------------------------------------------------
    def _build_transition(self) -> list[list[float]]:
        modes = self.config.modes
        n = len(modes)
        if self.config.stationary or n == 1:
            return [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]
        stay = min(1.0, max(0.0, self.config.self_transition))
        off = (1.0 - stay) / (n - 1)
        return [[stay if i == j else off for j in range(n)] for i in range(n)]

    @property
    def modes(self) -> tuple[RivalPolicy, ...]:
        return self.config.modes

    @property
    def posterior(self) -> dict[RivalPolicy, float]:
        return {mode: w for mode, w in zip(self.config.modes, self._posterior)}

    @property
    def particles(self) -> tuple[RivalParticle, ...]:
        return tuple(
            RivalParticle(
                policy=mode,
                reserve_fraction=_NOMINAL_RESERVE.get(mode, 0.5),
                car_scale=1.0,
                weight=w,
            )
            for mode, w in zip(self.config.modes, self._posterior)
        )

    # -- inference ---------------------------------------------------------
    def predict(self) -> list[float]:
        n = len(self.config.modes)
        return [
            sum(self._posterior[i] * self.transition[i][j] for i in range(n))
            for j in range(n)
        ]

    def update_on_observation(
        self, observed_gap_closed_m: float, expected_by_policy: dict[RivalPolicy, float]
    ) -> None:
        prior = self.predict()
        sigma = max(1e-6, self.config.emission_sigma_m)
        likelihoods = []
        for mode in self.config.modes:
            expected = expected_by_policy.get(mode, 0.0)
            residual = observed_gap_closed_m - expected
            likelihoods.append(math.exp(-0.5 * (residual / sigma) ** 2))
        posterior = [p * l for p, l in zip(prior, likelihoods)]
        total = sum(posterior)
        if total <= 1e-12:
            # every mode explains the observation poorly: keep the prediction
            # and widen rather than collapse onto one arbitrary mode.
            self._posterior = prior
        else:
            self._posterior = [p / total for p in posterior]
        self._normalize()

    def update_on_outcome(self, ego_attacked: bool, gained: bool) -> None:
        """No-op: the observation update already carries this evidence.

        Updating here as well would double-count a single attempt. Kept so the
        controller interface is identical across belief backends.
        """
        return None

    def mix_for_non_stationarity(self) -> None:
        """No-op: non-stationarity is encoded in the transition matrix."""
        return None

    # -- summaries ---------------------------------------------------------
    def strong_rival_mass(self) -> float:
        return sum(
            w for mode, w in zip(self.config.modes, self._posterior) if mode in DEFENSIVE
        )

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
        positive = [w for w in self._posterior if w > 0.0]
        if len(positive) <= 1:
            return 0.0
        entropy = -sum(w * math.log(w) for w in positive)
        return entropy / math.log(len(positive))

    def capability_forecast(self) -> dict[str, float]:
        reserves = sorted(_NOMINAL_RESERVE.get(m, 0.5) for m in self.config.modes)
        return {
            "policy_mass": {m.value: w for m, w in self.posterior.items()},
            "reserve_median": reserves[len(reserves) // 2],
            "reserve_p10": reserves[0],
            "reserve_p90": reserves[-1],
            "strong_rival_mass": self.strong_rival_mass(),
            "ambiguity_index": self.ambiguity_index(),
        }

    def sample(self, rng: random.Random) -> RivalParticle:
        return rng.choices(self.particles, weights=[p.weight for p in self.particles], k=1)[0]

    # -- internals ---------------------------------------------------------
    def _normalize(self) -> None:
        total = sum(self._posterior)
        if total <= 0.0:
            n = len(self._posterior)
            self._posterior = [1.0 / n] * n
            return
        self._posterior = [w / total for w in self._posterior]
