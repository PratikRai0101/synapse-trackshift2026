"""Remaining-race resource value.

Supplies the terminal continuation cost that makes deferred energy expensive.
The required first build uses time in seconds as the cost unit; a configured
lifecycle price is labelled season-informed, not a solved season optimisation.

Monotonicity contract
---------------------
``TerminalValue.cost_s`` is **non-increasing in usable energy**. That single
property is what makes a futile commitment (position unchanged, energy spent)
strictly worse than the reference, so the commitment rule rejects it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..contracts.state import BatteryParams
from ..simulation.battery import chemical_energy_j, usable_energy_j


@dataclass(frozen=True)
class ReserveBand:
    """Reachable reserve band handed down from the remaining-race horizon."""

    floor_j: float
    soft_floor_j: float
    ceiling_j: float

    def __post_init__(self) -> None:
        if not (0.0 <= self.floor_j <= self.soft_floor_j <= self.ceiling_j):
            raise ValueError("reserve band must satisfy floor <= soft_floor <= ceiling")


@dataclass(frozen=True)
class TerminalValue:
    """Convex, monotone terminal resource cost (seconds)."""

    seconds_per_joule: float
    reserve: ReserveBand
    shortfall_multiplier: float = 3.0
    stress_price_s_per_unit: float = 0.0

    def cost_s(self, usable_energy_j: float, stress_units: float = 0.0) -> float:
        """Lower is better. Strictly decreasing in energy above the floor."""
        cost = -self.seconds_per_joule * usable_energy_j
        if usable_energy_j < self.reserve.soft_floor_j:
            shortfall = self.reserve.soft_floor_j - usable_energy_j
            cost += self.seconds_per_joule * self.shortfall_multiplier * shortfall
        cost += self.stress_price_s_per_unit * stress_units
        return cost

    def is_feasible(self, usable_energy_j: float) -> bool:
        return usable_energy_j >= self.reserve.floor_j

    def energy_shortfall_j(self, usable_energy_j: float) -> float:
        return max(0.0, self.reserve.floor_j - usable_energy_j)


def default_terminal_value(battery: BatteryParams, seconds_per_megajoule: float = 0.20) -> TerminalValue:
    """Synthetic but explicitly declared resource valuation for the demonstrator."""
    full = chemical_energy_j(_state_at(battery, battery.soc_max), battery)
    empty = 0.0
    span = full - empty
    return TerminalValue(
        seconds_per_joule=seconds_per_megajoule / 1_000_000.0,
        reserve=ReserveBand(
            floor_j=0.05 * span,
            soft_floor_j=0.20 * span,
            ceiling_j=full,
        ),
    )


def usable_energy_for_soc(soc: float, battery: BatteryParams) -> float:
    return usable_energy_j(_state_at(battery, soc), battery)


# ---------------------------------------------------------------------------
# Remaining-race value: finite-horizon recursion over a small resource grid.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LapMapConfig:
    """Declared synthetic lap-map problem.

    The lap-time-versus-energy curve is a declared assumption, not a calibrated
    pace model. Pit plans are held or enumerated externally, not branched here.
    """

    laps: int = 20
    n_energy_levels: int = 201
    max_energy_j: float = 4_000_000.0
    max_deploy_per_lap_j: float = 4_000_000.0
    base_lap_time_s: float = 90.0
    seconds_gained_per_mj: float = 0.35
    stress_price_s_per_j: float = 0.0


@dataclass
class RaceValueQuery:
    value_s: float
    deploy_target_j: float
    laps_remaining: int
    in_domain: bool
    provenance: str = "synthetic_parameter"
    reason: str | None = None


class RaceValueMap:
    """Finite-horizon value recursion over usable electrical energy.

    ``V_l(E) = min_u { t_lap(E, u) + stress(u) + V_{l-1}(E - u) }`` with
    ``V_0(E)`` equal to the terminal resource cost. Terminal reserve is priced
    exactly once, at ``V_0``; no per-lap energy penalty is added on top.

    Out-of-domain queries are flagged, never extrapolated.
    """

    def __init__(self, terminal_value: TerminalValue, config: LapMapConfig | None = None) -> None:
        self.terminal_value = terminal_value
        self.config = config or LapMapConfig()
        floor = terminal_value.reserve.floor_j
        top = max(floor + 1.0, self.config.max_energy_j)
        n = max(3, self.config.n_energy_levels)
        self._grid = [floor + (top - floor) * i / (n - 1) for i in range(n)]
        self._value: list[list[float]] = []
        self._policy: list[list[int]] = []
        self._solve()

    # -- public ------------------------------------------------------------
    def in_domain(self, energy_j: float) -> bool:
        return self._grid[0] <= energy_j <= self._grid[-1]

    def value(self, energy_j: float, laps_remaining: int) -> float:
        return self.query(energy_j, laps_remaining).value_s

    def deploy_target(self, energy_j: float, laps_remaining: int) -> float:
        return self.query(energy_j, laps_remaining).deploy_target_j

    def query(self, energy_j: float, laps_remaining: int) -> RaceValueQuery:
        if not self.in_domain(energy_j):
            return RaceValueQuery(
                value_s=float("nan"),
                deploy_target_j=float("nan"),
                laps_remaining=laps_remaining,
                in_domain=False,
                reason="out_of_domain",
            )
        if laps_remaining < 0:
            return RaceValueQuery(
                value_s=float("nan"),
                deploy_target_j=float("nan"),
                laps_remaining=laps_remaining,
                in_domain=False,
                reason="negative_laps",
            )
        laps = min(laps_remaining, self.config.laps)
        idx = self._nearest_index(energy_j)
        target = self._grid[idx] - self._grid[self._policy[laps][idx]]
        return RaceValueQuery(
            value_s=self._interpolate(self._value[laps], energy_j),
            deploy_target_j=target,
            laps_remaining=laps,
            in_domain=True,
        )

    # -- internals ---------------------------------------------------------
    def _solve(self) -> None:
        grid = self._grid
        n = len(grid)
        floor = self.terminal_value.reserve.floor_j

        self._value.append([self.terminal_value.cost_s(e) for e in grid])
        self._policy.append([i for i in range(n)])  # at V_0 there is no next lap

        for _lap in range(1, self.config.laps + 1):
            previous = self._value[-1]
            values = [math.inf] * n
            policies = [i for i in range(n)]
            for i, energy in enumerate(grid):
                best_value = math.inf
                best_j = i
                for j in range(i + 1):  # spend nothing (j == i) or spend down to j
                    spend = energy - grid[j]
                    if spend > self.config.max_deploy_per_lap_j + 1e-9:
                        break
                    candidate = (
                        self._lap_time_s(spend)
                        + self.config.stress_price_s_per_j * spend
                        + previous[j]
                    )
                    if candidate < best_value:
                        best_value = candidate
                        best_j = j
                values[i] = best_value
                policies[i] = best_j
            self._value.append(values)
            self._policy.append(policies)

        # floor is the grid origin already; keep the reference explicit
        self._floor_j = floor

    def _lap_time_s(self, deploy_j: float) -> float:
        gain = self.config.seconds_gained_per_mj * (deploy_j / 1_000_000.0)
        return max(1.0, self.config.base_lap_time_s - gain)

    def _nearest_index(self, energy_j: float) -> int:
        grid = self._grid
        if energy_j <= grid[0]:
            return 0
        if energy_j >= grid[-1]:
            return len(grid) - 1
        return int(round(self._position(energy_j)))

    def _position(self, energy_j: float) -> float:
        grid = self._grid
        n = len(grid)
        return max(0.0, min(1.0, (energy_j - grid[0]) / (grid[-1] - grid[0]))) * (n - 1)

    def _interpolate(self, level: list[float], energy_j: float) -> float:
        """Linear interpolation between grid points; no extrapolation."""
        n = len(self._grid)
        pos = self._position(energy_j)
        lo = int(math.floor(pos))
        hi = min(lo + 1, n - 1)
        frac = pos - lo
        return level[lo] * (1.0 - frac) + level[hi] * frac


def _state_at(battery: BatteryParams, soc: float):
    from ..contracts.state import BatteryState

    return BatteryState(soc=soc, temp_k=battery.coolant_temp_k)
