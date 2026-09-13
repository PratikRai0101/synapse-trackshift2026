"""Display projection for closed-loop traces.

These tests pin the boundary between what the engine computes (longitudinal
distance, gap, contact) and what the adapter merely displays (a synthetic loop
and a lateral offset). A failure here means the viewer could show something the
simulator did not actually produce.
"""
import math
from dataclasses import dataclass

from src.intelligence.closed_loop import HiddenRivalMode
from src.intelligence.simulation_motion import (
    DT_S,
    LATERAL_OFFSET_M,
    OVERLAP_DISTANCE_M,
    PERIMETER_M,
    TRACK_WIDTH_M,
    build_motion_trace,
    loop_heading,
    loop_point,
    motion_packet,
)


@dataclass
class _Start:
    frame_index: int = 0
    timestamp_s: float = 0.0
    driver: str = "EGO"
    rival: str = "RIV"
    own_speed_kmh: float = 275.0
    rival_speed_kmh: float = 275.0
    gap_s: float = 0.9
    own_energy: float = 70.0
    battery_temperature: float = 70.0
    battery_soh: float = 1.0
    lap: int = 1


def test_trace_is_monotonic_and_one_step_per_model_interval():
    trace = build_motion_trace(_Start(), action="BURN", steps=20)
    assert len(trace) == 20
    assert all(round(b.t_s - a.t_s, 9) == DT_S for a, b in zip(trace, trace[1:]))
    assert all(b.ego_distance_m > a.ego_distance_m for a, b in zip(trace, trace[1:]))


def test_actions_change_the_projected_trajectory():
    burn = build_motion_trace(_Start(), action="BURN", steps=20)
    harvest = build_motion_trace(_Start(), action="HARVEST", steps=20)
    assert abs(burn[-1].ego_distance_m - harvest[-1].ego_distance_m) > 1.0


def test_reference_branch_runs_without_a_forced_action():
    reference = build_motion_trace(_Start(), action=None, steps=10)
    assert len(reference) == 10
    assert reference[-1].ego_energy > 0.0


def test_lateral_offset_only_applies_while_the_cars_overlap():
    trace = build_motion_trace(_Start(), action="BURN", steps=20)
    for step in trace:
        separation = abs(step.rival_distance_m - step.ego_distance_m)
        if separation < OVERLAP_DISTANCE_M:
            # Exactly one car is drawn off the centre line during an overlap.
            ego_off = math.hypot(step.ego_x - loop_point(step.ego_distance_m)[0],
                                 step.ego_y - loop_point(step.ego_distance_m)[1])
            rival_off = math.hypot(step.rival_x - loop_point(step.rival_distance_m)[0],
                                   step.rival_y - loop_point(step.rival_distance_m)[1])
            assert abs(ego_off + rival_off - LATERAL_OFFSET_M) < 1e-6
        else:
            assert (step.ego_x, step.ego_y) == loop_point(step.ego_distance_m)


def test_lateral_offset_stays_inside_the_displayed_track_width():
    trace = build_motion_trace(_Start(), action="BURN", steps=20)
    for step in trace:
        centre_x, centre_y = loop_point(step.ego_distance_m)
        assert math.hypot(step.ego_x - centre_x, step.ego_y - centre_y) <= TRACK_WIDTH_M / 2


def test_heading_matches_the_display_loop_tangent():
    for distance in (0.0, 450.0, 1200.0, PERIMETER_M - 1.0, PERIMETER_M + 10.0):
        x0, y0 = loop_point(distance)
        x1, y1 = loop_point(distance + 1.0)
        expected = math.atan2(x1 - x0, y1 - y0)
        assert abs(loop_heading(distance) - expected) < 1e-9


def test_loop_wraps_instead_of_running_off_the_end():
    assert loop_point(0.0) == loop_point(PERIMETER_M)
    assert loop_point(PERIMETER_M * 2 + 500.0) == loop_point(500.0)


def test_packet_declares_simulation_and_never_leaks_hidden_mode():
    payload = motion_packet(_Start(), action="BURN", steps=10,
                            mode=HiddenRivalMode.DEPLETE)
    assert payload["run_mode"] == "simulated"
    assert payload["coordinate_units"] == "m"
    assert "display projection" in payload["motion_provenance"]
    assert payload["simulation"]["command"] == "BURN"
    assert payload["simulation"]["model"] == "replay_ai.closed_loop"
    assert "deplate" not in str(payload).lower()
    assert "deplete" not in str(payload).lower()


def test_packet_frame_matches_the_last_trace_step_for_late_joiners():
    payload = motion_packet(_Start(), action="HARVEST", steps=8)
    last = payload["trace"][-1]
    ego = payload["frame"]["drivers"]["EGO"]
    assert ego["x"] == last["ego_x"]
    assert ego["fraction"] == last["ego_distance_m"] / PERIMETER_M
    assert payload["simulation"]["gap_s"] == last["gap_s"]


def test_geometry_edges_are_consistent_with_car_projection():
    payload = motion_packet(_Start(), action="BURN", steps=5)
    geometry = payload["track_geometry"]
    assert len(geometry["x"]) == len(geometry["x_inner"]) == len(geometry["x_outer"])
    width = math.hypot(geometry["x_outer"][0] - geometry["x_inner"][0],
                       geometry["y_outer"][0] - geometry["y_inner"][0])
    assert abs(width - TRACK_WIDTH_M) < 0.05
