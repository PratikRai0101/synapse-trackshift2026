"""Information-contract and leakage tests.

This is a release gate, not an optional refinement. Hidden rival state and
future samples must not reach a deployable controller.
"""

from __future__ import annotations

import dataclasses

from gridops.contracts.provenance import Provenance
from gridops.contracts.records import DecisionInput, ObservationFrame, RecordHeader
from gridops.contracts.state import BatteryParams, BatteryState, VehicleState
from gridops.evaluation.runner import EpisodeConfig, RivalRuntime, build_decision_input
from gridops.simulation.rivals import RivalPolicy

PROHIBITED_FIELDS = {
    "rival_soc",
    "rival_current_a",
    "rival_temp_k",
    "rival_policy",
    "rival_policy_family",
    "future_telemetry",
    "test_label",
    "privileged_counterfactual",
}


def _frame(available_at_s: float, channel: str = "speed", value: float = 80.0) -> ObservationFrame:
    return ObservationFrame(
        header=RecordHeader(
            run_id="r1",
            record_id=f"o-{available_at_s}-{channel}",
            time_s=0.0,
            source="simulation",
            provenance=Provenance.SIMULATED_MEASUREMENT,
        ),
        sampled_at_s=available_at_s - 0.1,
        available_at_s=available_at_s,
        channels={channel: value},
        units={channel: "m/s"},
    )


def _ego() -> VehicleState:
    return VehicleState(
        progress_m=100.0,
        speed_mps=80.0,
        fuel_kg=0.0,
        battery=BatteryState(soc=0.7, temp_k=BatteryParams().coolant_temp_k),
    )


def test_decision_input_has_no_prohibited_fields() -> None:
    names = {f.name for f in dataclasses.fields(DecisionInput)}
    assert names.isdisjoint(PROHIBITED_FIELDS)


def test_future_observations_are_not_visible() -> None:
    now = 5.0
    frames = [_frame(4.0), _frame(6.0), _frame(5.0)]
    decision_input = build_decision_input(
        _ego(), rival_progress_m=130.0, now_s=now,
        config=EpisodeConfig(), battery=BatteryParams(), observations=frames,
    )
    visible = decision_input.visible_observations()
    assert all(frame.available_at_s <= now for frame in visible)
    assert len(visible) == 2


def test_hidden_rival_state_does_not_change_the_input() -> None:
    cfg = EpisodeConfig()
    battery = BatteryParams()
    public_progress = 130.0

    weak = RivalRuntime(
        state=VehicleState(public_progress, 80.0, 0.0, BatteryState(0.9, 300.0)),
        policy=RivalPolicy.CONSERVING,
    )
    strong = RivalRuntime(
        state=VehicleState(public_progress, 80.0, 0.0, BatteryState(0.05, 340.0)),
        policy=RivalPolicy.MATCHING,
    )

    input_weak = build_decision_input(
        _ego(), weak.state.progress_m, 5.0, cfg, battery
    )
    input_strong = build_decision_input(
        _ego(), strong.state.progress_m, 5.0, cfg, battery
    )
    assert input_weak == input_strong
    # changing the public field does change the input.
    moved = build_decision_input(_ego(), weak.state.progress_m + 25.0, 5.0, cfg, battery)
    assert moved != input_weak


def test_public_progress_does_change_the_input() -> None:
    cfg = EpisodeConfig()
    a = build_decision_input(_ego(), 130.0, 5.0, cfg, BatteryParams())
    b = build_decision_input(_ego(), 155.0, 5.0, cfg, BatteryParams())
    assert a.gap_m != b.gap_m
