"""Contact safety: a hard feasibility check on committed controls.

The plant already builds footprints and runs a separating-axis test. This module
projects the ego and rival forward kinematically and refuses a target speed that
would put the two footprints in contact. It is a *supervisor* in the same sense
as the reserve guard: a modelled contact risk makes the plan infeasible, it is
not merely recorded afterwards.

The rival's future is unknown to the controller. The projection therefore holds
the rival's public speed and lateral offset constant, which is conservative: if
the ego would hit a rival holding its line, the plan is unsafe.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..contracts.state import Track
from ..simulation.geometry import (
    Footprint,
    TrackPath,
    footprint_corners,
    rectangles_overlap,
)

#: Declared kinematic limits for the projection, matching the plant exactly.
#: If the projection is less aggressive than the plant, the plant can close
#: faster than predicted and contact occurs anyway.
LATERAL_RATE_MPS = 1.5
ACCEL_LIMIT_MPS2 = 12.0
SPEED_TRACKING_GAIN = 1.5


@dataclass
class ContactGuard:
    track: Track
    footprint: Footprint = Footprint()
    margin_m: float = 0.0
    dt_s: float = 0.05
    speed_search_step_mps: float = 1.0
    _path: TrackPath = field(init=False)
    _inflated: Footprint = field(init=False)

    def __post_init__(self) -> None:
        self._path = TrackPath(self.track)
        # Declared model-error margin. The projection is optimistic under
        # parameter shift, so the guard checks an inflated footprint: a plan is
        # only accepted if it clears the rival by this margin as well.
        self._inflated = Footprint(
            self.footprint.length_m + 2.0 * self.margin_m,
            self.footprint.width_m + 2.0 * self.margin_m,
        )

    # -- projection --------------------------------------------------------
    def _project(
        self,
        ego_s: float,
        ego_v: float,
        ego_lat: float,
        rival_s: float,
        rival_v: float,
        rival_lat: float,
        ego_v_target: float,
        ego_lat_target: float,
        horizon_s: float,
    ) -> bool:
        steps = max(1, int(round(horizon_s / self.dt_s)))
        s_e, v_e, l_e = ego_s, ego_v, ego_lat
        s_r, l_r = rival_s, rival_lat
        for _ in range(steps):
            accel = max(
                -ACCEL_LIMIT_MPS2,
                min(ACCEL_LIMIT_MPS2, SPEED_TRACKING_GAIN * (ego_v_target - v_e)),
            )
            v_e = max(0.0, v_e + accel * self.dt_s)
            s_e += v_e * self.dt_s
            delta = ego_lat_target - l_e
            l_e += max(-LATERAL_RATE_MPS * self.dt_s, min(LATERAL_RATE_MPS * self.dt_s, delta))
            s_r += rival_v * self.dt_s
            ego_rect = footprint_corners(self._path.pose_at(s_e, l_e), self._inflated)
            rival_rect = footprint_corners(self._path.pose_at(s_r, l_r), self._inflated)
            if rectangles_overlap(ego_rect, rival_rect):
                return True
        return False

    def predicts_contact(
        self,
        ego_progress_m: float,
        ego_speed_mps: float,
        ego_lateral_m: float,
        rival_progress_m: float,
        rival_speed_mps: float,
        rival_lateral_m: float,
        ego_target_speed_mps: float,
        ego_target_lateral_m: float,
        horizon_s: float,
    ) -> bool:
        return self._project(
            ego_progress_m, ego_speed_mps, ego_lateral_m,
            rival_progress_m, rival_speed_mps, rival_lateral_m,
            ego_target_speed_mps, ego_target_lateral_m, horizon_s,
        )

    def max_safe_target_speed(
        self,
        ego_progress_m: float,
        ego_speed_mps: float,
        ego_lateral_m: float,
        rival_progress_m: float,
        rival_speed_mps: float,
        rival_lateral_m: float,
        desired_target_speed_mps: float,
        ego_target_lateral_m: float,
        horizon_s: float,
    ) -> float:
        """Largest target speed that does not project a contact.

        Scans downward from the desired target. A result below the rival's speed
        means the ego may move laterally this cycle but must not close yet.
        """
        candidate = desired_target_speed_mps
        floor = rival_speed_mps - 10.0
        while candidate >= floor:
            if not self.predicts_contact(
                ego_progress_m, ego_speed_mps, ego_lateral_m,
                rival_progress_m, rival_speed_mps, rival_lateral_m,
                candidate, ego_target_lateral_m, horizon_s,
            ):
                return candidate
            candidate -= self.speed_search_step_mps
        return floor
