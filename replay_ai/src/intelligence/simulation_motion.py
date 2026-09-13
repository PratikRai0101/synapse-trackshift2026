"""Spatial layout for closed-loop simulator traces.

The engine owns longitudinal distance, speed, energy and contact detection.
This adapter projects those distances onto a synthetic closed display track so
the 3D viewer can render an evaluated branch.

The lateral offset used during an overlap is a deterministic **display
projection**, not physical racing-line output. ``motion_provenance`` in the
payload states that, so a viewer can never present it as simulated steering.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Protocol

from .closed_loop import ClosedLoopSimulator, HiddenRivalMode
from .race_physics import CarPose, PassMonitor, TrackGeometry

DT_S = 0.1
# Stadium display loop: two straights joined by semicircles, metres.
STRAIGHT_M = 900.0
RADIUS_M = 400.0
PERIMETER_M = 2 * STRAIGHT_M + 2 * math.pi * RADIUS_M
TRACK_WIDTH_M = 12.0
GENERATED_POINTS = 600
# Below this longitudinal separation the two cars are drawn on parallel lines.
OVERLAP_DISTANCE_M = 8.0
# Lateral offset is applied to the car that is behind in the running order.
LATERAL_OFFSET_M = 1.6


class BranchStartLike(Protocol):
    """Structural contract: only public observed state may enter a branch."""

    frame_index: int
    timestamp_s: float
    driver: str
    rival: str
    own_speed_kmh: float
    rival_speed_kmh: float
    gap_s: float
    own_energy: float
    battery_temperature: float
    battery_soh: float
    lap: int


@dataclass(frozen=True)
class MotionStep:
    t_s: float
    ego_x: float
    ego_y: float
    rival_x: float
    rival_y: float
    ego_heading: float
    rival_heading: float
    ego_distance_m: float
    rival_distance_m: float
    ego_speed_kmh: float
    rival_speed_kmh: float
    ego_energy: float
    gap_s: float
    contact: bool


def loop_point(distance_m: float) -> tuple[float, float]:
    """Position on the display loop at an arc length, wrapped to one lap."""
    d = distance_m % PERIMETER_M
    half = STRAIGHT_M / 2
    if d < STRAIGHT_M:
        return (-half + d, -RADIUS_M)
    d -= STRAIGHT_M
    if d < math.pi * RADIUS_M:
        a = d / RADIUS_M - math.pi / 2
        return (half + math.cos(a) * RADIUS_M, math.sin(a) * RADIUS_M)
    d -= math.pi * RADIUS_M
    if d < STRAIGHT_M:
        return (half - d, RADIUS_M)
    d -= STRAIGHT_M
    a = d / RADIUS_M + math.pi / 2
    return (-half + math.cos(a) * RADIUS_M, math.sin(a) * RADIUS_M)


def loop_heading(distance_m: float) -> float:
    x0, y0 = loop_point(distance_m)
    x1, y1 = loop_point(distance_m + 1.0)
    return math.atan2(x1 - x0, y1 - y0)


def _offset_position(distance_m: float, lateral_m: float) -> tuple[float, float]:
    """Displace from the centre line along the local track normal."""
    x, y = loop_point(distance_m)
    x1, y1 = loop_point(distance_m + 1.0)
    dx, dy = x1 - x, y1 - y
    length = math.hypot(dx, dy) or 1.0
    # Rotate the tangent 90 degrees: the outward normal of the loop.
    return (x + (-dy / length) * lateral_m, y + (dx / length) * lateral_m)


def build_motion_trace(
    branch: BranchStartLike,
    action: str | None = None,
    steps: int = 20,
    seed: int = 0,
    mode: HiddenRivalMode = HiddenRivalMode.MATCH,
) -> list[MotionStep]:
    """Run one branch and project both cars onto the display loop.

    ``action=None`` runs the simulator's own reference policy; a named action
    forces the counterfactual, exactly as ``run_counterfactual`` does.
    """
    simulator = ClosedLoopSimulator(
        mode,
        seed=seed,
        use_mpc=True,
        controller_variant="no_search",
        initial_speed_kmh=branch.own_speed_kmh,
        initial_rival_speed_kmh=branch.rival_speed_kmh,
        initial_gap_s=branch.gap_s,
        initial_energy=branch.own_energy,
        initial_temperature=branch.battery_temperature,
        initial_battery_soh=branch.battery_soh,
        initial_lap=branch.lap,
    )
    run = simulator.run(steps) if action is None else simulator.run_forced(action, steps)

    # Only public state feeds the contact monitor; hidden rival mode never does.
    monitor = PassMonitor(TrackGeometry(length_m=PERIMETER_M, width_m=TRACK_WIDTH_M))
    trace: list[MotionStep] = []
    rival_pose = CarPose(branch.rival, simulator.rival_distance_m, 0.0)

    for index, step in enumerate(run):
        ego_distance = step.ego_distance_m
        rival_distance = step.rival_distance_m
        overtaking = abs(rival_distance - ego_distance) < OVERLAP_DISTANCE_M
        # The car behind takes the offset line while the two overlap, so the
        # viewer can see which side the pass is modelled on.
        ego_behind = ego_distance <= rival_distance
        ego_lateral = -LATERAL_OFFSET_M if (overtaking and ego_behind) else 0.0
        rival_lateral = -LATERAL_OFFSET_M if (overtaking and not ego_behind) else 0.0

        ego_pose = CarPose(branch.driver, ego_distance, ego_lateral)
        rival_pose = CarPose(branch.rival, rival_distance, rival_lateral)
        evaluation = monitor.evaluate(ego_pose, rival_pose)

        ego_x, ego_y = _offset_position(ego_distance, ego_lateral)
        rival_x, rival_y = _offset_position(rival_distance, rival_lateral)
        trace.append(MotionStep(
            # Evenly spaced model time, so the viewer's playback clock and the
            # plant steps cannot drift apart on accumulated float error.
            t_s=index * DT_S,
            ego_x=ego_x, ego_y=ego_y, rival_x=rival_x, rival_y=rival_y,
            ego_heading=loop_heading(ego_distance),
            rival_heading=loop_heading(rival_distance),
            ego_distance_m=ego_distance, rival_distance_m=rival_distance,
            ego_speed_kmh=step.ego_speed_kmh,
            rival_speed_kmh=simulator.rival.speed_kmh,
            ego_energy=step.ego_energy,
            gap_s=step.gap_s,
            contact=evaluation.contact,
        ))
    return trace


def _driver_state(step: MotionStep, side: str, lap: int) -> dict:
    x = step.ego_x if side == "ego" else step.rival_x
    y = step.ego_y if side == "ego" else step.rival_y
    distance = step.ego_distance_m if side == "ego" else step.rival_distance_m
    return {
        "x": x,
        "y": y,
        "speed": step.ego_speed_kmh if side == "ego" else step.rival_speed_kmh,
        "gear": 7,
        "drs": 0,
        "throttle": 100,
        "brake": 0,
        "tyre": 2,
        "lap": lap,
        "rel_dist": (distance % PERIMETER_M) / PERIMETER_M,
        "position": 2 if side == "ego" else 1,
        "fraction": distance / PERIMETER_M,
        "heading": step.ego_heading if side == "ego" else step.rival_heading,
        "in_pit": False,
        "motion_quality": "sampled",
    }


def _display_geometry() -> dict:
    """Edges derived from the same loop the cars are projected onto."""
    geometry = {"x": [], "y": [], "x_inner": [], "y_inner": [],
                "x_outer": [], "y_outer": [], "rotation_deg": 0.0, "drs_zones": []}
    half_width = TRACK_WIDTH_M / 2
    for i in range(GENERATED_POINTS):
        distance = i / GENERATED_POINTS * PERIMETER_M
        x, y = loop_point(distance)
        inner_x, inner_y = _offset_position(distance, -half_width)
        outer_x, outer_y = _offset_position(distance, half_width)
        geometry["x"].append(x)
        geometry["y"].append(y)
        geometry["x_inner"].append(inner_x)
        geometry["y_inner"].append(inner_y)
        geometry["x_outer"].append(outer_x)
        geometry["y_outer"].append(outer_y)
    return geometry


def motion_packet(
    branch: BranchStartLike,
    action: str | None = None,
    steps: int = 20,
    seed: int = 0,
    mode: HiddenRivalMode = HiddenRivalMode.MATCH,
    frame_index: int | None = None,
) -> dict:
    """One payload in the same schema as the replay broadcast.

    ``frame`` describes the newest sample for late joiners; ``trace`` carries
    the whole branch so a viewer can play it back at its own rate.
    """
    trace = build_motion_trace(branch, action, steps, seed, mode)
    if not trace:
        raise ValueError("simulation produced no steps")
    last = trace[-1]
    return {
        "source_id": f"replay-ai:{branch.driver}",
        "coordinate_units": "m",
        "run_mode": "simulated",
        "geometry_provenance": (
            "Synthetic display loop; car positions are a projection of plant "
            "longitudinal distance, not surveyed circuit geometry"
        ),
        "motion_provenance": (
            "replay_ai closed-loop plant; lateral overlap offset is a display "
            "projection, not simulated steering"
        ),
        "frame_index": int(round(last.t_s / DT_S)) if frame_index is None else frame_index,
        "frame": {
            "t": last.t_s,
            "lap": branch.lap,
            "drivers": {
                branch.driver: _driver_state(last, "ego", branch.lap),
                branch.rival: _driver_state(last, "rival", branch.lap),
            },
            "safety_car": None,
        },
        "track_status": "1",
        "playback_speed": 1,
        "is_paused": False,
        "total_frames": steps,
        "circuit_length_m": PERIMETER_M,
        "driver_colors": {branch.driver: "#3671C6", branch.rival: "#e8453c"},
        "has_rc_data": False,
        "race_control_events": [],
        "session_data": {
            "time": "", "time_s": last.t_s, "lap": branch.lap,
            "leader": branch.rival, "total_laps": 0,
        },
        "selected_drivers": [],
        "track_geometry": _display_geometry(),
        "simulation": {
            "command": action or "reference",
            "gap_s": last.gap_s,
            "ego_energy": last.ego_energy,
            "contact": last.contact,
            "model": "replay_ai.closed_loop",
        },
        "trace": [asdict(step) for step in trace],
    }
