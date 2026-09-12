"""Overtake-window risk / reward evaluation.

For a *potential* overtake (focus driver vs. the car directly ahead) this scores
the reward of attempting it against the risk of it failing, using only signals
available in the replay:

- Reward: proximity, DRS, closing speed, value of the position being fought for.
- Risk:   energy reserve, tyre age, and how few laps remain to recover.

The result is a transparent, explainable score rather than a black box.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional

from .config import DEFAULT_CONFIG, ModelConfig

VERDICT_HIGH = "HIGH"
VERDICT_MEDIUM = "MEDIUM"
VERDICT_LOW = "LOW"
VERDICT_AVOID = "AVOID"


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _position_value(position: Optional[int]) -> float:
    if position is None:
        return 0.8
    if position <= 3:
        return 1.0          # podium fight - maximum value
    if position <= 10:
        return 0.85         # points fight
    return 0.7              # midfield / backmarker


@dataclass
class OvertakeAssessment:
    reward: float          # 0..100, upside of the move
    risk: float            # 0..100, downside / failure cost
    score: float           # reward - risk, roughly -100..100
    probability: float     # 0..1, modelled success chance
    verdict: str           # HIGH / MEDIUM / LOW / AVOID
    factors: Dict[str, float] = field(default_factory=dict)

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


def evaluate_overtake_window(
    gap_ahead_s: Optional[float],
    speed_delta_kmh: float = 0.0,
    drs: bool = False,
    soc: float = 100.0,
    tyre_life: float = 0.0,
    laps_remaining: Optional[int] = None,
    position: Optional[int] = None,
    config: Optional[ModelConfig] = None,
) -> OvertakeAssessment:
    """Score the overtake window against the car ahead."""
    cfg = config or DEFAULT_CONFIG
    gap_s = None if gap_ahead_s is None else _num(gap_ahead_s)
    drs_on = bool(drs)
    soc = _num(soc, 100.0)
    tyre_life = _num(tyre_life)
    speed_delta = _num(speed_delta_kmh)

    # --- reward ------------------------------------------------------------
    if gap_s is None:
        # No car ahead -> there is no overtake window to reward.
        reward = 0.0
    else:
        gap_factor = _clamp(1.0 - (gap_s / 1.5), 0.0, 1.0)
        drs_factor = 1.0 if drs_on else 0.0
        pace_factor = _clamp((speed_delta + 12.0) / 32.0, 0.0, 1.0)
        pos_value = _position_value(position)
        reward = 100.0 * (
            cfg.reward_w_gap * gap_factor
            + cfg.reward_w_drs * drs_factor
            + cfg.reward_w_pace * pace_factor
        ) * pos_value

    # --- risk --------------------------------------------------------------
    energy_risk = _clamp((40.0 - soc) / 40.0, 0.0, 1.0)
    tyre_risk = _clamp(tyre_life / 28.0, 0.0, 1.0)
    if laps_remaining is None:
        time_risk = 0.0
    else:
        time_risk = _clamp((5.0 - _num(laps_remaining)) / 5.0, 0.0, 1.0)
    risk = 100.0 * (
        cfg.risk_w_energy * energy_risk
        + cfg.risk_w_tyre * tyre_risk
        + cfg.risk_w_time * time_risk
    )

    score = reward - risk
    probability = 1.0 / (1.0 + math.exp(-(score - 15.0) / 12.0))

    if score >= 35.0:
        verdict = VERDICT_HIGH
    elif score >= 10.0:
        verdict = VERDICT_MEDIUM
    elif score >= -15.0:
        verdict = VERDICT_LOW
    else:
        verdict = VERDICT_AVOID

    return OvertakeAssessment(
        reward=reward,
        risk=risk,
        score=score,
        probability=probability,
        verdict=verdict,
        factors={
            "gap": 0.0 if gap_s is None else _clamp(1.0 - (gap_s / 1.5), 0.0, 1.0),
            "drs": 1.0 if drs_on else 0.0,
            "pace": _clamp((speed_delta + 12.0) / 32.0, 0.0, 1.0),
            "position_value": _position_value(position),
            "energy_risk": energy_risk,
            "tyre_risk": tyre_risk,
            "time_risk": time_risk,
        },
    )
