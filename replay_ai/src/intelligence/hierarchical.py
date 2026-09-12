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
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple


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
    """Rolling-baseline feature extraction; no future samples are consulted."""

    def __init__(self, window: int = 5) -> None:
        self.window = max(1, int(window))
        self._speed: List[float] = []
        self._gaps: List[float] = []
        self._brakes: List[float] = []
        self._previous_gap = 0.0

    def update(self, o: RivalTelemetry) -> RivalFeatures:
        speed = float(o.speed_kmh)
        baseline = sum(self._speed) / len(self._speed) if self._speed else speed
        gap_delta = self._previous_gap - float(o.gap_s) if self._gaps else 0.0
        brake_mean = sum(self._brakes) / len(self._brakes) if self._brakes else float(o.brake)
        speeds = self._speed + [speed]
        mean = sum(speeds) / len(speeds)
        variance = sum((x - mean) ** 2 for x in speeds) / len(speeds)
        # A clip is an observation, not proof of a depleted battery.
        clip = 1.0 if float(o.throttle_pct) >= 98.0 and speed < baseline - 1.0 else 0.0
        features = RivalFeatures(speed - baseline, gap_delta, clip,
                                 float(o.brake) - brake_mean, variance,
                                 max(0.0, min(1.0, float(o.active_aero))))
        self._speed = (self._speed + [speed])[-self.window:]
        self._gaps = (self._gaps + [float(o.gap_s)])[-self.window:]
        self._brakes = (self._brakes + [float(o.brake)])[-self.window:]
        self._previous_gap = float(o.gap_s)
        return features


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

        def transition(previous: HMMState, current: HMMState) -> float:
            if self.mode_transition:
                row = self.mode_transition.get(previous[0].value, {})
                mode_probability = row.get(current[0].value, 0.0)
                # Override and tyre are not labelled by public telemetry here;
                # distribute their transition mass uniformly.
                return mode_probability / (len(OverrideMode) * len(TyreState))
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
            error = (((features.dgap - closure) / scales[0]) ** 2 +
                     ((features.throttle_clip - clip) / scales[1]) ** 2 +
                     ((features.brake_delta - brake) / scales[2]) ** 2)
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
    """Small finite-horizon DP for retain/replace battery decisions."""
    def __init__(self, races: int = 5, replacement_cost: float = 0.18) -> None:
        self.races = max(1, races)
        self.replacement_cost = replacement_cost

    def decide(self, soh: float, temperature: float = 70.0) -> SOHDecision:
        soh = max(0.0, min(1.0, soh))
        resistance = 1.0 + (1.0 - soh) * (0.4 + max(0.0, temperature - 60.0) / 500.0)
        retain = sum((1.0 - soh) * resistance * (i + 1) / self.races for i in range(self.races))
        replace = retain > self.replacement_cost
        return SOHDecision(1.0 if replace else soh, 1.0 if replace else resistance,
                           self.replacement_cost if replace else retain, replace)


@dataclass(frozen=True)
class TacticalDecision:
    command: str
    target_speed_kmh: float
    lambda_kin: float
    lambda_b: float
    envelope_feasible: bool
    reason: str


class MotorsportIntelligence:
    """End-to-end sector/lap facade consumed by replay and training scripts."""
    def __init__(self, hmm_artifact: str | None = None) -> None:
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
        self.level2 = BoundedScenarioPlanner()
        self.last_hmm: HMMResult | None = None
        self.last_level2 = None

    def observe(self, observation: RivalTelemetry, own_speed_kmh: float = 0.0,
                own_soc: float = 70.0, gap_s: float | None = None) -> TacticalDecision:
        result = self.hmm.update(self.features.update(observation))
        self.last_hmm = result
        observed_gap = gap_s if gap_s is not None else observation.gap_s
        plan = self.level2.plan(result, own_speed_kmh, observed_gap, own_soc)
        self.last_level2 = plan
        target = plan.reference_speed_kmh[0] if plan.reference_speed_kmh else own_speed_kmh
        feasible = plan.envelope.feasible and own_soc >= 5.0
        reason = {
            "BURN": "rival derate probability and continuation value support attack",
            "HARVEST": "rival may be hoarding energy; protect reserve",
            "PROACTIVE TRAP": "probe response while preserving continuation energy",
        }[plan.command]
        return TacticalDecision(
            plan.command,
            target if feasible else own_speed_kmh,
            plan.lambda_kin[0] if plan.lambda_kin else 0.0,
            plan.lambda_b,
            feasible,
            reason,
        )
