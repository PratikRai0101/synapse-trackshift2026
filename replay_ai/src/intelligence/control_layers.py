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

    def point(self, distance_m: float, curvature: float,
              requested_speed_kmh: float) -> EnvelopePoint:
        cfg = self.config
        lateral_cap = math.sqrt(cfg.max_lateral_accel / max(abs(curvature), 1e-9))
        speed_cap = min(cfg.max_speed_kmh, max(cfg.min_speed_kmh, lateral_cap * 3.6))
        speed = min(max(cfg.min_speed_kmh, requested_speed_kmh), speed_cap)
        lateral_used = (speed / 3.6) ** 2 * abs(curvature)
        remaining = max(0.0, cfg.max_lateral_accel - lateral_used)
        longitudinal = math.sqrt(remaining * cfg.max_longitudinal_accel / cfg.max_lateral_accel)
        return EnvelopePoint(distance_m, speed_cap, longitudinal, speed <= speed_cap + 1e-9)


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


class BoundedScenarioPlanner:
    """Small bounded rollout over tactical commands.

    This deliberately does not call itself POMCP: it evaluates a finite action
    set against the current belief and continuation reserve value. A true
    generative tree search can replace this class behind the same result shape.
    """

    def __init__(self, envelope: PerformanceEnvelope | None = None) -> None:
        self.envelope = envelope or PerformanceEnvelope()

    def plan(self, hmm: HMMResult, own_speed_kmh: float, gap_s: float,
             energy: float, curvature: float = 0.0) -> Level2Plan:
        p = hmm.ers_probabilities
        reserve_value = max(0.0, energy - 5.0) * 0.02
        actions = (
            ("BURN", 12.0, 0.12, p[ERSMode.DERATE.value] * 2.0),
            ("HARVEST", -4.0, -0.03, p[ERSMode.HARVEST.value] * 2.0),
            ("PROACTIVE TRAP", 3.0, 0.02, (1.0 - p[ERSMode.DERATE.value]) * 0.5),
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
        envelope = self.envelope.point(0.0, curvature, own_speed_kmh)
        reference = tuple(min(envelope.speed_limit_kmh,
                              max(0.0, own_speed_kmh + selected.expected_gap_change_s * 20.0))
                          for _ in range(5))
        lambda_kin = tuple(1.0 if speed < envelope.speed_limit_kmh else 0.0
                            for speed in reference)
        lambda_b = max(0.01, (100.0 - energy) / 100.0)
        return Level2Plan(selected.command, reference, lambda_kin, lambda_b,
                          tuple(scored), envelope)


@dataclass(frozen=True)
class Level1Command:
    cue: str
    engine_power_fraction: float
    electric_power_fraction: float
    regen_fraction: float
    constrained: bool


class FastExecutionController:
    """Bounded Level 1 cue/power split reference."""

    def __init__(self, eta_deploy: float = 0.95, eta_regen: float = 0.65) -> None:
        self.eta_deploy = max(1e-6, eta_deploy)
        self.eta_regen = max(1e-6, eta_regen)

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
