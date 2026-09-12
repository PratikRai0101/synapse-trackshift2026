"""Splits and the pitch bundle: distinct physics, grouped reporting."""

from __future__ import annotations

import pytest

from gridops.contracts.state import BatteryParams, VehicleParams
from gridops.evaluation.batch import default_manifest, run_batch
from gridops.evaluation.report import build_bundle, render_markdown
from gridops.evaluation.runner import EpisodeConfig, EpisodeRunner
from gridops.evaluation.splits import apply_battery, apply_vehicle, split_override
from gridops.race_value.lap_map import default_terminal_value
from gridops.simulation.track import synthetic_circuit
from gridops.simulation.tyres import default_tyre_params


def test_test_split_shifts_physics() -> None:
    override = split_override("test")
    battery = apply_battery(BatteryParams(), override)
    vehicle = apply_vehicle(VehicleParams(), override)
    assert battery.resistance_ohm != BatteryParams().resistance_ohm
    assert vehicle.mass_kg != VehicleParams().mass_kg
    assert vehicle.mu_base != VehicleParams().mu_base
    # the controller's models are calibrated on development, not on test
    assert override.calibration_split == "development"


def test_unknown_split_is_rejected() -> None:
    with pytest.raises(ValueError):
        split_override("does-not-exist")


def _factory() -> EpisodeRunner:
    battery = BatteryParams()
    return EpisodeRunner(
        track=synthetic_circuit(),
        vehicle=VehicleParams(),
        battery=battery,
        terminal_value=default_terminal_value(battery),
        config=EpisodeConfig(
            duration_s=6.0, dt_s=0.05, replan_interval_s=1.0,
            decision_budget_s=0.05, rival_progress_m=6.0,
        ),
        tyre_params=default_tyre_params(),
    )


def test_rows_and_bundle_are_grouped_by_split() -> None:
    dev = run_batch(
        default_manifest(seeds=(1,), split="development", controllers=("reference", "m"),
                         policies=("conserving",)),
        _factory,
    )
    test = run_batch(
        default_manifest(seeds=(1,), split="test", controllers=("reference", "m"),
                         policies=("conserving",)),
        _factory,
    )
    payloads = [dev.to_dict(), test.to_dict()]
    assert {row["split"] for row in payloads[0]["rows"]} == {"development"}
    assert {row["split"] for row in payloads[1]["rows"]} == {"test"}

    bundle = build_bundle(payloads)
    assert set(bundle["aggregate_by_split"]) == {"development", "test"}
    markdown = render_markdown(bundle)
    assert "development` split" in markdown and "test` split" in markdown


def test_split_claim_flags_non_transferring_contact_avoidance() -> None:
    bundle = {
        "aggregate_by_split": {
            "development": [{"controller": "m", "total_contacts": 0, "median_final_gap_m": 8.0}],
            "test": [{"controller": "m", "total_contacts": 120, "median_final_gap_m": 30.0}],
        }
    }
    from gridops.evaluation.report import split_claims

    claims = split_claims(bundle["aggregate_by_split"])
    assert claims and claims[0]["status"] == "not met on the held-out split"
