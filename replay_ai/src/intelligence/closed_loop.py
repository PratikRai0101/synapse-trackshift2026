"""Action-responsive closed-loop reference simulator for intelligence tests."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
import random

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
                 lap_map_artifact: str | None = None,
                 seed: int = 0,
                 use_mpc: bool = True,
                 controller_variant: str = "full",
                 scenario: str = "nominal") -> None:
        self.config = config or SimulationConfig()
        self.rival_mode = rival_mode  # simulation truth; never passed to model
        rng = random.Random(seed)
        initial_speed = 275.0 + rng.random() * 10.0
        initial_gap = 0.8 + rng.random() * 0.4
        energy, soh, temperature = {
            "nominal": (70.0, 1.0, 70.0),
            "energy_stress": (35.0, 0.82, 85.0),
            "thermal_stress": (50.0, 0.88, 105.0),
        }.get(scenario, (70.0, 1.0, 70.0))
        self.initial_energy = energy
        self.ego = CarState(initial_speed, initial_gap, energy)
        self.rival = CarState(initial_speed, initial_gap, energy)
        self.plant = VehiclePlant(PlantState(
            speed_kmh=initial_speed,
            energy=energy,
            battery_temperature=temperature,
        ))
        self.time_s = 0.0
        self.step_index = 0
        self.current_lap = 1
        self.lap_deployed = 0.0
        self.cumulative_deployed = 0.0
        self.cumulative_recovered = 0.0
        self.battery_soh = soh
        self.battery_temperature = temperature
        self.scenario = scenario
        self.controller_variant = controller_variant
        self.model = MotorsportIntelligence(
            hmm_artifact=hmm_artifact,
            lap_map_artifact=lap_map_artifact,
            use_search=controller_variant != "no_search",
            use_spatial=controller_variant != "no_spatial",
            use_soh=controller_variant != "no_soh",
        )
        self.execution = FastExecutionController()
        self.use_mpc = use_mpc
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
        # Level 3 supplies a deployment budget, whereas the MPC accepts a
        # remaining-energy floor. Convert units/meaning at the layer boundary.
        reserve_target = (max(5.0, self.ego.energy - target_remaining)
                          if target is not None else None)
        execution, mpc = self.execution.track_zone(
            decision.lambda_kin, decision.lambda_b, 100.0,
            decision.target_speed_kmh, self.ego.speed_kmh, self.ego.energy,
            reserve_target,
        )
        self.last_mpc_result = mpc
        mpc_fraction = (execution.mpc_power_fraction or 0.0) if self.use_mpc else 1.0
        strategic_regen = 1.0 if decision.command == "HARVEST" else 0.0
        regen_fraction = (max(strategic_regen, mpc.regen_fraction)
                          if self.use_mpc else strategic_regen)
        brake_fraction = mpc.brake_fraction if self.use_mpc else 0.0
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
            brake_fraction=brake_fraction,
            regen_fraction=regen_fraction,
            slipstream_gap_s=self.ego.gap_s,
            dirty_air_gap_s=self.ego.gap_s,
            ahead_active_aero=1.0,
        )
        self.cumulative_deployed += self.plant.config.energy_rate * power_fraction * cfg.dt_s
        self.cumulative_recovered += self.plant.config.regen_rate * regen_fraction * cfg.dt_s
        self.ego.speed_kmh = plant_step.speed_kmh
        self.ego.energy = plant_step.energy
        self.battery_temperature = plant_step.battery_temperature
        throughput = abs(plant_step.energy - previous_energy)
        thermal_stress = max(0.0, self.battery_temperature - 70.0) / 30.0
        fade = throughput * (0.00005 + 0.00003 * thermal_stress)
        self.battery_soh = max(0.60, self.battery_soh - fade)

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
