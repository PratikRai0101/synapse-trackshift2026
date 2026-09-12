"""Geometry and pass-classification tests.

A pass is never inferred from longitudinal order alone: contact, track exit and
persistence must all be checked.
"""

from __future__ import annotations

import numpy as np
import pytest

from gridops.simulation.geometry import (
    Footprint,
    PassMonitor,
    PassOutcome,
    TrackPath,
    footprint_corners,
    footprint_within_track,
    rectangles_overlap,
)
from gridops.simulation.track import synthetic_circuit


@pytest.fixture()
def path() -> TrackPath:
    return TrackPath(synthetic_circuit(), n=600)


def test_track_path_is_finite_and_curves(path: TrackPath) -> None:
    for s in np.linspace(0.0, path.length_m, 20):
        pose = path.pose_at(float(s), 0.0)
        assert np.isfinite(pose.x_m) and np.isfinite(pose.y_m)
        assert np.isfinite(pose.heading_rad)


def test_lateral_offset_moves_perpendicular(path: TrackPath) -> None:
    centre = path.pose_at(1000.0, 0.0)
    offset = path.pose_at(1000.0, 2.0)
    distance = np.hypot(offset.x_m - centre.x_m, offset.y_m - centre.y_m)
    assert distance == pytest.approx(2.0, abs=1e-6)


def test_footprint_corners_form_a_rectangle(path: TrackPath) -> None:
    pose = path.pose_at(500.0, 0.0)
    corners = footprint_corners(pose, Footprint())
    assert corners.shape == (4, 2)
    # opposite corners share the same centre
    centre = corners.mean(axis=0)
    assert np.allclose(corners[0] + corners[2], 2 * centre, atol=1e-9)


def test_overlap_and_separation(path: TrackPath) -> None:
    same = footprint_corners(path.pose_at(500.0, 0.0), Footprint())
    overlapping = footprint_corners(path.pose_at(503.0, 0.5), Footprint())
    separated = footprint_corners(path.pose_at(520.0, 0.0), Footprint())
    beside = footprint_corners(path.pose_at(500.0, 3.0), Footprint())
    assert rectangles_overlap(same, overlapping)
    assert not rectangles_overlap(same, separated)
    assert not rectangles_overlap(same, beside)


def test_track_containment(path: TrackPath) -> None:
    on_line = path.pose_at(500.0, 0.0)
    near_edge = path.pose_at(500.0, 6.8)
    assert footprint_within_track(on_line, Footprint(), path.track)
    assert not footprint_within_track(near_edge, Footprint(), path.track)


def test_contact_is_not_a_pass(path: TrackPath) -> None:
    monitor = PassMonitor(path.track, persistence_s=0.0)
    ego = path.pose_at(500.0, 0.0)
    rival = path.pose_at(500.0, 0.0)
    outcome = monitor.update(0.0, ego, rival)
    assert outcome is PassOutcome.CONTACT
    assert monitor.passes == 0


def test_track_exit_is_not_a_pass(path: TrackPath) -> None:
    monitor = PassMonitor(path.track, persistence_s=0.0)
    ego = path.pose_at(520.0, 6.8)
    rival = path.pose_at(500.0, 0.0)
    outcome = monitor.update(0.0, ego, rival)
    assert outcome is PassOutcome.TRACK_EXIT
    assert monitor.passes == 0


def test_clearance_must_persist(path: TrackPath) -> None:
    monitor = PassMonitor(path.track, margin_m=1.0, persistence_s=2.0)
    ego = path.pose_at(520.0, 3.0)
    rival = path.pose_at(500.0, 0.0)
    assert monitor.update(0.0, ego, rival) is not PassOutcome.PASS
    assert monitor.update(1.0, ego, rival) is not PassOutcome.PASS
    outcome = monitor.update(2.5, ego, rival)
    assert outcome is PassOutcome.PASS
    assert monitor.passes == 1


def test_order_change_without_clearance_is_catch_up(path: TrackPath) -> None:
    monitor = PassMonitor(path.track, persistence_s=0.0)
    ego = path.pose_at(502.0, 0.0)  # marginally ahead, overlapping
    rival = path.pose_at(500.0, 0.0)
    outcome = monitor.update(0.0, ego, rival)
    assert outcome in {PassOutcome.CATCH_UP, PassOutcome.CONTACT}
    assert monitor.passes == 0


def test_re_pass_is_counted_separately(path: TrackPath) -> None:
    monitor = PassMonitor(path.track, margin_m=1.0, persistence_s=0.0)
    ahead_far = path.pose_at(600.0, 3.0)
    behind = path.pose_at(500.0, 0.0)
    monitor.update(0.0, ahead_far, behind)
    assert monitor.passes == 1
    monitor.update(1.0, behind, ahead_far)  # re-passed
    outcome = monitor.update(2.0, ahead_far, behind)
    assert outcome is PassOutcome.RE_PASS
    assert monitor.re_passes == 1
