"""Action-responsive closed-loop reference simulator for intelligence tests."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .hierarchical import MotorsportIntelligence, RivalTelemetry, TacticalDecision


class HiddenRivalMode(str, Enum):
    CONSERVE = "conserve"
    DEPLETE = "deplete"
    MATCH = "match"


@dataclass(frozen=True)
class SimulationConfig:
    dt_s: float = 0.1
    ego_accel_kmh_s: float = 15.0
    burn_bonus_kmh_s: float = 8.0
    harvest_penalty_kmh_s: float = 3.0
    rival_accel_kmh_s: float = 10.0
    drag_kmh_s: float = 2.0
    battery_burn_per_s: float = 1.2
    battery_harvest_per_s: float = 0.7


@dataclass
class CarState:
    speed_kmh: float
    gap_s: float
    energy: float


@dataclass(frozen=True)
class PublicSimulationObservation:
    timestamp_s: float
    speed_kmh: float
    throttle_pct: float
    brake: float
    gap_s: float
    active_aero: float


@dataclass(frozen=True)
class SimulationStep:
    observation: PublicSimulationObservation
    decision: TacticalDecision
    ego_speed_kmh: float
    gap_s: float
    ego_energy: float


class ClosedLoopSimulator:
    """Minimal action-responsive plant with inaccessible rival truth."""

    def __init__(self, rival_mode: HiddenRivalMode = HiddenRivalMode.MATCH,
                 config: SimulationConfig | None = None) -> None:
        self.config = config or SimulationConfig()
        self.rival_mode = rival_mode  # simulation truth; never passed to model
        self.ego = CarState(280.0, 1.0, 70.0)
        self.rival = CarState(280.0, 1.0, 70.0)
        self.time_s = 0.0
        self.model = MotorsportIntelligence()

    def _observation(self) -> RivalTelemetry:
        # Only the rival's public channels enter the model. Rival SOC/mode is
        # deliberately absent; it exists only inside this simulator.
        return RivalTelemetry(
            speed_kmh=self.rival.speed_kmh,
            throttle_pct=100.0 if self.rival.speed_kmh < 300.0 else 92.0,
            brake=0.0,
            gap_s=max(0.0, self.ego.gap_s),
            active_aero=1.0 if self.ego.gap_s < 1.0 else 0.0,
        )

    def step(self) -> SimulationStep:
        cfg = self.config
        public = self._observation()
        decision = self.model.observe(public, own_speed_kmh=self.ego.speed_kmh,
                                       own_soc=self.ego.energy, gap_s=self.ego.gap_s)
        if decision.command == "BURN" and self.ego.energy > 5.0:
            ego_accel = cfg.ego_accel_kmh_s + cfg.burn_bonus_kmh_s
            energy_delta = -cfg.battery_burn_per_s
        elif decision.command == "HARVEST":
            ego_accel = cfg.ego_accel_kmh_s - cfg.harvest_penalty_kmh_s
            energy_delta = cfg.battery_harvest_per_s
        else:
            ego_accel = cfg.ego_accel_kmh_s
            energy_delta = -cfg.battery_burn_per_s * 0.25
        self.ego.speed_kmh = max(0.0, self.ego.speed_kmh +
                                 (ego_accel - cfg.drag_kmh_s) * cfg.dt_s)
        self.ego.energy = max(0.0, min(100.0, self.ego.energy +
                                       energy_delta * cfg.dt_s))

        if self.rival_mode is HiddenRivalMode.CONSERVE:
            rival_accel = cfg.rival_accel_kmh_s - 4.0
        elif self.rival_mode is HiddenRivalMode.DEPLETE:
            rival_accel = cfg.rival_accel_kmh_s + 5.0
        else:
            rival_accel = cfg.rival_accel_kmh_s
        self.rival.speed_kmh = max(0.0, self.rival.speed_kmh +
                                   (rival_accel - cfg.drag_kmh_s) * cfg.dt_s)
        # Positive gap means the rival remains ahead. Approximate time-gap
        # dynamics from relative speed; clamp rather than silently wrap.
        self.ego.gap_s = max(0.0, self.ego.gap_s +
                             (self.rival.speed_kmh - self.ego.speed_kmh) /
                             3.6 * cfg.dt_s / max(self.ego.speed_kmh / 3.6, 1.0))
        self.rival.gap_s = self.ego.gap_s
        self.time_s += cfg.dt_s
        return SimulationStep(
            PublicSimulationObservation(self.time_s, public.speed_kmh,
                                        public.throttle_pct, public.brake,
                                        self.ego.gap_s, public.active_aero),
            decision, self.ego.speed_kmh, self.ego.gap_s, self.ego.energy,
        )

    def run(self, steps: int) -> tuple[SimulationStep, ...]:
        return tuple(self.step() for _ in range(max(0, int(steps))))
