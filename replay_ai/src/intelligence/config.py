"""Tunable parameters for the AI Motorsport Intelligence models.

All magic numbers in the energy estimator, the overtake score and the decision
policy live here in one dataclass so they can be inspected, overridden and
**calibrated** against real races (see :mod:`src.intelligence.backtest`).

Defaults reproduce the hand-tuned values the models shipped with. ``load_config``
reads ``computed_data/model_config.json`` if present, so calibration can persist
an operating point that the app picks up automatically.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from typing import Any, Dict, Optional

DEFAULT_CONFIG_PATH = os.path.join("computed_data", "model_config.json")


@dataclass
class ModelConfig:
    # --- energy estimator --------------------------------------------------
    lap_budget: float = 100.0            # normalised battery capacity
    deploy_rate: float = 1.2             # EU/s at full deployment
    deploy_throttle_min: float = 80.0    # % throttle required to deploy
    deploy_speed_min: float = 70.0       # km/h below which deployment is off
    harvest_brake_rate: float = 4.5      # EU/s while braking
    harvest_coast_rate: float = 0.7      # EU/s while off-throttle/off-brake
    soc_reserve: float = 5.0             # hard low floor
    soc_soft_ceil: float = 45.0          # above this, deployment is unrestricted
    soc_deploy_floor_factor: float = 0.15  # min deploy multiplier at reserve

    # --- decision policy ---------------------------------------------------
    attack_min_score: float = 10.0       # min overtake score to call ATTACK
    attack_max_gap_s: float = 1.0        # must be within this of the car ahead
    attack_min_soc: float = 45.0         # needs at least this much energy
    harvest_soc: float = 35.0            # below this -> HARVEST
    lift_coast_soc: float = 15.0         # below this -> LIFT & COAST

    # --- overtake score weights -------------------------------------------
    reward_w_gap: float = 0.5
    reward_w_drs: float = 0.3
    reward_w_pace: float = 0.2
    risk_w_energy: float = 0.5
    risk_w_tyre: float = 0.3
    risk_w_time: float = 0.2

    # -- (de)serialisation --------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "ModelConfig":
        known = {f.name for f in fields(cls)}
        clean = {k: v for k, v in (data or {}).items() if k in known}
        return cls(**clean)

    def save(self, path: Optional[str] = None) -> str:
        path = path or DEFAULT_CONFIG_PATH
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(path, "w") as fh:
            json.dump(self.to_dict(), fh, indent=2, sort_keys=True)
        return path

    @classmethod
    def load(cls, path: Optional[str] = None) -> "ModelConfig":
        path = path or DEFAULT_CONFIG_PATH
        with open(path) as fh:
            return cls.from_dict(json.load(fh))


DEFAULT_CONFIG = ModelConfig()


def load_config(path: Optional[str] = None) -> ModelConfig:
    """Load a calibrated config, falling back to defaults if absent/invalid."""
    path = path or DEFAULT_CONFIG_PATH
    if os.path.exists(path):
        try:
            return ModelConfig.load(path)
        except Exception:
            return ModelConfig()
    return ModelConfig()
