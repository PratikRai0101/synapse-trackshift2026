import pytest

from src.intelligence.lap_strategy import (
    LapTimeMap, LapTimeSample, RaceEnergyPlanner, StrategyConfig,
)


def fitted_map():
    return LapTimeMap(bin_width=5).fit([
        LapTimeSample(90.0, 0, 0, 0),
        LapTimeSample(89.0, 5, 0, 0),
        LapTimeSample(88.0, 10, 0, 0),
        LapTimeSample(91.0, 0, 0, 5),
    ])


def test_map_requires_fit_and_predicts_nearest_bucket():
    lap_map = LapTimeMap()
    with pytest.raises(RuntimeError):
        lap_map.predict(LapTimeSample(1, 0))
    assert lap_map.fit([LapTimeSample(90, 0)]).predict(LapTimeSample(1, 0)) == 90


def test_planner_returns_one_target_per_lap_and_preserves_reserve():
    planner = RaceEnergyPlanner(
        fitted_map(),
        StrategyConfig(lap_count=4, energy_step=5, minimum_reserve=5),
    )
    targets = planner.plan(initial_energy=30)
    assert len(targets) == 4
    assert all(target.deploy_energy >= 0 for target in targets)
    assert targets[-1].reserve_after_lap >= 0
    assert sum(target.deploy_energy for target in targets) <= 30


def test_more_energy_does_not_make_the_first_target_slower():
    planner = RaceEnergyPlanner(
        fitted_map(),
        StrategyConfig(lap_count=3, energy_step=5, minimum_reserve=5),
    )
    low = planner.plan(initial_energy=15)[0]
    high = planner.plan(initial_energy=30)[0]
    assert high.target_lap_time_s <= low.target_lap_time_s
