"""Deterministic closed-loop episode runner.

Owns the plant and the hidden rival truth. The controller receives only a
:class:`DecisionInput` built from public and own-car fields. This is the primary
acceptance seam.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from ..contracts.records import DecisionInput, ObservationFrame
from ..contracts.state import (
    ActionFamily,
    BatteryParams,
    Control,
    Track,
    VehicleParams,
    VehicleState,
)
from ..race_value.lap_map import TerminalValue, usable_energy_j
from ..simulation.plant import Plant, initial_state
from ..simulation.rivals import (
    RivalPolicy,
    RivalPolicyConfig,
    rival_control,
)
from .controllers import Controller, Decision, ReferenceController

PASS_GAP_M = 0.0
GAIN_THRESHOLD_M = 5.0


@dataclass
class EpisodeConfig:
    duration_s: float = 40.0
    dt_s: float = 0.05
    replan_interval_s: float = 1.0
    decision_budget_s: float = 0.2
    ego_progress_m: float = 0.0
    rival_progress_m: float = 30.0
    initial_speed_mps: float = 80.0
    laps_remaining: int = 20
    run_mode: str = "simulation"


@dataclass
class RivalRuntime:
    """Rival truth. ``state`` and ``policy`` are evaluator-only."""

    state: VehicleState
    policy: RivalPolicy


@dataclass
class EpisodeReport:
    run_mode: str
    duration_s: float
    decisions: list[dict[str, Any]] = field(default_factory=list)
    final_gap_m: float = 0.0
    ego_final_progress_m: float = 0.0
    rival_final_progress_m: float = 0.0
    ego_final_energy_j: float = 0.0
    ego_energy_spent_j: float = 0.0
    pass_events: int = 0
    recross_events: int = 0
    contested_steps: int = 0
    ego_steps: int = 0
    saturation_counts: dict[str, int] = field(default_factory=dict)

    def summary(self) -> dict[str, Any]:
        return {
            "run_mode": self.run_mode,
            "duration_s": self.duration_s,
            "final_gap_m": self.final_gap_m,
            "ego_final_progress_m": self.ego_final_progress_m,
            "rival_final_progress_m": self.rival_final_progress_m,
            "ego_final_energy_j": self.ego_final_energy_j,
            "ego_energy_spent_j": self.ego_energy_spent_j,
            "pass_events": self.pass_events,
            "recross_events": self.recross_events,
            "decisions": len(self.decisions),
            "saturation_counts": dict(self.saturation_counts),
        }


def build_decision_input(
    ego: VehicleState,
    rival_progress_m: float,
    now_s: float,
    config: EpisodeConfig,
    battery: BatteryParams,
    observations: list[ObservationFrame] | None = None,
) -> DecisionInput:
    """Build the permitted input. Hidden rival state is deliberately absent."""
    return DecisionInput(
        time_s=now_s,
        run_mode=config.run_mode,
        ego_progress_m=ego.progress_m,
        ego_speed_mps=ego.speed_mps,
        ego_usable_energy_j=usable_energy_j(ego.battery, battery),
        ego_battery_temp_k=ego.battery.temp_k,
        gap_m=rival_progress_m - ego.progress_m,
        laps_remaining=config.laps_remaining,
        observations=list(observations or []),
        versions={"plant": "synthetic.v1", "belief": "particle.v1"},
    )


class EpisodeRunner:
    def __init__(
        self,
        track: Track,
        vehicle: VehicleParams,
        battery: BatteryParams,
        terminal_value: TerminalValue,
        config: EpisodeConfig,
        rival_config: RivalPolicyConfig | None = None,
    ) -> None:
        self.track = track
        self.vehicle = vehicle
        self.battery = battery
        self.terminal_value = terminal_value
        self.config = config
        self.rival_config = rival_config or RivalPolicyConfig()
        self._ego_plant = Plant(vehicle, battery, track)
        self._rival_plant = Plant(vehicle, battery, track)

    def run(
        self,
        controller: Controller | None = None,
        rival_policy: RivalPolicy = RivalPolicy.MATCHING,
        seed: int = 0,
        observations: list[ObservationFrame] | None = None,
    ) -> EpisodeReport:
        controller = controller or ReferenceController()
        rng = random.Random(seed)
        cfg = self.config
        ego = initial_state(
            self.battery, progress_m=cfg.ego_progress_m, speed_mps=cfg.initial_speed_mps
        )
        rival = RivalRuntime(
            state=initial_state(
                self.battery, progress_m=cfg.rival_progress_m, speed_mps=cfg.initial_speed_mps
            ),
            policy=rival_policy,
        )

        report = EpisodeReport(run_mode=cfg.run_mode, duration_s=cfg.duration_s)
        ego_energy_start = usable_energy_j(ego.battery, self.battery)

        t = 0.0
        next_decision = 0.0
        ego_control = Control(ActionFamily.REFERENCE, 0.0, cfg.initial_speed_mps, cfg.replan_interval_s)
        previous_gap: float | None = None
        previous_decision: Decision | None = None
        since_ego_attack_s = 0.0
        was_ahead = False

        while t < cfg.duration_s:
            gap = rival.state.progress_m - ego.progress_m

            if t + 1e-9 >= next_decision:
                if previous_gap is not None and previous_decision is not None:
                    gap_closed = previous_gap - gap
                    attacked = previous_decision.family in (
                        ActionFamily.ATTACK_NOW,
                        ActionFamily.ATTACK_LATER,
                    )
                    gained = gap_closed >= GAIN_THRESHOLD_M or (gap <= PASS_GAP_M < previous_gap)
                    controller.notify_gap_change(gap_closed)
                    controller.notify_commitment_outcome(attacked, gained)

                decision_input = build_decision_input(
                    ego, rival.state.progress_m, t, cfg, self.battery, observations
                )
                decision = controller.decide(decision_input, cfg.decision_budget_s)
                ego_control = Control(
                    family=decision.family,
                    p_k_dc_w=decision.p_k_dc_w,
                    target_speed_mps=decision.target_speed_mps,
                    horizon_s=cfg.replan_interval_s,
                )
                report.decisions.append(
                    {
                        "time_s": t,
                        "family": decision.family.value,
                        "status": decision.status,
                        "reason_codes": list(decision.reason_codes),
                        "p_k_dc_w": decision.p_k_dc_w,
                        "gap_m": gap,
                        "runtime_s": decision.runtime_s,
                        "search_iterations": decision.search_iterations,
                        "timed_out": decision.timed_out,
                    }
                )
                previous_gap = gap
                previous_decision = decision
                next_decision += cfg.replan_interval_s

            if ego_control.family in (ActionFamily.ATTACK_NOW, ActionFamily.PROBE):
                since_ego_attack_s += cfg.dt_s
            else:
                since_ego_attack_s = 0.0

            rival_power, rival_target = rival_control(
                rival.policy,
                ego_control.family,
                gap,
                since_ego_attack_s,
                self.rival_config,
            )
            rival_control_obj = Control(
                family=ActionFamily.REFERENCE,
                p_k_dc_w=rival_power,
                target_speed_mps=rival_target,
                horizon_s=cfg.dt_s,
            )

            ego_step = self._ego_plant.step(ego, ego_control, cfg.dt_s)
            rival_step = self._rival_plant.step(rival.state, rival_control_obj, cfg.dt_s)
            ego = ego_step.state
            rival.state = rival_step.state

            for reason in ego_step.saturation:
                report.saturation_counts[reason.value] = (
                    report.saturation_counts.get(reason.value, 0) + 1
                )

            new_gap = rival.state.progress_m - ego.progress_m
            if abs(new_gap) <= 2.0:
                report.contested_steps += 1
            is_ahead = new_gap < PASS_GAP_M
            if is_ahead and not was_ahead:
                report.pass_events += 1
            elif not is_ahead and was_ahead:
                report.recross_events += 1
            was_ahead = is_ahead

            report.ego_steps += 1
            t += cfg.dt_s

        report.final_gap_m = rival.state.progress_m - ego.progress_m
        report.ego_final_progress_m = ego.progress_m
        report.rival_final_progress_m = rival.state.progress_m
        report.ego_final_energy_j = usable_energy_j(ego.battery, self.battery)
        report.ego_energy_spent_j = max(0.0, ego_energy_start - report.ego_final_energy_j)
        return report
