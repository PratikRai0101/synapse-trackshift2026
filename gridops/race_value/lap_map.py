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

from dataclasses import dataclass

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


def _state_at(battery: BatteryParams, soc: float):
    from ..contracts.state import BatteryState

    return BatteryState(soc=soc, temp_k=battery.coolant_temp_k)
