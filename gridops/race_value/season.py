"""Block 1 — synthetic season lifecycle dynamic program.

A small finite-horizon problem over a season of events with two component-health
aspects (capacity retention and resistance growth), a replacement option and a
synthetic replacement penalty. It produces a **local marginal resource price**,
which is exactly what the specification calls *season-informed*: a configured
lifecycle price is sufficient for the interface, but this is not a calibrated
championship optimisation.

The payoff and wear maps are explicit and synthetic. There is no claim about real
battery life or real championship points.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class SeasonConfig:
    n_events: int = 24
    capacity_buckets: int = 11
    resistance_buckets: int = 11
    capacity_loss_per_event: float = 0.012
    resistance_growth_per_event: float = 0.010
    events_per_component: int = 8
    replacement_penalty: float = 1.5   # synthetic points cost of taking a new unit
    performance_weight: float = 40.0   # synthetic points sensitivity to health
    reference_capacity_retention: float = 1.0
    reference_resistance_growth: float = 1.0


@dataclass
class SeasonResult:
    value: float
    replacement_events: tuple[int, ...]
    marginal_stress_price: float
    provenance: str = "synthetic_parameter"


class SeasonLifecycle:
    """Finite-horizon DP over (capacity retention, resistance growth)."""

    def __init__(self, config: SeasonConfig | None = None) -> None:
        self.config = config or SeasonConfig()
        self._capacity_grid = [
            self.config.reference_capacity_retention
            - i * (1.0 - 0.80) / (self.config.capacity_buckets - 1)
            for i in range(self.config.capacity_buckets)
        ]
        self._resistance_grid = [
            self.config.reference_resistance_growth
            + i * (1.6 - 1.0) / (self.config.resistance_buckets - 1)
            for i in range(self.config.resistance_buckets)
        ]
        self._value: list[list[list[float]]] = []
        self._policy: list[list[list[bool]]] = []
        self._solve()

    # -- public ------------------------------------------------------------
    def solve(self) -> SeasonResult:
        first = self._value[0][-1][-1]
        replacements: list[int] = []
        cap_idx = 0
        res_idx = 0
        for event in range(self.config.n_events):
            if self._policy[event][cap_idx][res_idx]:
                replacements.append(event)
                cap_idx, res_idx = 0, 0
            cap_idx, res_idx = self._advance(cap_idx, res_idx)
        return SeasonResult(
            value=first,
            replacement_events=tuple(replacements),
            marginal_stress_price=self.marginal_stress_price(),
        )

    def marginal_stress_price(self) -> float:
        """Synthetic time-equivalent price of one event of additional wear."""
        fresh = self._value[0][0][0]
        worn = self._value[0][1][1]
        return float(worn - fresh)

    # -- internals ---------------------------------------------------------
    def _performance(self, cap_idx: int, res_idx: int) -> float:
        capacity = self._capacity_grid[cap_idx]
        resistance = self._resistance_grid[res_idx]
        # synthetic points lost per event as health degrades
        return -self.config.performance_weight * (
            (1.0 - capacity) + 0.5 * (resistance - 1.0)
        )

    def _advance(self, cap_idx: int, res_idx: int) -> tuple[int, int]:
        cap_step = (1.0 - 0.80) / (self.config.capacity_buckets - 1)
        res_step = (1.6 - 1.0) / (self.config.resistance_buckets - 1)
        dc = self.config.capacity_loss_per_event / cap_step
        dr = self.config.resistance_growth_per_event / res_step
        return (
            min(self.config.capacity_buckets - 1, int(round(cap_idx + dc))),
            min(self.config.resistance_buckets - 1, int(round(res_idx + dr))),
        )

    def _solve(self) -> None:
        cfg = self.config
        n_cap, n_res = cfg.capacity_buckets, cfg.resistance_buckets
        # terminal value: a worn unit is worth less at the end of the season
        self._value = [
            [
                [self._performance(cap, res) for res in range(n_res)]
                for cap in range(n_cap)
            ]
        ]
        self._policy = [
            [[False] * n_res for _ in range(n_cap)]
        ]
        for _ in range(cfg.n_events):
            previous = self._value[-1]
            values = [[0.0] * n_res for _ in range(n_cap)]
            policies = [[False] * n_res for _ in range(n_cap)]
            for cap in range(n_cap):
                for res in range(n_res):
                    nxt_cap, nxt_res = self._advance(cap, res)
                    run_cost = self._performance(cap, res) + previous[nxt_cap][nxt_res]
                    replace_cost = (
                        -cfg.replacement_penalty + previous[0][0]
                    )
                    if replace_cost > run_cost:
                        values[cap][res] = replace_cost
                        policies[cap][res] = True
                    else:
                        values[cap][res] = run_cost
                        policies[cap][res] = False
            self._value.append(values)
            self._policy.append(policies)
