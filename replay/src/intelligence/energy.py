"""Estimated energy-deployment model for the race replay.

FastF1 exposes no ERS / battery / state-of-charge channel, so this module
*estimates* electrical deployment and harvest from the driver inputs that are
available (throttle, brake, speed) and integrates them into state of charge
(SoC).

The battery is normalised to 100 "energy units" (EU):

- Deploying under full throttle above :data:`DEPLOY_SPEED_MIN` drains the budget.
- Braking harvests the most (MGU-K regen).
- Off-throttle coasting harvests a little (lift & coast).

Crucially, deployment is **self-regulating**: as SoC falls toward the reserve
floor, the effective deploy rate is throttled back. This mirrors how a real
energy-management map behaves - drivers save when the battery is low and spend
freely when it is high - and keeps the estimate inside a realistic band instead
of saturating at 0 or 100.

These numbers are a defensible engineering approximation, **not** telemetry.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Sequence

import numpy as np

from .config import DEFAULT_CONFIG, ModelConfig

# --- calibration (tunable) -------------------------------------------------
LAP_BUDGET = 100.0          # normalised battery capacity
DEPLOY_RATE = 1.2           # EU/s at full deployment
DEPLOY_THROTTLE_MIN = 80.0  # % throttle required to count as deployment
DEPLOY_SPEED_MIN = 70.0     # km/h below which deployment is not counted
HARVEST_BRAKE_RATE = 4.5    # EU/s while braking
HARVEST_COAST_RATE = 0.7    # EU/s while off-throttle and off-brake
HARVEST_COAST_THROTTLE_MAX = 15.0
HARVEST_COAST_SPEED_MIN = 50.0
BRAKE_THRESHOLD = 0.5       # brake channel is 0/1 with float noise
SOC_RESERVE = 5.0           # hard low floor for the battery
SOC_SOFT_CEIL = 45.0        # above this, deployment is unrestricted
SOC_DEPLOY_FLOOR_FACTOR = 0.15  # minimum deploy multiplier at/below reserve
ATTACK_MIN_SCORE = 10.0     # require at least a MEDIUM-grade window to attack

MODE_ATTACK = "ATTACK"
MODE_BALANCED = "BALANCED"
MODE_HARVEST = "HARVEST"
MODE_LIFT_COAST = "LIFT & COAST"


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


@dataclass
class EnergySnapshot:
    """Estimated energy state for a single driver at a single frame."""

    soc: float             # remaining battery energy (0..100 EU)
    deploy: float          # current effective deployment rate (EU/s)
    harvest: float         # current harvest rate (EU/s)
    balance: float         # net energy flow (EU/s), harvest - deploy
    sustainability: float  # harvested / deployed over the lap (1.0 = neutral)
    lap: int = 0

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DeploymentAdvice:
    """Recommended energy-deployment mode for the focus driver."""

    mode: str
    reason: str
    urgency: float  # 0..1, how time-critical the call is

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def is_braking(brake: Any) -> bool:
    return _num(brake) >= BRAKE_THRESHOLD


def soc_deploy_factor(
    soc: float,
    reserve: float = SOC_RESERVE,
    soft_ceil: float = SOC_SOFT_CEIL,
    floor: float = SOC_DEPLOY_FLOOR_FACTOR,
) -> float:
    """How much deployment the current battery level allows (floor..1.0)."""
    span = max(1e-6, float(soft_ceil) - float(reserve))
    return _clamp((_num(soc) - reserve) / span, float(floor), 1.0)


def deploy_rate(throttle: Any, speed: Any, config: Optional[ModelConfig] = None) -> float:
    """Instantaneous *requested* deployment rate (EU/s) from driver inputs."""
    cfg = config or DEFAULT_CONFIG
    t = _num(throttle)
    s = _num(speed)
    if t < cfg.deploy_throttle_min or s < cfg.deploy_speed_min:
        return 0.0
    span = max(1.0, 100.0 - cfg.deploy_throttle_min)
    factor = _clamp((t - cfg.deploy_throttle_min) / span, 0.0, 1.0)
    return cfg.deploy_rate * factor


def harvest_rate(throttle: Any, brake: Any, speed: Any, config: Optional[ModelConfig] = None) -> float:
    """Instantaneous harvest rate (EU/s) from driver inputs."""
    cfg = config or DEFAULT_CONFIG
    if is_braking(brake):
        return cfg.harvest_brake_rate
    t = _num(throttle)
    s = _num(speed)
    if t <= HARVEST_COAST_THROTTLE_MAX and s >= HARVEST_COAST_SPEED_MIN:
        return cfg.harvest_coast_rate
    return 0.0


@dataclass
class DriverEnergySeries:
    """Compact per-driver energy series for fast per-frame lookup."""

    soc: "np.ndarray"
    deploy: "np.ndarray"
    harvest: "np.ndarray"
    lap: "np.ndarray"
    lap_start: "np.ndarray"
    cum_deploy: "np.ndarray"
    cum_harvest: "np.ndarray"

    def __len__(self) -> int:
        return int(self.soc.size)

    def snapshot(self, index: int) -> EnergySnapshot:
        n = len(self)
        if n == 0:
            return EnergySnapshot(0.0, 0.0, 0.0, 0.0, 1.0, 0)
        i = max(0, min(int(index), n - 1))
        j = int(self.lap_start[i])
        dep = float(self.cum_deploy[i + 1] - self.cum_deploy[j])
        har = float(self.cum_harvest[i + 1] - self.cum_harvest[j])
        sustainability = (har / dep) if dep > 1e-6 else 1.0
        return EnergySnapshot(
            soc=float(self.soc[i]),
            deploy=float(self.deploy[i]),
            harvest=float(self.harvest[i]),
            balance=float(self.harvest[i] - self.deploy[i]),
            sustainability=_clamp(sustainability, 0.0, 2.0),
            lap=int(self.lap[i]),
        )


def estimate_arrays(
    t: Sequence[float],
    throttle: Sequence[float],
    brake: Sequence[float],
    speed: Sequence[float],
    lap: Sequence[Any],
    start_soc: Optional[float] = None,
    reserve: Optional[float] = None,
    soft_ceil: Optional[float] = None,
    config: Optional[ModelConfig] = None,
) -> DriverEnergySeries:
    """Vectorised SoC estimate; ~25x faster than the object-based series."""
    cfg = config or DEFAULT_CONFIG
    if start_soc is None:
        start_soc = cfg.lap_budget
    if reserve is None:
        reserve = cfg.soc_reserve
    if soft_ceil is None:
        soft_ceil = cfg.soc_soft_ceil
    t_arr = np.asarray(t, dtype=np.float64)
    n = int(t_arr.size)
    if n == 0:
        z = np.zeros(0)
        return DriverEnergySeries(z, z, z, np.zeros(0, dtype=np.int64), np.zeros(0, dtype=np.int64), np.zeros(1), np.zeros(1))

    thr = np.asarray(throttle, dtype=np.float64)
    brk = np.asarray(brake, dtype=np.float64)
    spd = np.asarray(speed, dtype=np.float64)
    lap_arr = np.asarray(lap)

    span = max(1.0, 100.0 - cfg.deploy_throttle_min)
    requested = np.where(
        (thr >= cfg.deploy_throttle_min) & (spd >= cfg.deploy_speed_min),
        cfg.deploy_rate * np.clip((thr - cfg.deploy_throttle_min) / span, 0.0, 1.0),
        0.0,
    )
    harvested = np.where(
        brk >= BRAKE_THRESHOLD,
        cfg.harvest_brake_rate,
        np.where(
            (thr <= HARVEST_COAST_THROTTLE_MAX) & (spd >= HARVEST_COAST_SPEED_MIN),
            cfg.harvest_coast_rate,
            0.0,
        ),
    )
    dt = np.maximum(np.diff(t_arr, prepend=t_arr[0]), 0.0)

    soc = np.empty(n, dtype=np.float64)
    deploy = np.empty(n, dtype=np.float64)
    s = float(start_soc)
    soft_span = max(1e-6, float(soft_ceil) - float(reserve))
    floor = cfg.soc_deploy_floor_factor
    req_l = requested.tolist()
    har_l = harvested.tolist()
    dt_l = dt.tolist()
    for i in range(n):
        factor = (s - reserve) / soft_span
        if factor < floor:
            factor = floor
        elif factor > 1.0:
            factor = 1.0
        d = req_l[i] * factor
        s += (har_l[i] - d) * dt_l[i]
        if s < 0.0:
            s = 0.0
        elif s > cfg.lap_budget:
            s = cfg.lap_budget
        soc[i] = s
        deploy[i] = d

    lap_start = np.zeros(n, dtype=np.int64)
    start = 0
    prev = lap_arr[0]
    for i in range(n):
        if lap_arr[i] != prev:
            start = i
            prev = lap_arr[i]
        lap_start[i] = start

    cum_deploy = np.concatenate(([0.0], np.cumsum(deploy * dt)))
    cum_harvest = np.concatenate(([0.0], np.cumsum(harvested * dt)))
    return DriverEnergySeries(
        soc=soc, deploy=deploy, harvest=harvested, lap=lap_arr,
        lap_start=lap_start, cum_deploy=cum_deploy, cum_harvest=cum_harvest,
    )


def step_energy(
    soc: float,
    dt: float,
    throttle: Any,
    brake: Any,
    speed: Any,
    reserve: Optional[float] = None,
    soft_ceil: Optional[float] = None,
    config: Optional[ModelConfig] = None,
) -> tuple:
    """Advance SoC by ``dt`` for a single sample; returns ``(soc, deploy, harvest)``.

    Uses the same self-regulating deploy factor as the batch estimator, so
    stepping sample by sample reproduces ``estimate_arrays`` exactly. This lets
    live consumers (e.g. the Race Engineer insight window) integrate in O(1).
    """
    cfg = config or DEFAULT_CONFIG
    if reserve is None:
        reserve = cfg.soc_reserve
    if soft_ceil is None:
        soft_ceil = cfg.soc_soft_ceil
    factor = soc_deploy_factor(soc, reserve, soft_ceil, cfg.soc_deploy_floor_factor)
    deploy = deploy_rate(throttle, speed, cfg) * factor
    harvest = harvest_rate(throttle, brake, speed, cfg)
    new_soc = _clamp(_num(soc) + (harvest - deploy) * max(0.0, _num(dt)), 0.0, cfg.lap_budget)
    return new_soc, deploy, harvest


class EnergyEstimator:
    """Integrates deployment/harvest into a self-regulating state of charge."""

    def __init__(
        self,
        lap_budget: Optional[float] = None,
        reserve: Optional[float] = None,
        soft_ceil: Optional[float] = None,
        start_soc: Optional[float] = None,
        config: Optional[ModelConfig] = None,
    ):
        self.config = config or DEFAULT_CONFIG
        self.lap_budget = float(self.config.lap_budget if lap_budget is None else lap_budget)
        self.reserve = float(self.config.soc_reserve if reserve is None else reserve)
        self.soft_ceil = float(self.config.soc_soft_ceil if soft_ceil is None else soft_ceil)
        self.start_soc = float(self.lap_budget if start_soc is None else start_soc)

    def estimate_series(self, samples: Sequence[Dict[str, Any]]) -> List[EnergySnapshot]:
        """Estimate energy for an ordered per-driver sample series.

        Each sample needs ``t`` (seconds), and optionally ``throttle``,
        ``brake``, ``speed`` and ``lap``.
        """
        out: List[EnergySnapshot] = []
        if not samples:
            return out

        soc = self.start_soc
        prev_t = _num(samples[0].get("t"))
        lap_deploy = 0.0
        lap_harvest = 0.0
        prev_lap = samples[0].get("lap")

        for sample in samples:
            t = _num(sample.get("t"))
            dt = max(0.0, t - prev_t)
            lap = sample.get("lap", prev_lap)
            if lap != prev_lap:
                # New lap: reset only the per-lap sustainability accumulator.
                lap_deploy = 0.0
                lap_harvest = 0.0
                prev_lap = lap

            requested = deploy_rate(sample.get("throttle"), sample.get("speed"), self.config)
            deploy = requested * soc_deploy_factor(soc, self.reserve, self.soft_ceil,
                                                   self.config.soc_deploy_floor_factor)
            harvest = harvest_rate(sample.get("throttle"), sample.get("brake"), sample.get("speed"), self.config)

            soc = _clamp(soc + (harvest - deploy) * dt, 0.0, self.lap_budget)
            lap_deploy += deploy * dt
            lap_harvest += harvest * dt
            sustainability = (lap_harvest / lap_deploy) if lap_deploy > 1e-6 else 1.0

            out.append(
                EnergySnapshot(
                    soc=soc,
                    deploy=deploy,
                    harvest=harvest,
                    balance=harvest - deploy,
                    sustainability=_clamp(sustainability, 0.0, 2.0),
                    lap=int(lap) if lap is not None else 0,
                )
            )
            prev_t = t

        return out

    def estimate_arrays(
        self,
        t: Sequence[float],
        throttle: Sequence[float],
        brake: Sequence[float],
        speed: Sequence[float],
        lap: Sequence[Any],
    ) -> "DriverEnergySeries":
        """Fast SoC-series estimate over numpy arrays (no per-sample objects)."""
        return estimate_arrays(
            t, throttle, brake, speed, lap,
            start_soc=self.start_soc, reserve=self.reserve, soft_ceil=self.soft_ceil,
            config=self.config,
        )


def recommend_deployment_mode(
    soc: float,
    gap_ahead_s: Optional[float] = None,
    laps_remaining: Optional[int] = None,
    drs: bool = False,
    tyre_life: Optional[float] = None,
    overtake_score: float = 0.0,
    config: Optional[ModelConfig] = None,
) -> DeploymentAdvice:
    """Pick a deployment mode that balances short-term attack vs. battery life."""
    cfg = config or DEFAULT_CONFIG
    soc = _num(soc, 100.0)

    if soc < cfg.lift_coast_soc:
        return DeploymentAdvice(
            MODE_LIFT_COAST,
            "Battery critically low - lift & coast to recover",
            urgency=1.0,
        )
    if soc < cfg.harvest_soc:
        return DeploymentAdvice(
            MODE_HARVEST,
            "Reserve low - harvest to rebuild the battery",
            urgency=_clamp((cfg.harvest_soc - soc) / 20.0, 0.0, 1.0),
        )

    in_window = gap_ahead_s is not None and gap_ahead_s <= cfg.attack_max_gap_s
    if in_window and soc >= cfg.attack_min_soc and overtake_score >= cfg.attack_min_score:
        urgency = _clamp(1.0 - (_num(gap_ahead_s) / max(1e-6, cfg.attack_max_gap_s)), 0.0, 1.0)
        if drs:
            urgency = _clamp(urgency + 0.2, 0.0, 1.0)
        return DeploymentAdvice(
            MODE_ATTACK,
            f"Overtake window vs car ahead ({gap_ahead_s:.1f}s) - deploy now",
            urgency=urgency,
        )

    return DeploymentAdvice(
        MODE_BALANCED,
        "No immediate window - manage energy for later",
        urgency=0.0,
    )
