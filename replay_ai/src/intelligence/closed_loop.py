"""Action-responsive closed-loop reference simulator for intelligence tests."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math

from .hierarchical import MotorsportIntelligence, RivalTelemetry, TacticalDecision
from .control_layers import FastExecutionController
from .vehicle_plant import PlantState, VehiclePlant


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
    steps_per_lap: int = 20


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
                 config: SimulationConfig | None = None,
                 hmm_artifact: str | None = None,
                 lap_map_artifact: str | None = None) -> None:
        self.config = config or SimulationConfig()
        self.rival_mode = rival_mode  # simulation truth; never passed to model
        self.ego = CarState(280.0, 1.0, 70.0)
        self.rival = CarState(280.0, 1.0, 70.0)
        self.plant = VehiclePlant(PlantState(speed_kmh=280.0, energy=70.0))
        self.time_s = 0.0
        self.step_index = 0
        self.current_lap = 1
        self.lap_deployed = 0.0
        self.battery_soh = 1.0
        self.battery_temperature = 70.0
        self.model = MotorsportIntelligence(hmm_artifact=hmm_artifact,
                                             lap_map_artifact=lap_map_artifact)
        self.execution = FastExecutionController()
        self.last_mpc_result = None
        self.rival_defending = False

    def _observation(self) -> RivalTelemetry:
        # Only the rival's public channels enter the model. Rival SOC/mode is
        # deliberately absent; it exists only inside this simulator.
        if self.rival_mode is HiddenRivalMode.CONSERVE:
            # Managed pedal: deliberately hoard energy while appearing merely
            # a little slower on a timing screen.
            throttle = 92.0
        elif self.rival_mode is HiddenRivalMode.DEPLETE:
            # Foot pinned but car is physically unable to sustain pace: the
            # public signature of L_derate.
            throttle = 100.0
        else:
            throttle = 100.0 if self.rival.speed_kmh < 300.0 else 92.0
        return RivalTelemetry(
            speed_kmh=self.rival.speed_kmh,
            throttle_pct=throttle,
            brake=0.0,
            gap_s=max(0.0, self.ego.gap_s),
            active_aero=1.0 if self.ego.gap_s < 1.0 else 0.0,
            lap=self.current_lap,
        )

    def step(self) -> SimulationStep:
        cfg = self.config
        public = self._observation()
        decision = self.model.observe(
            public, own_speed_kmh=self.ego.speed_kmh,
            own_soc=self.ego.energy, gap_s=self.ego.gap_s,
            battery_soh=self.battery_soh,
            battery_temperature=self.battery_temperature,
        )
        target = decision.lap_energy_target
        target_remaining = max(0.0, (target or 0.0) - self.lap_deployed)
        can_deploy = target is None or target_remaining > 0.0
        execution, mpc = self.execution.track_zone(
            decision.lambda_kin, decision.lambda_b, 100.0,
            decision.target_speed_kmh, self.ego.speed_kmh, self.ego.energy,
            target,
        )
        self.last_mpc_result = mpc
        mpc_fraction = execution.mpc_power_fraction or 0.0
        regen_fraction = 1.0 if decision.command == "HARVEST" else 0.0
        if decision.command == "BURN" and self.ego.energy > 5.0 and can_deploy:
            power_fraction = mpc_fraction
            deployment = (min(cfg.battery_burn_per_s * power_fraction, target_remaining)
                          if target is not None else cfg.battery_burn_per_s * power_fraction)
            self.lap_deployed += deployment * cfg.dt_s
        else:
            power_fraction = 0.0
        curvature = 0.0012 + 0.0008 * math.sin(self.plant.state.distance_m / 180.0)
        previous_energy = self.plant.state.energy
        plant_step = self.plant.step(
            power_fraction, cfg.dt_s, curvature,
            regen_fraction=regen_fraction,
            slipstream_gap_s=self.ego.gap_s,
        )
        self.ego.speed_kmh = plant_step.speed_kmh
        self.ego.energy = plant_step.energy
        self.battery_temperature = plant_step.battery_temperature
        throughput = abs(plant_step.energy - previous_energy)
        self.battery_soh = max(0.60, self.battery_soh - throughput * 0.00005)

        self.rival_defending = self.ego.gap_s < 1.0
        defense_bonus = 4.0 if self.rival_defending else 0.0
        if self.rival_mode is HiddenRivalMode.CONSERVE:
            rival_accel = cfg.rival_accel_kmh_s + 8.0 + defense_bonus
        elif self.rival_mode is HiddenRivalMode.DEPLETE:
            # The rival loses pace despite 100% throttle, creating a genuine
            # attack opportunity visible through public speed/gap response.
            rival_accel = cfg.rival_accel_kmh_s - 30.0 + defense_bonus
        else:
            rival_accel = cfg.rival_accel_kmh_s + defense_bonus
        self.rival.speed_kmh = max(0.0, self.rival.speed_kmh +
                                   (rival_accel - cfg.drag_kmh_s) * cfg.dt_s)
        # Positive gap means the rival remains ahead. Approximate time-gap
        # dynamics from relative speed; clamp rather than silently wrap.
        self.ego.gap_s = max(0.0, self.ego.gap_s +
                             (self.rival.speed_kmh - self.ego.speed_kmh) /
                             3.6 * cfg.dt_s / max(self.ego.speed_kmh / 3.6, 1.0))
        self.rival.gap_s = self.ego.gap_s
        self.time_s += cfg.dt_s
        self.step_index += 1
        if self.step_index % max(1, cfg.steps_per_lap) == 0:
            self.current_lap += 1
            self.lap_deployed = 0.0
        return SimulationStep(
            PublicSimulationObservation(self.time_s, public.speed_kmh,
                                        public.throttle_pct, public.brake,
                                        self.ego.gap_s, public.active_aero),
            decision, self.ego.speed_kmh, self.ego.gap_s, self.ego.energy,
        )

    def pit_stop(self) -> None:
        """Apply a pit event to the ego plant; future frames reflect new tyres/fuel."""
        self.plant.pit_stop()

    def run(self, steps: int) -> tuple[SimulationStep, ...]:
        return tuple(self.step() for _ in range(max(0, int(steps))))
