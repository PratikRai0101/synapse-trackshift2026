"""Frozen paired batch: pairing, determinism, failure accounting, ablations."""

from __future__ import annotations

import pytest

from gridops.contracts.state import BatteryParams, VehicleParams
from gridops.evaluation.batch import (
    BatchManifest,
    default_manifest,
    run_batch,
)
from gridops.evaluation.runner import EpisodeConfig, EpisodeRunner
from gridops.race_value.lap_map import default_terminal_value
from gridops.simulation.track import synthetic_circuit
from gridops.simulation.tyres import default_tyre_params


def _factory() -> EpisodeRunner:
    battery = BatteryParams()
    return EpisodeRunner(
        track=synthetic_circuit(),
        vehicle=VehicleParams(),
        battery=battery,
        terminal_value=default_terminal_value(battery),
        config=EpisodeConfig(
            duration_s=8.0, dt_s=0.05, replan_interval_s=1.0,
            decision_budget_s=0.05, rival_progress_m=6.0,
        ),
        tyre_params=default_tyre_params(),
    )


def _manifest(controllers, policies=("matching", "conserving"), seeds=(1, 2)) -> BatchManifest:
    return default_manifest(
        seeds=seeds, split="development", controllers=tuple(controllers), policies=policies
    )


def test_row_count_matches_the_grid() -> None:
    manifest = _manifest(("reference", "m"), policies=("matching", "conserving"), seeds=(1, 2))
    result = run_batch(manifest, _factory)
    assert len(result.rows) == 2 * 2 * 2


def test_batch_is_deterministic() -> None:
    manifest = _manifest(("reference", "m"), policies=("matching",), seeds=(1, 2))
    first = run_batch(manifest, _factory)
    second = run_batch(manifest, _factory)
    keys = ("controller", "rival_policy", "seed", "status", "final_gap_m", "ego_energy_spent_j")
    assert [[getattr(r, k) for k in keys] for r in first.rows] == [
        [getattr(r, k) for k in keys] for r in second.rows
    ]


def test_completion_rate_is_reported() -> None:
    manifest = _manifest(("reference", "m"), policies=("matching",), seeds=(1,))
    result = run_batch(manifest, _factory)
    assert result.completion_rate("m") == 1.0
    assert result.completion_rate("reference") == 1.0


def test_failures_are_recorded_not_dropped() -> None:
    manifest = _manifest(("bogus_controller",), policies=("matching",), seeds=(1, 2))
    result = run_batch(manifest, _factory)
    assert len(result.rows) == 2
    assert all(row.status == "error" for row in result.rows)
    assert result.completion_rate("bogus_controller") == 0.0
    aggregate = result.aggregate()
    assert aggregate[0]["episodes"] == 2 and aggregate[0]["completed"] == 0
    assert aggregate[0]["completion_rate"] == 0.0


def test_paired_deltas_align_on_seed_and_policy() -> None:
    manifest = _manifest(("reference", "m"), policies=("matching", "conserving"), seeds=(1, 2, 3))
    result = run_batch(manifest, _factory)
    deltas = result.paired_deltas("m", "final_gap_m")
    assert len(deltas) == 2 * 3


def test_aggregate_contains_every_controller() -> None:
    manifest = _manifest(("reference", "m"), policies=("matching",), seeds=(1,))
    result = run_batch(manifest, _factory)
    names = {row["controller"] for row in result.aggregate()}
    assert {"reference", "m"} <= names


def test_method_spends_less_than_the_base_paper_planner() -> None:
    """The batch-level headline: M is far more frugal than B_stat."""
    manifest = _manifest(
        ("stationary", "m"),
        policies=("matching", "aggressive", "conserving"),
        seeds=(1, 2),
    )
    result = run_batch(manifest, _factory)
    by_name = {row["controller"]: row for row in result.aggregate()}
    assert by_name["m"]["mean_energy_spent_j"] < by_name["stationary"]["mean_energy_spent_j"]
    assert by_name["m"]["completion_rate"] == 1.0


def test_ablation_variants_are_distinct_controllers() -> None:
    manifest = _manifest(
        ("m", "m_no_continuation", "m_no_probe", "m_posterior_mean"),
        policies=("conserving",),
        seeds=(1,),
    )
    result = run_batch(manifest, _factory)
    names = {row["controller"] for row in result.aggregate()}
    assert len(names) == 4
    assert all(result.completion_rate(name) == 1.0 for name in names)
