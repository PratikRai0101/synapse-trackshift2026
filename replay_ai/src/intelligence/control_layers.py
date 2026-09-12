"""Reference Level 2 and Level 1 control layers.

These are transparent baselines for the proposed SOCP/POMCP and 100 Hz MPC
layers. They enforce bounded physical requests and expose the same outputs that
a later cvxpy/POMCP implementation can replace.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence

from .hierarchical import ERSMode, HMMResult
from .socp_envelope import SOCPConfig, SOCPPerformanceEnvelope
from .scenario_search import BoundedPOMCP, SearchConfig
from .zone_mpc import ZoneMPC, ZoneMPCConfig, ZoneMPCResult
from .spatial_planner import TrackSample, SpatialReference, SpatialTrajectoryPlanner


@dataclass(frozen=True)
class EnvelopeConfig:
    max_speed_kmh: float = 360.0
    max_longitudinal_accel: float = 8.0
    max_brake_accel: float = 15.0
    max_lateral_accel: float = 12.0
    min_speed_kmh: float = 20.0


@dataclass(frozen=True)
class EnvelopePoint:
    distance_m: float
    speed_limit_kmh: float
    longitudinal_accel_limit: float
    feasible: bool


class PerformanceEnvelope:
    """Combined longitudinal/lateral grip envelope reference."""

    def __init__(self, config: EnvelopeConfig | None = None) -> None:
        self.config = config or EnvelopeConfig()
        self.socp = SOCPPerformanceEnvelope(SOCPConfig(
            friction_mu=self.config.max_lateral_accel / 9.81,
            gravity=9.81,
            max_speed_kmh=self.config.max_speed_kmh,
            min_speed_kmh=self.config.min_speed_kmh,
        ))

    def point(self, distance_m: float, curvature: float,
              requested_speed_kmh: float) -> EnvelopePoint:
        result = self.socp.solve(
            [distance_m], [requested_speed_kmh], [curvature],
            [self.config.max_longitudinal_accel],
        )
        point = result.points[0]
        return EnvelopePoint(distance_m, point.speed_kmh,
                             point.longitudinal_accel, result.feasible)


@dataclass(frozen=True)
class ScenarioAction:
    command: str
    energy_cost: float
    expected_gap_change_s: float
    continuation_value: float
    score: float


@dataclass(frozen=True)
class Level2Plan:
    command: str
    reference_speed_kmh: tuple[float, ...]
    lambda_kin: tuple[float, ...]
    lambda_b: float
    action_scores: tuple[ScenarioAction, ...]
    envelope: EnvelopePoint
    search_values: Mapping[str, float] | None = None
    spatial_reference: SpatialReference | None = None
    spatial_feasible: bool = True
    spatial_residual: float = 0.0


class BoundedScenarioPlanner:
    """Small bounded rollout over tactical commands.

    This deliberately does not call itself POMCP: it evaluates a finite action
    set against the current belief and continuation reserve value. A true
    generative tree search can replace this class behind the same result shape.
    """

    def __init__(self, envelope: PerformanceEnvelope | None = None,
                 search_config: SearchConfig | None = None,
                 use_search: bool = True, use_spatial: bool = True) -> None:
        self.envelope = envelope or PerformanceEnvelope()
        self.searcher = BoundedPOMCP(search_config)
        self.spatial = SpatialTrajectoryPlanner()
        self.use_search = use_search
        self.use_spatial = use_spatial

    def plan(self, hmm: HMMResult, own_speed_kmh: float, gap_s: float,
             energy: float, curvature: float = 0.0,
             wear_cost: float = 0.0) -> Level2Plan:
        p = hmm.ers_probabilities
        reserve_value = max(0.0, energy - 5.0) * 0.02
        actions = (
            # Evidence gates are intentional: a continuation value alone must
            # not turn every weak posterior into HARVEST or BURN.
            ("BURN", 12.0, 0.12,
             p[ERSMode.DERATE.value] * 2.0 if gap_s < 1.0 and energy > 20.0 else -1.0),
            ("HARVEST", -4.0, -0.03,
             p[ERSMode.HARVEST.value] * 2.0 if p[ERSMode.HARVEST.value] >= 0.40 or energy < 30.0 else -1.0),
            ("PROACTIVE TRAP", 3.0, 0.02,
             (1.0 - p[ERSMode.DERATE.value]) * 0.5),
        )
        scored = []
        for command, cost, gap_gain, belief_value in actions:
            attack_value = max(0.0, 1.0 - gap_s) * gap_gain * 10.0
            score = attack_value + belief_value + reserve_value - abs(cost) * 0.01
            if energy <= 5.0 and command == "BURN":
                score -= 10.0
            scored.append(ScenarioAction(command, cost, gap_gain, belief_value,
                                         score))
        selected = max(scored, key=lambda action: action.score)
        search = self.searcher.search(hmm, gap_s, energy)
        search_allowed = self.use_search and (
            (search.action != "BURN" or p[ERSMode.DERATE.value] >= 0.40) and
            (search.action != "HARVEST" or p[ERSMode.HARVEST.value] >= 0.40 or energy < 30.0)
        )
        if search_allowed:
            selected = next(action for action in scored if action.command == search.action)
        envelope = self.envelope.point(0.0, curvature, own_speed_kmh)
        track = tuple(TrackSample(index * 25.0,
                                   max(0.0, curvature + 0.0002 * index))
                      for index in range(5))
        tactical_speed = max(0.0, own_speed_kmh + selected.expected_gap_change_s * 20.0)
        spatial = (self.spatial.plan(
            track, tactical_speed, speed_gain_kmh=0.0,
            initial_energy=energy, reserve_energy=5.0,
        ) if self.use_spatial else None)
        if spatial is None:
            reference = tuple(envelope.speed_limit_kmh for _ in range(5))
            lambda_kin = tuple(0.0 for _ in range(5))
        else:
            reference = spatial.speeds_kmh
            lambda_kin = spatial.kinetic_costates
        lambda_b = max(0.01, (100.0 - energy) / 100.0 + max(0.0, wear_cost))
        return Level2Plan(
            selected.command, reference, lambda_kin, lambda_b,
            tuple(scored), envelope, search.values, spatial,
            spatial.envelope.feasible if spatial else True,
            spatial.envelope.max_residual if spatial else 0.0,
        )


@dataclass(frozen=True)
class Level1Command:
    cue: str
    engine_power_fraction: float
    electric_power_fraction: float
    regen_fraction: float
    constrained: bool
    mpc_power_fraction: float | None = None


class FastExecutionController:
    """Bounded Level 1 cue/power split reference."""

    def __init__(self, eta_deploy: float = 0.95, eta_regen: float = 0.65,
                 mpc_config: ZoneMPCConfig | None = None) -> None:
        self.eta_deploy = max(1e-6, eta_deploy)
        self.eta_regen = max(1e-6, eta_regen)
        self.mpc = ZoneMPC(mpc_config)

    def command(self, lambda_kin: float, lambda_b: float,
                pedal_pct: float, target_speed_kmh: float,
                current_speed_kmh: float) -> Level1Command:
        ratio = lambda_kin / max(abs(lambda_b), 1e-6)
        if lambda_kin > 0.0 and current_speed_kmh > target_speed_kmh:
            cue = "FRICTION BRAKE"
        elif ratio < -1.0 / self.eta_deploy:
            cue = "MAX ACCEL"
        elif ratio < -self.eta_regen:
            cue = "COAST"
        elif ratio < 0.0:
            cue = "REGEN BRAKE"
        else:
            cue = "HOLD"
        constrained = pedal_pct < 100.0
        if constrained:
            # Corners: preserve driver-requested total thrust.
            engine = max(0.0, min(1.0, pedal_pct / 100.0))
            electric = 0.0
        elif cue == "MAX ACCEL":
            engine, electric = 1.0, 1.0
        else:
            engine, electric = 1.0, 0.0
        regen = 1.0 if cue == "REGEN BRAKE" else 0.0
        return Level1Command(cue, engine, electric, regen, constrained)

    def track_zone(self, lambda_kin: float, lambda_b: float,
                   pedal_pct: float, target_speed_kmh: float,
                   current_speed_kmh: float, energy: float,
                   target_energy: float | None = None) -> tuple[Level1Command, ZoneMPCResult]:
        """Run the LP zone MPC and attach its first action to the cue."""
        cue = self.command(lambda_kin, lambda_b, pedal_pct,
                           target_speed_kmh, current_speed_kmh)
        zone = self.mpc.solve(current_speed_kmh, energy, target_speed_kmh,
                              target_energy)
        return Level1Command(cue.cue, cue.engine_power_fraction,
                             cue.electric_power_fraction, cue.regen_fraction,
                             cue.constrained, zone.power_fraction), zone
