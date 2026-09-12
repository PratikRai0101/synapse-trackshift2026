"""Development / test splits with shifted physics.

A new seed from the same generator is not independent validation. The test split
therefore shifts physical parameters and rival behaviour, and the controller's
models are calibrated on the development split and evaluated on the test split.

These are declared parameter shifts within the same model family, not an
independently developed plant. That limitation is stated in the pitch.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from ..contracts.state import BatteryParams, VehicleParams
from ..simulation.rivals import RivalPolicyConfig
from ..simulation.tyres import TyreParams


@dataclass(frozen=True)
class SplitOverride:
    name: str
    description: str
    battery: dict = field(default_factory=dict)
    vehicle: dict = field(default_factory=dict)
    tyre: dict = field(default_factory=dict)
    rival: dict = field(default_factory=dict)
    calibration_split: str = "development"


SPLITS: dict[str, SplitOverride] = {
    "development": SplitOverride(
        name="development",
        description="baseline synthetic parameters",
    ),
    "calibration": SplitOverride(
        name="calibration",
        description="slightly different seeds, same physics family",
        battery={"soc_initial": 0.65},
        rival={"reaction_delay_s": 1.2},
    ),
    "test": SplitOverride(
        name="test",
        description=(
            "shifted physics and a quicker-reacting, faster defending rival; "
            "the controller's calibration comes from the development split"
        ),
        battery={"resistance_ohm": 0.028, "cooling_w_per_k": 48.0},
        vehicle={"mu_base": 1.45, "mass_kg": 820.0, "drag_area_m2": 1.6},
        tyre={"wear_rate_scale": 1.5},
        rival={
            "reaction_delay_s": 0.5,
            "attack_target_speed_mps": 92.0,
            "defend_power_w": 170_000.0,
        },
        calibration_split="development",
    ),
}


def split_override(name: str) -> SplitOverride:
    if name not in SPLITS:
        raise ValueError(f"unknown split: {name}")
    return SPLITS[name]


def apply_battery(base: BatteryParams, override: SplitOverride) -> BatteryParams:
    if not override.battery:
        return base
    return replace(base, **override.battery)


def apply_vehicle(base: VehicleParams, override: SplitOverride) -> VehicleParams:
    if not override.vehicle:
        return base
    return replace(base, **override.vehicle)


def apply_tyres(base: TyreParams, override: SplitOverride) -> TyreParams:
    if not override.tyre:
        return base
    return replace(base, **override.tyre)


def apply_rival(base: RivalPolicyConfig, override: SplitOverride) -> RivalPolicyConfig:
    if not override.rival:
        return base
    return replace(base, **override.rival)
