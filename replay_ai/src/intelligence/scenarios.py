"""Deterministic decision-scenario bookmarks for the judge demonstration.

A live pitch must not depend on the presenter happening to scrub to an
interesting moment. This module scans a recorded driver's public telemetry once
and returns the frame that best exhibits each teachable scenario.

The scan runs the *public-signal HMM only* -- the same calibrated belief the
replay HUD uses, never the hidden simulator truth. The full planner, SOCP
envelope and counterfactual simulator are still executed live when the frame is
shown, so a bookmark only guarantees "this is the moment", not "this is the
answer". Results are cached to ``computed_data`` so the live demo is instant.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Iterable, Mapping, Optional, Sequence

from src.intelligence.energy import estimate_arrays
from src.intelligence.hierarchical import FortyStateHMM, RivalTelemetry

SCENARIO_DIR = os.path.join("computed_data")

# Thresholds are public-signal heuristics aligned with the planner's own rules:
# the bounded planner only lets BURN compete when P(Lderate) >= 0.40, and only
# lets HARVEST compete when P(Lharvest) >= 0.40 or the estimated store < 30 EU.
_DOMINANCE = 0.40
_DEPLETION_SIGNAL = 0.30
_BATTLE_GAP_S = 1.5
_PROBE_MIN_GAP_S = 0.25
_LOW_ENERGY_SOC = 30.0
_LONG_STINT_LAPS = 15.0
_HOT_TRACK_C = 48.0


@dataclass(frozen=True)
class ScenarioSpec:
    key: str
    title: str
    subtitle: str


SCENARIOS: tuple[ScenarioSpec, ...] = (
    ScenarioSpec("counter_harvest", "COUNTER-HARVEST",
                 "Rival hoarding energy, not spent"),
    ScenarioSpec("depletion", "GENUINE DEPLETION",
                 "Rival physically out of energy"),
    ScenarioSpec("attack", "ATTACK APPROVED",
                 "Depleted rival, budget to pounce"),
    ScenarioSpec("envelope", "ENVELOPE BLOCKS ATTACK",
                 "Rival beatable, energy says no"),
    ScenarioSpec("trap", "PROACTIVE TRAP",
                 "Unresolved belief, probe to learn"),
    ScenarioSpec("thermal", "THERMAL CONSERVE",
                 "Long stint heat forces harvest"),
)


@dataclass(frozen=True)
class ScenarioObservation:
    """One sampled moment reduced to the signals the scenario rules need."""

    frame_index: int
    p_harvest: float
    p_derate: float
    gap_s: float
    soc: float
    tyre_life: float
    track_temp: float


def scenario_artifact_path(year: int, round_number: int) -> str:
    return os.path.join(
        SCENARIO_DIR, f"scenario_bookmarks_{int(year)}_{int(round_number):02d}.json"
    )


def _as_int(value) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _hmm_factory(hmm_artifact: Optional[str]):
    """Build independent HMMs from one shared, parsed calibration artifact."""
    if not hmm_artifact:
        return FortyStateHMM
    try:
        base = FortyStateHMM.from_artifact(hmm_artifact)
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return FortyStateHMM

    def build() -> FortyStateHMM:
        return FortyStateHMM(
            self_transition=base.self_transition,
            sigma=base.sigma,
            emission_means=base.emission_means,
            emission_sigma=base.emission_sigma,
            mode_transition=base.mode_transition,
        )

    return build


def build_energy_soc(frames: Sequence[Mapping], driver: str,
                     config=None) -> Sequence[float]:
    """Reconstruct a driver's estimated state-of-charge series from cached frames."""
    from src.intelligence.config import DEFAULT_CONFIG

    t: list[float] = []
    throttle: list[float] = []
    brake: list[float] = []
    speed: list[float] = []
    lap: list[float] = []
    last = None
    for frame in frames:
        pos = frame.get("drivers", {}).get(driver)
        if pos is not None:
            last = pos
        elif last is not None:
            pos = last
        t.append(float(frame.get("t", 0.0) or 0.0))
        if pos is None:
            throttle.append(0.0)
            brake.append(0.0)
            speed.append(0.0)
            lap.append(1)
        else:
            throttle.append(float(pos.get("throttle", 0.0) or 0.0))
            brake.append(float(pos.get("brake", 0.0) or 0.0))
            speed.append(float(pos.get("speed", 0.0) or 0.0))
            lap.append(float(pos.get("lap", 1) or 1))
    series = estimate_arrays(t, throttle, brake, speed, lap,
                             config=config or DEFAULT_CONFIG)
    return series.soc


def scan_recorded_driver(frames: Sequence[Mapping], driver: str,
                         soc_series: Sequence[float], *,
                         hmm_artifact: Optional[str] = None,
                         sample_step: int = 50,
                         min_lap: int = 2) -> tuple[ScenarioObservation, ...]:
    """One causal pass over a recorded driver's race.

    The focus driver's car-ahead becomes the inferred rival, mirroring the live
    ``RaceEngineer`` wiring, and each (focus, rival) pair keeps its own HMM so
    the belief only advances on observations that actually belong to that pair.
    """
    make_hmm = _hmm_factory(hmm_artifact)
    models: dict[tuple[str, str], FortyStateHMM] = {}
    observations: list[ScenarioObservation] = []
    step = max(1, int(sample_step))

    for index in range(0, len(frames), step):
        frame = frames[index]
        drivers = frame.get("drivers", {})
        me = drivers.get(driver)
        if not me or me.get("in_pit"):
            continue
        lap = _as_int(me.get("lap")) or 0
        if lap < int(min_lap):
            continue
        position = _as_int(me.get("position"))
        if position is None:
            continue
        ahead = next(
            (code for code, data in drivers.items()
             if _as_int(data.get("position")) == position - 1),
            None,
        )
        if ahead is None:
            continue
        rival = drivers.get(ahead, {})
        if (_as_int(rival.get("lap")) or 0) != lap:
            continue
        my_dist = float(me.get("dist", 0.0) or 0.0)
        rival_dist = float(rival.get("dist", 0.0) or 0.0)
        if rival_dist <= my_dist:
            continue
        my_speed = float(me.get("speed", 0.0) or 0.0)
        if my_speed <= 1.0:
            continue
        gap_s = (rival_dist - my_dist) / (my_speed / 3.6)

        pair = (driver, ahead)
        hmm = models.get(pair)
        if hmm is None:
            hmm = make_hmm()
            models[pair] = hmm
        result = hmm.observe(RivalTelemetry(
            speed_kmh=float(rival.get("speed", 0.0) or 0.0),
            throttle_pct=float(rival.get("throttle", 0.0) or 0.0),
            brake=float(rival.get("brake", 0.0) or 0.0),
            gap_s=gap_s,
            active_aero=1.0 if rival.get("drs", 0) in (8, 10, 12, 14) else 0.0,
            sector=_as_int(rival.get("sector")) or 0,
            lap=_as_int(rival.get("lap")) or 0,
            tyre_life=float(rival.get("tyre_life", 0.0) or 0.0),
            time_s=float(frame.get("t", 0.0) or 0.0),
        ))
        probabilities = result.ers_probabilities
        observations.append(ScenarioObservation(
            frame_index=index,
            p_harvest=float(probabilities.get("Lharvest", 0.0)),
            p_derate=float(probabilities.get("Lderate", 0.0)),
            gap_s=gap_s,
            soc=float(soc_series[index]) if index < len(soc_series) else 70.0,
            tyre_life=float(me.get("tyre_life", 0.0) or 0.0),
            track_temp=float(frame.get("weather", {}).get("track_temp", 0.0) or 0.0),
        ))
    return tuple(observations)


def scenario_candidates(observation: ScenarioObservation) -> dict[str, float]:
    """Score every scenario this moment could demonstrate (empty if none)."""
    candidates: dict[str, float] = {}
    harvest = observation.p_harvest
    derate = observation.p_derate

    if harvest >= _DOMINANCE and harvest >= derate:
        candidates["counter_harvest"] = harvest
    if derate >= _DOMINANCE and derate > harvest:
        candidates["depletion"] = derate

    if observation.gap_s <= _BATTLE_GAP_S:
        proximity = 1.0 - min(observation.gap_s, _BATTLE_GAP_S)
        if derate >= _DOMINANCE and observation.soc >= _LOW_ENERGY_SOC:
            candidates["attack"] = derate + proximity
        if derate >= _DEPLETION_SIGNAL and observation.soc < _LOW_ENERGY_SOC:
            candidates["envelope"] = derate + proximity
        if (_PROBE_MIN_GAP_S <= observation.gap_s <= _BATTLE_GAP_S
                and max(harvest, derate) < _DOMINANCE):
            candidates["trap"] = proximity

    if observation.tyre_life >= _LONG_STINT_LAPS or observation.track_temp >= _HOT_TRACK_C:
        candidates["thermal"] = (observation.tyre_life / 30.0
                                 + observation.track_temp / 60.0)
    return candidates


def select_scenario_frames(
    observations: Iterable[ScenarioObservation],
    keys: Optional[Sequence[str]] = None,
) -> dict[str, int]:
    """Pick one distinct frame per scenario, highest score first.

    Scenarios are claimed in the canonical order, so a moment that could serve
    both "genuine depletion" and "attack approved" produces two different,
    deterministic bookmarks instead of the same frame twice.
    """
    order = tuple(keys) if keys else tuple(spec.key for spec in SCENARIOS)
    ranked: dict[str, list[tuple[float, int]]] = {key: [] for key in order}
    for observation in observations:
        for key, score in scenario_candidates(observation).items():
            if key in ranked:
                ranked[key].append((score, observation.frame_index))

    chosen: dict[str, int] = {}
    used: set[int] = set()
    for key in order:
        for _score, frame in sorted(ranked[key], key=lambda item: (-item[0], item[1])):
            if frame not in used:
                chosen[key] = frame
                used.add(frame)
                break
    return chosen


def save_scenario_artifact(path: str, targets: Mapping[str, Mapping[str, int]],
                           *, year: Optional[int] = None,
                           round_number: Optional[int] = None,
                           sample_step: int = 50) -> str:
    """Persist per-driver scenario frames so the live demo loads instantly."""
    payload = {
        "year": year,
        "round": round_number,
        "sample_step": int(sample_step),
        "drivers": {
            str(driver): {str(key): int(frame) for key, frame in frames.items()}
            for driver, frames in targets.items()
        },
    }
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as sink:
        json.dump(payload, sink, indent=2, sort_keys=True)
    return path


def load_scenario_artifact(path: str) -> dict[str, dict[str, int]]:
    """Return ``{driver: {scenario_key: frame_index}}`` or ``{}`` if absent."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as source:
            payload = json.load(source)
    except (OSError, ValueError, json.JSONDecodeError):
        return {}
    drivers = payload.get("drivers", {}) if isinstance(payload, dict) else {}
    result: dict[str, dict[str, int]] = {}
    for driver, frames in drivers.items():
        if not isinstance(frames, Mapping):
            continue
        clean: dict[str, int] = {}
        for key, frame in frames.items():
            value = _as_int(frame)
            if value is not None:
                clean[str(key)] = value
        if clean:
            result[str(driver)] = clean
    return result
