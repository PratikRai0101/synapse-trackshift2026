"""Calibrate the rival model from paired plant rollouts.

Two distinct signals are needed, and conflating them was the original bug:

- **gap closure** per (action, policy) — prices a commitment in the tactical
  surrogate;
- **rival speed** per (action, policy) — the belief's evidence.

Gap closure alone is confounded: it accumulates the ego's own advantage, so once
the ego is ahead and faster every interval looks like a weak rival regardless of
policy. The rival's public speed does not have that defect.

The controller never observes the true policy. Calibration produces an off-line
model of what each *hypothesised* policy would do. Calibration and evaluation
share the same plant, so this is a calibration/selection step, not independent
validation.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Sequence

from ..contracts.state import ActionFamily, BatteryParams, Control, Track, VehicleParams
from ..decision.tactical import ACTION_POWER_W, ACTION_TARGET_SPEED_MPS, FAMILIES
from ..simulation.plant import Plant, initial_state
from ..simulation.rivals import REACTIVE_POLICIES, RivalPolicy, RivalPolicyConfig, rival_control
from ..simulation.tyres import TyreParams


@dataclass
class Calibration:
    closure_means_m: dict[tuple[ActionFamily, RivalPolicy], float] = field(default_factory=dict)
    response_means_mps: dict[tuple[ActionFamily, RivalPolicy], float] = field(default_factory=dict)
    closure_sigma_m: float = 1.0
    response_sigma_mps: float = 0.8
    samples: int = 0
    provenance: str = "simulation_fitted"

    def closure(self, action: ActionFamily, policy: RivalPolicy) -> float:
        return self.closure_means_m.get((action, policy), 0.0)

    def response(self, action: ActionFamily, policy: RivalPolicy) -> float:
        return self.response_means_mps.get((action, policy), 80.0)

    def closure_fn(self):
        return lambda action, policy: self.closure(action, policy)

    def response_fn(self):
        return lambda action, policy: self.response(action, policy)

    def table(self) -> list[dict[str, float | str]]:
        return [
            {
                "action": action.value,
                "policy": policy.value,
                "closure_m": self.closure(action, policy),
                "rival_speed_mps": self.response(action, policy),
            }
            for (action, policy) in sorted(
                self.closure_means_m, key=lambda item: (item[0].value, item[1].value)
            )
        ]


def _rollout(
    plant: Plant,
    action: ActionFamily,
    policy: RivalPolicy,
    progress_m: float,
    speed_mps: float,
    closure_horizon_s: float,
    response_horizon_s: float,
    dt_s: float,
    rival_config: RivalPolicyConfig,
) -> tuple[float, float]:
    """Return ``(gap_closed_m, rival_speed_change_mps)``.

    Closure is measured over the whole tactical horizon so a first-second
    acceleration transient cannot masquerade as a sustained gain. The response
    is the rival's speed change over one decision interval.
    """
    ego = initial_state(plant.battery, progress_m=progress_m, speed_mps=speed_mps)
    rival = initial_state(plant.battery, progress_m=progress_m, speed_mps=speed_mps)
    ego_control = Control(
        action,
        ACTION_POWER_W.get(action, 0.0),
        ACTION_TARGET_SPEED_MPS.get(action, speed_mps),
        closure_horizon_s,
    )
    elapsed = 0.0
    since_ego_attack = 0.0
    ego_start, rival_start = ego.progress_m, rival.progress_m
    response_change = 0.0
    captured_response = False
    steps = int(round(closure_horizon_s / dt_s))
    response_steps = max(1, int(round(response_horizon_s / dt_s)))
    for step in range(steps):
        rival_power, rival_target = rival_control(
            policy, action, 0.0, since_ego_attack, rival_config
        )
        rival_control_obj = Control(ActionFamily.REFERENCE, rival_power, rival_target, dt_s)
        ego = plant.step(ego, ego_control, dt_s).state
        rival = plant.step(rival, rival_control_obj, dt_s).state
        since_ego_attack += dt_s
        elapsed += dt_s
        if not captured_response and step + 1 >= response_steps:
            response_change = rival.speed_mps - speed_mps
            captured_response = True
    ego_advance = ego.progress_m - ego_start
    rival_advance = rival.progress_m - rival_start
    return ego_advance - rival_advance, response_change


def calibrate(
    track: Track,
    vehicle: VehicleParams,
    battery: BatteryParams,
    actions: Sequence[ActionFamily] = FAMILIES,
    policies: Sequence[RivalPolicy] = REACTIVE_POLICIES,
    horizon_s: float = 1.0,
    dt_s: float = 0.05,
    speed_mps: float = 80.0,
    start_progress_m: Sequence[float] = (200.0, 1000.0, 1700.0, 2400.0, 3100.0, 3900.0, 4500.0, 5200.0),
    closure_horizon_s: float = 3.0,
    response_horizon_s: float = 1.0,
    rival_config: RivalPolicyConfig | None = None,
    tyre_params: TyreParams | None = None,
    closure_sigma_floor_m: float = 0.75,
    response_sigma_floor_mps: float = 0.8,
) -> Calibration:
    """Measure response and closure only on sections where the circuit does not
    mask the policy. Start positions are placed on straights; a corner caps both
    a defending and a conserving rival at the same speed."""
    plant = Plant(vehicle, battery, track, tyre_params)
    rival_config = rival_config or RivalPolicyConfig()
    closure_means: dict[tuple[ActionFamily, RivalPolicy], float] = {}
    response_means: dict[tuple[ActionFamily, RivalPolicy], float] = {}
    closure_residuals: list[float] = []
    response_residuals: list[float] = []
    for action in actions:
        for policy in policies:
            samples = [
                _rollout(
                    plant, action, policy, progress, speed_mps,
                    closure_horizon_s, response_horizon_s, dt_s, rival_config,
                )
                for progress in start_progress_m
            ]
            closures = [c for c, _ in samples]
            responses = [r for _, r in samples]
            closure_mean = statistics.fmean(closures)
            response_mean = statistics.fmean(responses)
            closure_means[(action, policy)] = closure_mean
            response_means[(action, policy)] = response_mean
            closure_residuals.extend(c - closure_mean for c in closures)
            response_residuals.extend(r - response_mean for r in responses)

    closure_sigma = (
        statistics.pstdev(closure_residuals)
        if len(closure_residuals) > 1
        else closure_sigma_floor_m
    )
    response_sigma = (
        statistics.pstdev(response_residuals)
        if len(response_residuals) > 1
        else response_sigma_floor_mps
    )
    return Calibration(
        closure_means_m=closure_means,
        response_means_mps=response_means,
        closure_sigma_m=max(closure_sigma_floor_m, closure_sigma),
        response_sigma_mps=max(response_sigma_floor_mps, response_sigma),
        samples=len(closure_residuals),
    )
