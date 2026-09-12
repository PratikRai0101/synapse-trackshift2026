"""Conditional convex planner: DCP, residuals, bounds and scarcity response."""

from __future__ import annotations

import numpy as np
import pytest

from gridops.contracts.state import (
    BatteryParams,
    VehicleParams,
    cornering_speed_limit_mps,
)
from gridops.decision.planning import ConditionalConvexPlanner, PlannerConfig
from gridops.race_value.lap_map import default_terminal_value, usable_energy_for_soc
from gridops.simulation.track import synthetic_circuit


@pytest.fixture()
def planner() -> ConditionalConvexPlanner:
    battery = BatteryParams()
    return ConditionalConvexPlanner(
        track=synthetic_circuit(),
        vehicle=VehicleParams(),
        battery=battery,
        terminal_value=default_terminal_value(battery),
        config=PlannerConfig(horizon_m=500.0, ds_m=50.0),
    )


def _plan(planner: ConditionalConvexPlanner, energy_j: float, speed: float = 80.0):
    return planner.plan(
        progress_m=0.0,
        speed_mps=speed,
        usable_energy_j=energy_j,
        base_speed_mps=85.0,
    )


def test_planner_is_dcp_and_optimal(planner: ConditionalConvexPlanner) -> None:
    plan = _plan(planner, usable_energy_for_soc(0.70, planner.battery))
    assert plan.is_dcp
    assert plan.status == "optimal", plan.notes
    assert plan.accepted


def test_residuals_are_within_tolerance(planner: ConditionalConvexPlanner) -> None:
    plan = _plan(planner, usable_energy_for_soc(0.70, planner.battery))
    ok, problems = planner.validate_plan(plan)
    assert ok, problems
    assert plan.max_dynamics_residual_mj < 1e-6
    assert plan.max_grip_residual_n < 1e-3


def test_power_bounds_are_respected(planner: ConditionalConvexPlanner) -> None:
    plan = _plan(planner, usable_energy_for_soc(0.70, planner.battery))
    assert np.all(plan.p_k_dc_w >= -1e-6)
    assert np.all(plan.p_k_dc_w <= planner.config.p_max_w + 1e-3)
    assert plan.max_power_violation_w < 1e-6


def test_trust_region_bounds_the_planned_speed(planner: ConditionalConvexPlanner) -> None:
    plan = _plan(planner, usable_energy_for_soc(0.70, planner.battery))
    n = len(plan.p_k_dc_w)
    for k in range(n):
        v_ref = planner.reference_speed(float(plan.s_m[k]), 85.0, planner.vehicle.mass_kg)
        assert plan.speed_mps[k] <= v_ref + planner.config.trust_dv_mps + 1e-3
        assert plan.speed_mps[k] >= max(
            planner.config.min_speed_mps, v_ref - planner.config.trust_dv_mps
        ) - 1e-3


def test_planned_speed_never_exceeds_the_corner_limit(planner: ConditionalConvexPlanner) -> None:
    plan = _plan(planner, usable_energy_for_soc(0.70, planner.battery))
    for k in range(len(plan.p_k_dc_w)):
        limit = cornering_speed_limit_mps(
            float(plan.s_m[k]), planner.track, planner.vehicle, planner.vehicle.mass_kg
        )
        assert plan.speed_mps[k] <= limit + planner.config.trust_dv_mps + 1e-3


def test_terminal_reserve_floor_is_respected(planner: ConditionalConvexPlanner) -> None:
    plan = _plan(planner, usable_energy_for_soc(0.70, planner.battery))
    assert plan.terminal_energy_j >= planner.terminal_value.reserve.floor_j - 1.0


def test_scarce_energy_reduces_deployment(planner: ConditionalConvexPlanner) -> None:
    rich = _plan(planner, usable_energy_for_soc(0.90, planner.battery))
    poor = _plan(planner, usable_energy_for_soc(0.30, planner.battery))
    assert rich.accepted and poor.accepted
    assert poor.deployed_energy_j < rich.deployed_energy_j


def test_infeasible_target_is_reported_not_hidden(planner: ConditionalConvexPlanner) -> None:
    below_floor = planner.terminal_value.reserve.floor_j - 10_000.0
    plan = _plan(planner, below_floor)
    assert not plan.accepted
    assert "infeasible" in plan.status
    ok, problems = planner.validate_plan(plan)
    assert not ok and problems


def test_tight_lower_trust_forces_deployment(planner: ConditionalConvexPlanner) -> None:
    """An attack must hold pace, so a tight lower bound forces deployment."""
    energy = usable_energy_for_soc(0.70, planner.battery)
    loose = planner.plan(0.0, 80.0, energy, base_speed_mps=86.0)
    tight = planner.plan(0.0, 80.0, energy, base_speed_mps=86.0, lower_trust_dv_mps=4.0)
    assert loose.accepted and tight.accepted
    assert tight.deployed_energy_j > loose.deployed_energy_j
    for k in range(1, len(tight.p_k_dc_w)):
        v_ref = planner.reference_speed(float(tight.s_m[k]), 86.0, planner.vehicle.mass_kg)
        assert tight.speed_mps[k] >= max(planner.config.min_speed_mps, v_ref - 4.0) - 1e-3


def test_solver_returns_primal_residuals_and_timing(planner: ConditionalConvexPlanner) -> None:
    plan = _plan(planner, usable_energy_for_soc(0.70, planner.battery))
    assert plan.solve_time_s >= 0.0
    assert np.isfinite(plan.max_dynamics_residual_mj)
    assert np.isfinite(plan.predicted_time_s)
    assert plan.predicted_time_s > 0.0
