"""Passing geometry: world path, oriented footprints and pass classification.

A completed pass is never inferred from longitudinal order alone. It requires:

1. the ego rear to clear the rival front by a configured margin,
2. the clearance to persist for a configured interval,
3. no modelled contact and no track exit during that interval.

Catch-up (progress order changing) without these is reported as ``CATCH_UP``.
The path is generated from the track curvature by integrating heading, so world
coordinates and track coordinates stay consistent.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum

import numpy as np

from ..contracts.state import Track


class PassOutcome(str, Enum):
    NONE = "none"
    CATCH_UP = "catch_up"
    CONTACT = "contact"
    TRACK_EXIT = "track_exit"
    PASS = "pass"
    RE_PASS = "re_pass"


@dataclass(frozen=True)
class Footprint:
    length_m: float = 5.6
    width_m: float = 2.0


@dataclass(frozen=True)
class Pose:
    s_m: float
    lateral_m: float
    x_m: float
    y_m: float
    heading_rad: float


class TrackPath:
    """World-coordinate path generated from ``track.curvature_at``."""

    def __init__(self, track: Track, n: int = 2000) -> None:
        self.track = track
        self.length_m = track.length_m
        s = np.linspace(0.0, track.length_m, n + 1)
        kappa = np.array([track.curvature_at(float(x)) for x in s])
        x_arr = np.zeros(n + 1)
        y_arr = np.zeros(n + 1)
        h_arr = np.zeros(n + 1)
        ds = track.length_m / n
        for i in range(1, n + 1):
            h_arr[i] = h_arr[i - 1] + 0.5 * (kappa[i - 1] + kappa[i]) * ds
            x_arr[i] = x_arr[i - 1] + math.cos(h_arr[i - 1]) * ds
            y_arr[i] = y_arr[i - 1] + math.sin(h_arr[i - 1]) * ds
        self._s = s
        self._x = x_arr
        self._y = y_arr
        self._h = h_arr

    def pose_at(self, s_m: float, lateral_m: float = 0.0) -> Pose:
        s_wrapped = s_m % self.length_m if self.length_m > 0 else 0.0
        x = float(np.interp(s_wrapped, self._s, self._x))
        y = float(np.interp(s_wrapped, self._s, self._y))
        h = float(np.interp(s_wrapped, self._s, self._h))
        # offset along the left normal
        nx, ny = -math.sin(h), math.cos(h)
        return Pose(
            s_m=s_m,
            lateral_m=lateral_m,
            x_m=x + nx * lateral_m,
            y_m=y + ny * lateral_m,
            heading_rad=h,
        )


def footprint_corners(pose: Pose, footprint: Footprint) -> np.ndarray:
    half_l, half_w = footprint.length_m / 2.0, footprint.width_m / 2.0
    c, s = math.cos(pose.heading_rad), math.sin(pose.heading_rad)
    local = [
        (-half_l, -half_w),
        (half_l, -half_w),
        (half_l, half_w),
        (-half_l, half_w),
    ]
    return np.array(
        [
            (pose.x_m + dx * c - dy * s, pose.y_m + dx * s + dy * c)
            for dx, dy in local
        ]
    )


def rectangles_overlap(a: np.ndarray, b: np.ndarray) -> bool:
    """Separating-axis test for two convex quadrilaterals."""
    for rect in (a, b):
        for i in range(4):
            edge = rect[(i + 1) % 4] - rect[i]
            axis = np.array([-edge[1], edge[0]])
            norm = np.linalg.norm(axis)
            if norm < 1e-12:
                continue
            axis = axis / norm
            pa, pb = a @ axis, b @ axis
            if pa.max() < pb.min() or pb.max() < pa.min():
                return False
    return True


def footprint_within_track(
    pose: Pose, footprint: Footprint, track: Track, tolerance_m: float = 0.0
) -> bool:
    """Track containment using the track-coordinate half-width."""
    half_track = track.width_at(pose.s_m % track.length_m) / 2.0
    return abs(pose.lateral_m) + footprint.width_m / 2.0 <= half_track + tolerance_m


@dataclass
class PassMonitor:
    """Classifies passes over an interaction, not from a single frame."""

    track: Track
    footprint: Footprint = Footprint()
    margin_m: float = 1.0
    persistence_s: float = 2.0
    contact: bool = False
    track_exit: bool = False
    passes: int = 0
    re_passes: int = 0
    contacts: int = 0
    exits: int = 0
    _ahead_since: float | None = field(default=None, init=False)
    _ahead_state: bool = field(default=False, init=False)
    _last_outcome: PassOutcome = field(default=PassOutcome.NONE, init=False)

    def _clears(self, ego: Pose, rival: Pose) -> bool:
        return (
            ego.s_m - self.footprint.length_m / 2.0
            > rival.s_m + self.footprint.length_m / 2.0 + self.margin_m
        )

    def update(self, t_s: float, ego: Pose, rival: Pose) -> PassOutcome:
        ego_rect = footprint_corners(ego, self.footprint)
        rival_rect = footprint_corners(rival, self.footprint)
        contact_now = rectangles_overlap(ego_rect, rival_rect)
        exit_now = not footprint_within_track(ego, self.footprint, self.track)

        if contact_now:
            self.contact = True
            self.contacts += 1
        if exit_now:
            self.track_exit = True
            self.exits += 1

        ahead = self._clears(ego, rival)
        outcome = PassOutcome.NONE

        if ahead:
            if not self._ahead_state:
                if self._ahead_since is None:
                    self._ahead_since = t_s
                clean = not contact_now and not exit_now
                sustained = (t_s - self._ahead_since) >= self.persistence_s
                if clean and sustained:
                    if self.passes + self.re_passes > 0:
                        self.re_passes += 1
                        outcome = PassOutcome.RE_PASS
                    else:
                        self.passes += 1
                        outcome = PassOutcome.PASS
                    self._ahead_state = True
                    self._ahead_since = None
        else:
            self._ahead_since = None
            self._ahead_state = False
            if ego.s_m > rival.s_m and not contact_now and not exit_now:
                outcome = PassOutcome.CATCH_UP

        if contact_now:
            outcome = PassOutcome.CONTACT
        elif exit_now:
            outcome = PassOutcome.TRACK_EXIT

        self._last_outcome = outcome
        return outcome

    @property
    def last_outcome(self) -> PassOutcome:
        return self._last_outcome
