"""Hierarchical motorsport intelligence backend for replay telemetry.

This module is deliberately explicit about observability: FastF1 does not expose
battery SOC or ECU deployment.  The HMM therefore estimates *belief over ERS
modes* from public signals; ``soc_probabilities`` is not a sensor reading.
The implementation is a deterministic, dependency-light reference backend that
can later be replaced by fitted emissions, a neural lap map, or a full POMCP
solver without changing the replay contract.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from enum import Enum
from itertools import product
from collections import defaultdict, deque
from typing import Deque, Dict, Iterable, List, Mapping, Sequence, Tuple


class ERSMode(str, Enum):
    HIGH = "H"
    MEDIUM = "M"
    HARVEST = "Lharvest"
    DERATE = "Lderate"


class OverrideMode(str, Enum):
    AVAILABLE = "available"
    SPENT = "spent"


class TyreState(str, Enum):
    NEW = "new"
    LIGHT = "light"
    MODERATE = "moderate"
    HEAVY = "heavy"
    CLIFF = "cliff"


HMMState = Tuple[ERSMode, OverrideMode, TyreState]
STATES: Tuple[HMMState, ...] = tuple(product(ERSMode, OverrideMode, TyreState))


@dataclass(frozen=True)
class RivalTelemetry:
    """Publicly available observation at a sector boundary.

    ``active_aero`` is a normalized public aero/DRS proxy (0..1) when the
    source has no direct aero channel.  ``sector`` is used to reset baselines.
    """
    speed_kmh: float
    throttle_pct: float
    brake: float
    gap_s: float
    active_aero: float = 0.0
    sector: int = 0
    lap: int = 0
    tyre_life: float = 0.0


@dataclass(frozen=True)
class RivalFeatures:
    dv_baseline: float
    dgap: float
    throttle_clip: float
    brake_delta: float
    speed_variance: float
    aero: float
    tyre_life: float = 0.0


@dataclass(frozen=True)
class HMMResult:
    belief: Mapping[HMMState, float]
    ers_probabilities: Mapping[str, float]
    most_likely_state: HMMState
    features: RivalFeatures

    @property
    def estimated_soc_mode(self) -> str:
        """Most likely ERS mode, explicitly an estimate from public telemetry."""
        return max(self.ers_probabilities, key=self.ers_probabilities.get)


class FeatureExtractor:
    """Causal, sector-aligned rolling five-lap feature extraction.

    A baseline made from adjacent samples confounds corners with straights. This
    extractor only promotes a lap into history after a later lap is observed,
    and compares each sample with prior completed laps from the same sector.
    """

    def __init__(self, window: int = 5) -> None:
        self.window = max(1, int(window))
        self._current_lap: int | None = None
        self._current: Dict[int, List[Tuple[float, float]]] = defaultdict(list)
        self._history: Dict[int, Deque[Tuple[float, float]]] = defaultdict(
            lambda: deque(maxlen=self.window)
        )
        self._sector_speeds: Dict[int, Deque[float]] = defaultdict(
            lambda: deque(maxlen=50)
        )
        self._clip_counts: Dict[Tuple[int, int], List[int]] = defaultdict(
            lambda: [0, 0]
        )
        self._previous_gap: float | None = None

    def _complete_lap(self) -> None:
        for sector, samples in self._current.items():
            if samples:
                speed = sum(value[0] for value in samples) / len(samples)
                brake = sum(value[1] for value in samples) / len(samples)
                self._history[sector].append((speed, brake))
        self._current.clear()

    def update(self, o: RivalTelemetry) -> RivalFeatures:
        lap, sector = int(o.lap), int(o.sector)
        if self._current_lap is None:
            self._current_lap = lap
        elif lap != self._current_lap:
            self._complete_lap()
            self._clip_counts.clear()
            self._current_lap = lap

        speed, brake = float(o.speed_kmh), float(o.brake)
        history = self._history[sector]
        baseline_speed = (sum(value[0] for value in history) / len(history)
                          if history else speed)
        baseline_brake = (sum(value[1] for value in history) / len(history)
                          if history else brake)
        recent = self._sector_speeds[sector]
        values = tuple(recent) + (speed,)
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / len(values)

        # Public telemetry has no explicit straight flag. Full-throttle samples
        # form the conservative denominator; the result is a duration fraction,
        # not a one-frame depleted-battery assertion.
        counts = self._clip_counts[(lap, sector)]
        if float(o.throttle_pct) >= 98.0:
            counts[1] += 1
            if history and speed < baseline_speed - 1.0:
                counts[0] += 1
        clipping_fraction = counts[0] / counts[1] if counts[1] else 0.0
        gap_delta = (self._previous_gap - float(o.gap_s)
                     if self._previous_gap is not None else 0.0)
        self._previous_gap = float(o.gap_s)
        self._current[sector].append((speed, brake))
        recent.append(speed)
        return RivalFeatures(
            speed - baseline_speed, gap_delta, clipping_fraction,
            brake - baseline_brake, variance,
            max(0.0, min(1.0, float(o.active_aero))),
            max(0.0, float(o.tyre_life)),
        )


class FortyStateHMM:
    """Forward HMM over ERS x override x tyre (4 x 2 x 5 = 40 states)."""

    def __init__(self, self_transition: float = 0.92, sigma: float = 1.0,
                 emission_means: Mapping[str, Mapping[str, float]] | None = None,
                 emission_sigma: Mapping[str, float] | None = None,
                 mode_transition: Mapping[str, Mapping[str, float]] | None = None) -> None:
        self.sigma = max(1e-6, float(sigma))
        self.self_transition = max(0.0, min(1.0, float(self_transition)))
        self._belief: Dict[HMMState, float] = {s: 1.0 / len(STATES) for s in STATES}
        self._extractor = FeatureExtractor()
        self.emission_means = dict(emission_means or {})
        # Per-feature scale. A single scalar sigma leaves the likelihood almost
        # flat across modes because feature errors are small (~0.01-0.3), so
        # calibrated scales are required for the filter to discriminate at all.
        self.emission_sigma = dict(emission_sigma or {})
        self.mode_transition = {
            mode: dict(row) for mode, row in (mode_transition or {}).items()
        }

    @classmethod
    def from_artifact(cls, path: str, **kwargs) -> "FortyStateHMM":
        """Load fitted means and scales produced by ``fit_hmm_emissions.py``."""
        with open(path) as source:
            artifact = json.load(source)
        means = artifact.get("means", artifact)
        keep = {"dgap", "throttle_clip", "brake_delta"}
        # ``samples``/``variance`` are calibration metadata, not emissions.
        clean = {mode: {key: value for key, value in values.items() if key in keep}
                 for mode, values in means.items()}
        kwargs.setdefault("emission_sigma", artifact.get("sigma") or None)
        kwargs.setdefault("mode_transition", artifact.get("transition") or None)
        return cls(emission_means=clean, **kwargs)

    def observe(self, observation: RivalTelemetry) -> HMMResult:
        """Extract causal features and process one sector observation."""
        return self.update(self._extractor.update(observation))

    @property
    def belief(self) -> Dict[HMMState, float]:
        return dict(self._belief)

    def _expected(self, state: HMMState, f: RivalFeatures) -> Tuple[float, float, float]:
        ers, override, tyre = state
        # Means are interpretable initial priors and should be fitted on labelled
        # telemetry before being presented as a validated physical estimator.
        defaults = {
            ERSMode.HIGH.value: {"dgap": .10, "throttle_clip": .00, "brake_delta": 0.0},
            ERSMode.MEDIUM.value: {"dgap": .03, "throttle_clip": .05, "brake_delta": 0.0},
            # Deliberate lift/managed pedal is not a super-clip; its public
            # signature is a small negative closure (the rival preserves pace
            # while the ego does not gain) with no pinned-throttle clipping.
            ERSMode.HARVEST.value: {"dgap": -.05, "throttle_clip": .00, "brake_delta": 0.0},
            ERSMode.DERATE.value: {"dgap": .16, "throttle_clip": .55, "brake_delta": 0.0},
        }
        means = {**defaults.get(ers.value, {}), **self.emission_means.get(ers.value, {})}
        closure = means["dgap"]
        clip = means["throttle_clip"]
        brake = means["brake_delta"] + (.10 if override is OverrideMode.SPENT else 0.0)
        return closure, clip, brake

    def update(self, features: RivalFeatures) -> HMMResult:
        n = len(STATES)
        switch = (1.0 - self.self_transition) / (n - 1)

        def factor_transition(previous, current, values, persistence: float) -> float:
            return (persistence if previous is current else
                    (1.0 - persistence) / (len(values) - 1))

        def transition(previous: HMMState, current: HMMState) -> float:
            if self.mode_transition:
                row = self.mode_transition.get(previous[0].value, {})
                mode_probability = row.get(current[0].value, 0.0)
                # Fitted ERS transitions must not erase the unlabelled factors.
                # Preserve override and tyre persistence until evidence changes it.
                return (mode_probability *
                        factor_transition(previous[1], current[1], OverrideMode, 0.97) *
                        factor_transition(previous[2], current[2], TyreState, 0.985))
            return self.self_transition if previous == current else switch

        predicted = {s: sum(self._belief[p] * transition(p, s) for p in STATES)
                     for s in STATES}
        likelihood: Dict[HMMState, float] = {}
        # Diagonal Gaussian per feature. Scale falls back to the scalar sigma
        # for any feature the artifact did not supply.
        scales = tuple(
            max(1e-6, float(self.emission_sigma.get(name, self.sigma)))
            for name in ("dgap", "throttle_clip", "brake_delta")
        )
        for state in STATES:
            closure, clip, brake = self._expected(state, features)
            tyre_expected = {
                TyreState.NEW: 2.0,
                TyreState.LIGHT: 8.0,
                TyreState.MODERATE: 18.0,
                TyreState.HEAVY: 30.0,
                TyreState.CLIFF: 45.0,
            }[state[2]]
            error = (((features.dgap - closure) / scales[0]) ** 2 +
                     ((features.throttle_clip - clip) / scales[1]) ** 2 +
                     ((features.brake_delta - brake) / scales[2]) ** 2 +
                     ((features.tyre_life - tyre_expected) / 10.0) ** 2)
            likelihood[state] = math.exp(-0.5 * error)
        weighted = {s: predicted[s] * likelihood[s] for s in STATES}
        total = sum(weighted.values()) or 1.0
        self._belief = {s: weighted[s] / total for s in STATES}
        ers = {mode.value: sum(p for s, p in self._belief.items() if s[0] is mode)
               for mode in ERSMode}
        likely = max(self._belief, key=self._belief.get)
        return HMMResult(self.belief, ers, likely, features)


@dataclass(frozen=True)
class SOHDecision:
    soh: float
    resistance: float
    wear_cost: float
    replace: bool


class SeasonLifecycleManager:
    """Finite-horizon retain/replace dynamic program over discretized SOH.

    Costs are time-equivalent development parameters, not identified cell or
    championship-point values. The DP is intentionally small enough to rerun at
    an event boundary and passes its marginal wear value down to Level 3.
    """
    def __init__(self, races: int = 5, replacement_cost: float = 0.18,
                 degradation_per_race: float = 0.012) -> None:
        self.races = max(1, races)
        self.replacement_cost = max(0.0, float(replacement_cost))
        self.degradation_per_race = max(0.0, float(degradation_per_race))

    @staticmethod
    def _resistance(soh: float, temperature: float) -> float:
        return 1.0 + (1.0 - soh) * (
            0.4 + max(0.0, temperature - 60.0) / 500.0)

    def decide(self, soh: float, temperature: float = 70.0) -> SOHDecision:
        from functools import lru_cache

        initial = max(0.0, min(1.0, float(soh)))
        thermal_multiplier = 1.0 + max(0.0, float(temperature) - 70.0) / 80.0
        fade = self.degradation_per_race * thermal_multiplier

        @lru_cache(maxsize=None)
        def value(event: int, soh_percent: int) -> tuple[float, bool]:
            if event >= self.races:
                return 0.0, False
            state = soh_percent / 100.0

            def next_value(start: float) -> float:
                after = max(0.0, start - fade)
                future, _ = value(event + 1, int(round(after * 100.0)))
                running = (1.0 - start) * self._resistance(start, temperature)
                return running + future

            retain_cost = next_value(state)
            replace_cost = self.replacement_cost + next_value(1.0)
            return ((replace_cost, True) if replace_cost < retain_cost
                    else (retain_cost, False))

        optimal_cost, replace = value(0, int(round(initial * 100.0)))
        effective_soh = 1.0 if replace else initial
        resistance = self._resistance(effective_soh, temperature)
        return SOHDecision(effective_soh, resistance, optimal_cost, replace)


@dataclass(frozen=True)
class TacticalDecision:
    command: str
    target_speed_kmh: float
    lambda_kin: float
    lambda_b: float
    envelope_feasible: bool
    reason: str
    lap_energy_target: float | None = None


class MotorsportIntelligence:
    """End-to-end sector/lap facade consumed by replay and training scripts."""
    def __init__(self, hmm_artifact: str | None = None,
                 lap_map_artifact: str | None = None,
                 use_search: bool = True, use_spatial: bool = True,
                 use_soh: bool = True) -> None:
        self.features = FeatureExtractor()
        self.hmm_source = "default"
        if hmm_artifact:
            try:
                self.hmm = FortyStateHMM.from_artifact(hmm_artifact)
                self.hmm_source = hmm_artifact
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
                # A missing/stale calibration must not prevent replay startup.
                self.hmm = FortyStateHMM()
        else:
            self.hmm = FortyStateHMM()
        self.lifecycle = SeasonLifecycleManager()
        # Imported lazily to keep the HMM module usable as a small standalone
        # inference component without introducing a module cycle.
        from .control_layers import BoundedScenarioPlanner
        self.use_soh = use_soh
        self.level2 = BoundedScenarioPlanner(use_search=use_search,
                                             use_spatial=use_spatial)
        self.lap_map = None
        self.lap_map_source = "unavailable"
        self.lap_planner = None
        self.last_lap_plan = None
        self.last_soh_decision = None
        self._planned_lap = None
        if lap_map_artifact:
            try:
                from .lap_strategy import LapTimeMap, RaceEnergyPlanner
                self.lap_map = LapTimeMap.from_file(lap_map_artifact)
                self.lap_planner = RaceEnergyPlanner(self.lap_map)
                self.lap_map_source = lap_map_artifact
            except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
                self.lap_map = None
                self.lap_planner = None
        self.last_hmm: HMMResult | None = None
        self.last_level2 = None
        self._runtime_battery_soh = 1.0
        self._runtime_battery_temperature = 70.0

    def runtime_metrics(self) -> dict:
        """Serializable diagnostics consumed by the runtime HUD/API."""
        soh = self._runtime_battery_soh
        soh_decision = self.last_soh_decision
        envelope = getattr(self.last_level2, "envelope", None)
        spatial = getattr(self.last_level2, "spatial_reference", None)
        return {
            "hmm_source": self.hmm_source,
            "lap_map_source": self.lap_map_source,
            "battery_soh": soh,
            "battery_resistance": (soh_decision.resistance if soh_decision else
                                    1.0 + (1.0 - soh) * 0.4),
            "battery_wear_cost": soh_decision.wear_cost if soh_decision else 0.0,
            "lap_target_energy": (self.last_lap_plan[0].deploy_energy
                                   if self.last_lap_plan else None),
            "socp_feasible": (spatial.envelope.feasible if spatial else
                               (envelope.feasible if envelope else None)),
            "socp_residual": (spatial.envelope.max_residual if spatial else
                              (getattr(envelope, "max_residual", None)
                               if envelope else None)),
            "scenario_values": (dict(self.last_level2.search_values)
                                 if self.last_level2 else {}),
            "scenario_risk_values": (dict(self.last_level2.search_risk_values or {})
                                     if self.last_level2 else {}),
            "scenario_particles": (self.last_level2.search_particles
                                    if self.last_level2 else 0),
            "scenario_histories": (self.last_level2.search_histories
                                    if self.last_level2 else 0),
            "spatial_speed_profile": (list(self.last_level2.reference_speed_kmh)
                                       if self.last_level2 else []),
            "kinetic_costates": (list(self.last_level2.lambda_kin)
                                  if self.last_level2 else []),
            "spatial_residual": (self.last_level2.spatial_residual
                                  if self.last_level2 else None),
        }

    def plan_lap(self, lap: int, energy: float, tyre_wear: float = 0.0,
                 battery_soh: float = 1.0, battery_temperature: float = 70.0):
        """Re-plan the remaining configured horizon at a lap boundary."""
        if self.lap_planner is None:
            return None
        if self._planned_lap == lap and self.last_lap_plan is not None:
            return self.last_lap_plan
        effective_soh = battery_soh if self.use_soh else 1.0
        effective_wear = tyre_wear if self.use_soh else 0.0
        self.last_soh_decision = self.lifecycle.decide(
            effective_soh, battery_temperature)
        self.last_lap_plan = self.lap_planner.plan(
            energy, effective_wear, battery_soh=effective_soh,
            wear_cost=self.last_soh_decision.wear_cost if self.use_soh else 0.0,
        )
        self._planned_lap = lap
        return self.last_lap_plan

    def observe(self, observation: RivalTelemetry, own_speed_kmh: float = 0.0,
                own_soc: float = 70.0, gap_s: float | None = None,
                battery_soh: float = 1.0,
                battery_temperature: float = 70.0) -> TacticalDecision:
        self._runtime_battery_soh = float(battery_soh)
        self._runtime_battery_temperature = float(battery_temperature)
        if self.lap_planner is not None:
            self.plan_lap(observation.lap, own_soc, observation.tyre_life,
                          battery_soh, battery_temperature)
        result = self.hmm.update(self.features.update(observation))
        self.last_hmm = result
        observed_gap = gap_s if gap_s is not None else observation.gap_s
        tactical_wear_cost = ((1.0 - battery_soh) * 0.8
                              if self.use_soh else 0.0)
        plan = self.level2.plan(result, own_speed_kmh, observed_gap, own_soc,
                                wear_cost=tactical_wear_cost)
        self.last_level2 = plan
        target = plan.reference_speed_kmh[0] if plan.reference_speed_kmh else own_speed_kmh
        feasible = plan.envelope.feasible and own_soc >= 5.0
        reason = {
            "BURN": "rival derate probability and continuation value support attack",
            "HARVEST": "rival may be hoarding energy; protect reserve",
            "PROACTIVE TRAP": "probe response while preserving continuation energy",
        }[plan.command]
        lap_energy_target = (
            self.last_lap_plan[0].deploy_energy
            if self.last_lap_plan else None
        )
        return TacticalDecision(
            plan.command,
            target if feasible else own_speed_kmh,
            plan.lambda_kin[0] if plan.lambda_kin else 0.0,
            plan.lambda_b,
            feasible,
            reason,
            lap_energy_target,
        )
