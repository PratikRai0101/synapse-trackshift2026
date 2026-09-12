"""Persistent particle belief over rival capability and response policy.

The rival's reserve and policy are hidden. The belief carries a weighted
particle set and is updated causally. It also models non-stationarity: the
opponent's policy may switch, so the posterior is mixed back toward the prior
at a slow rate rather than collapsing onto one family.

A failed ego commitment is evidence of a stronger rival. That update is what
bounds repeated futile attempts in the commitment layer.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Sequence

from ..simulation.rivals import REACTIVE_POLICIES, RivalPolicy


DEFENSIVE: frozenset[RivalPolicy] = frozenset(
    {RivalPolicy.MATCHING, RivalPolicy.AGGRESSIVE, RivalPolicy.DELAYED}
)
WEAK: frozenset[RivalPolicy] = frozenset(
    {RivalPolicy.CONSERVING, RivalPolicy.IGNORING, RivalPolicy.STATIONARY}
)


@dataclass
class RivalParticle:
    policy: RivalPolicy
    reserve_fraction: float   # fraction of usable electrical energy
    car_scale: float          # relative pace multiplier
    weight: float = 1.0

    @property
    def deployable_energy_j(self) -> float:
        return self.reserve_fraction


class RivalBelief:
    def __init__(
        self,
        particles: Sequence[RivalParticle],
        switch_rate: float = 0.05,
    ) -> None:
        if not particles:
            raise ValueError("belief requires at least one particle")
        self._particles = list(particles)
        self.switch_rate = switch_rate
        self._normalize()

    # -- access ------------------------------------------------------------
    @property
    def particles(self) -> tuple[RivalParticle, ...]:
        return tuple(self._particles)

    def sample(self, rng: random.Random) -> RivalParticle:
        weights = [p.weight for p in self._particles]
        return rng.choices(self._particles, weights=weights, k=1)[0]

    def capability_forecast(self) -> dict[str, float]:
        """Public summary: response-capability spread, never a rival SOC gauge."""
        total = sum(p.weight for p in self._particles) or 1.0
        by_policy: dict[str, float] = {}
        for particle in self._particles:
            by_policy[particle.policy.value] = (
                by_policy.get(particle.policy.value, 0.0) + particle.weight / total
            )
        reserves = sorted(p.reserve_fraction for p in self._particles)
        return {
            "policy_mass": by_policy,
            "reserve_median": reserves[len(reserves) // 2],
            "reserve_p10": reserves[max(0, int(0.1 * len(reserves)) - 1)],
            "reserve_p90": reserves[min(len(reserves) - 1, int(0.9 * len(reserves)))],
            "strong_rival_mass": self.strong_rival_mass(),
        }

    def strong_rival_mass(self) -> float:
        total = sum(p.weight for p in self._particles) or 1.0
        return sum(p.weight for p in self._particles if p.policy in DEFENSIVE) / total

    def credible_set(self, epsilon: float = 0.05) -> tuple[list[RivalParticle], float]:
        """Highest-density credible set and the excluded probability mass.

        Worst-case commitment over *all* particles is unusably conservative: a
        single low-weight defensive hypothesis vetoes every attack forever. The
        retained set keeps the smallest group whose mass reaches ``1 - epsilon``
        and reports the mass it excludes, per the specification's requirement to
        expose excluded probability rather than silently dropping scenarios.
        """
        ordered = sorted(self._particles, key=lambda p: p.weight, reverse=True)
        kept: list[RivalParticle] = []
        cumulative = 0.0
        for particle in ordered:
            kept.append(particle)
            cumulative += particle.weight
            if cumulative >= 1.0 - epsilon:
                break
        excluded = max(0.0, 1.0 - cumulative)
        return kept, excluded

    def ambiguity_index(self) -> float:
        """Normalised entropy of the policy posterior: 0 = resolved, 1 = uniform."""
        import math

        total = sum(p.weight for p in self._particles) or 1.0
        masses: dict[RivalPolicy, float] = {}
        for particle in self._particles:
            masses[particle.policy] = masses.get(particle.policy, 0.0) + particle.weight / total
        if len(masses) <= 1:
            return 0.0
        entropy = -sum(m * math.log(m) for m in masses.values() if m > 0.0)
        return entropy / math.log(len(masses))

    # -- causal updates ----------------------------------------------------
    def update_on_outcome(self, ego_attacked: bool, gained: bool) -> None:
        """Update on the *outcome of an attempted action*, not on hidden truth."""
        if not ego_attacked:
            return
        for particle in self._particles:
            if gained:
                particle.weight *= 1.6 if particle.policy in WEAK else 0.8
            else:
                particle.weight *= 1.6 if particle.policy in DEFENSIVE else 0.8
        self._normalize()

    def update_on_observation(
        self, observed_gap_closed_m: float, expected_by_policy: dict[RivalPolicy, float]
    ) -> None:
        """Reweight by whether the observed response is closer to the weak or the
        defensive expectation.

        A magnitude-exact Gaussian likelihood is brittle here: the surrogate's
        closure scale need not match the plant's, so a genuinely weak rival can
        be read as defensive. The update therefore discriminates on the sign of
        ``observed - midpoint`` with a soft, bounded strength.
        """
        import math

        weak_vals = [expected_by_policy[p] for p in expected_by_policy if p in WEAK]
        strong_vals = [expected_by_policy[p] for p in expected_by_policy if p in DEFENSIVE]
        if not weak_vals or not strong_vals:
            return
        weak_mean = sum(weak_vals) / len(weak_vals)
        strong_mean = sum(strong_vals) / len(strong_vals)
        if abs(weak_mean - strong_mean) < 1e-9:
            return  # action is uninformative: expectations do not separate
        midpoint = 0.5 * (weak_mean + strong_mean)
        strength = math.tanh(
            (observed_gap_closed_m - midpoint) / max(1.0, abs(weak_mean - strong_mean))
        )
        weak_factor = max(0.1, 1.0 + 0.9 * strength)
        strong_factor = max(0.1, 1.0 - 0.9 * strength)
        for particle in self._particles:
            particle.weight *= weak_factor if particle.policy in WEAK else strong_factor
        self._normalize()

    def mix_for_non_stationarity(self) -> None:
        """Slow mixing toward the prior: the opponent's policy can change."""
        n = len(self._particles)
        uniform = 1.0 / n
        for particle in self._particles:
            particle.weight = (
                (1.0 - self.switch_rate) * particle.weight + self.switch_rate * uniform
            )
        self._normalize()

    # -- constructors ------------------------------------------------------
    @classmethod
    def uniform(
        cls,
        policies: Sequence[RivalPolicy] = REACTIVE_POLICIES,
        reserve_levels: Sequence[float] = (0.2, 0.5, 0.8),
        car_scales: Sequence[float] = (0.98, 1.0, 1.02),
    ) -> "RivalBelief":
        particles = [
            RivalParticle(policy=policy, reserve_fraction=reserve, car_scale=scale)
            for policy in policies
            for reserve in reserve_levels
            for scale in car_scales
        ]
        return cls(particles)

    @classmethod
    def sparse_history(cls) -> "RivalBelief":
        """Fallback when little is known: wide spread, no unwarranted confidence."""
        return cls(
            [
                RivalParticle(RivalPolicy.STATIONARY, 0.5, 1.0, 1.0),
                RivalParticle(RivalPolicy.MATCHING, 0.5, 1.0, 1.0),
                RivalParticle(RivalPolicy.CONSERVING, 0.5, 1.0, 1.0),
            ]
        )

    def _normalize(self) -> None:
        total = sum(p.weight for p in self._particles)
        if total <= 0.0:
            for particle in self._particles:
                particle.weight = 1.0 / len(self._particles)
            return
        for particle in self._particles:
            particle.weight /= total
