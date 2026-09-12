"""Remaining-race value recursion: monotonicity, domain and reserve pricing."""

from __future__ import annotations

import math

import pytest

from gridops.contracts.state import BatteryParams
from gridops.race_value.lap_map import (
    LapMapConfig,
    RaceValueMap,
    default_terminal_value,
    usable_energy_for_soc,
)


@pytest.fixture()
def battery() -> BatteryParams:
    return BatteryParams()


@pytest.fixture()
def value_map(battery: BatteryParams) -> RaceValueMap:
    return RaceValueMap(
        default_terminal_value(battery),
        LapMapConfig(laps=8, n_energy_levels=81, max_energy_j=3_936_600.0),
    )


def test_terminal_value_is_priced_at_zero_laps(
    value_map: RaceValueMap, battery: BatteryParams
) -> None:
    energy = usable_energy_for_soc(0.7, battery)
    assert value_map.value(energy, 0) == pytest.approx(
        value_map.terminal_value.cost_s(energy)
    )


def test_value_grows_with_laps_remaining(value_map: RaceValueMap, battery: BatteryParams) -> None:
    energy = usable_energy_for_soc(0.7, battery)
    values = [value_map.value(energy, laps) for laps in range(0, 6)]
    for earlier, later in zip(values, values[1:]):
        assert later > earlier


def test_out_of_domain_is_flagged_not_extrapolated(
    value_map: RaceValueMap, battery: BatteryParams
) -> None:
    below = value_map.terminal_value.reserve.floor_j - 1.0
    query = value_map.query(below, 5)
    assert not query.in_domain
    assert query.reason == "out_of_domain"
    assert math.isnan(query.value_s)
    assert math.isnan(value_map.deploy_target(below, 5))


def test_negative_laps_flagged(value_map: RaceValueMap, battery: BatteryParams) -> None:
    query = value_map.query(usable_energy_for_soc(0.7, battery), -1)
    assert not query.in_domain and query.reason == "negative_laps"


def test_deploy_target_never_breaks_the_reserve_floor(
    value_map: RaceValueMap, battery: BatteryParams
) -> None:
    for frac in (0.2, 0.4, 0.6, 0.8, 0.95):
        energy = usable_energy_for_soc(frac, battery)
        target = value_map.deploy_target(energy, 5)
        assert target >= -1e-9
        assert energy - target >= value_map.terminal_value.reserve.floor_j - 1.0


def test_scarce_energy_does_not_deploy_more_than_rich(
    value_map: RaceValueMap, battery: BatteryParams
) -> None:
    rich = value_map.deploy_target(usable_energy_for_soc(0.9, battery), 5)
    poor = value_map.deploy_target(usable_energy_for_soc(0.2, battery), 5)
    assert poor <= rich + 1e-6


def test_deploy_target_respects_the_per_lap_cap(battery: BatteryParams) -> None:
    config = LapMapConfig(laps=4, max_deploy_per_lap_j=200_000.0, n_energy_levels=41)
    value_map = RaceValueMap(default_terminal_value(battery), config)
    target = value_map.deploy_target(usable_energy_for_soc(0.9, battery), 3)
    assert target <= config.max_deploy_per_lap_j + 1.0


def test_query_carries_provenance(value_map: RaceValueMap, battery: BatteryParams) -> None:
    query = value_map.query(usable_energy_for_soc(0.7, battery), 3)
    assert query.in_domain and query.provenance == "synthetic_parameter"


def test_r08_terminal_cost_depends_on_laps_remaining(battery: BatteryParams) -> None:
    """The tactical surrogate must see different continuation values by lap."""
    from gridops.contracts.state import ActionFamily
    from gridops.decision.tactical import TacticalModel, TacticalState
    from gridops.simulation.rivals import RivalPolicy

    value_map = RaceValueMap(
        default_terminal_value(battery),
        LapMapConfig(laps=20, n_energy_levels=81, max_energy_j=3_936_600.0),
    )
    short = TacticalModel(
        default_terminal_value(battery), 3,
        terminal_cost_fn=lambda energy: value_map.value(energy, 2),
    )
    long = TacticalModel(
        default_terminal_value(battery), 3,
        terminal_cost_fn=lambda energy: value_map.value(energy, 18),
    )
    state = TacticalState(energy_j=2_000_000.0, gap_m=6.0, policy=RivalPolicy.CONSERVING)
    assert short.terminal_cost(state) != long.terminal_cost(state)


def test_r08_deploy_target_shrinks_with_more_laps_remaining(
    value_map: RaceValueMap, battery: BatteryParams
) -> None:
    energy = usable_energy_for_soc(0.6, battery)
    assert value_map.deploy_target(energy, 2) >= value_map.deploy_target(energy, 18)
