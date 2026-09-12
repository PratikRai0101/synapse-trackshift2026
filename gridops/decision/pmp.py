"""Block 4B — analytical PMP/KKT switching cues.

Given the two costates of the reduced problem — ``lambda_kin`` (marginal
remaining-time cost of kinetic energy) and ``lambda_b`` (marginal remaining-race
cost of stored electrical energy) — the optimal control switches between four
regimes on the ratio ``lambda_kin / lambda_b``:

======================  ==========================================
condition               cue
======================  ==========================================
``lambda_kin > 0``      FRICTION_BRAKE   (slow down; grip-limited)
``r < -1/eta_plus``     MAX_ACCEL        (deploy; speed is worth more)
``-1/eta_plus < r``     COAST            (lift; neither extreme pays)
``-eta_minus < r < 0``  REGEN_BRAKE      (recover; energy is worth more)
======================  ==========================================

``r = lambda_kin / lambda_b``. The thresholds follow from the conversion
efficiencies in the deployment and recovery regimes.

These are guidance cues from a declared reduced model, derived via the same
first-order conditions used in the minimum-lap-time literature. They are **not**
a certified real-time optimal controller, and the costates are marginal values
of this model, not transferable physical constants.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


CUE_MAX_ACCEL = "MAX_ACCEL"
CUE_COAST = "COAST"
CUE_REGEN = "REGEN_BRAKE"
CUE_FRICTION = "FRICTION_BRAKE"
CUE_UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class CostateState:
    lambda_kin: float
    lambda_b: float
    eta_plus: float = 0.92
    eta_minus: float = 0.92

    @property
    def ratio(self) -> float:
        if abs(self.lambda_b) < 1e-18:
            return float("nan")
        return self.lambda_kin / self.lambda_b


def switching_cue(costate: CostateState) -> str:
    if costate.lambda_b <= 0.0 or not math.isfinite(costate.lambda_b):
        return CUE_UNAVAILABLE
    if costate.lambda_kin > 0.0:
        return CUE_FRICTION
    ratio = costate.ratio
    if ratio < -1.0 / costate.eta_plus:
        return CUE_MAX_ACCEL
    if ratio < -costate.eta_minus:
        return CUE_COAST
    if ratio < 0.0:
        return CUE_REGEN
    return CUE_COAST


@dataclass(frozen=True)
class GuidancePlan:
    cue: str
    lambda_kin: float
    lambda_b: float
    ratio: float
    max_deploy_w: float
    guidance: str


_GUIDANCE = {
    CUE_MAX_ACCEL: "full throttle, deploy MGU-K",
    CUE_COAST: "lift early, hold the reference",
    CUE_REGEN: "recover under braking",
    CUE_FRICTION: "friction brake, protect the tyres",
    CUE_UNAVAILABLE: "no valid costate: hold the reference",
}


def kinetic_costate(
    speed_mps: float, mass_kg: float, grid_step_m: float = 50.0
) -> float:
    """Marginal time cost of kinetic energy in the elapsed-time surrogate.

    The planner minimises ``sum ds sqrt(m/2) e^{-1/2}``; differentiating gives
    ``-0.5 ds sqrt(m/2) e^{-3/2}`` in seconds per joule.
    """
    e_kin = 0.5 * mass_kg * max(speed_mps, 1.0) ** 2
    return -0.5 * grid_step_m * math.sqrt(mass_kg / 2.0) * e_kin ** -1.5


def battery_costate(race_value, usable_energy_j: float, laps_remaining: int, delta_j: float = 10_000.0) -> float:
    """Marginal remaining-race **value** of stored energy (seconds per joule).

    ``V`` is a cost, so ``dV/dE < 0``; the costate is ``-dV/dE`` and is positive
    when extra energy is worth having.
    """
    lo = max(0.0, usable_energy_j - delta_j)
    hi = usable_energy_j + delta_j
    if hi <= lo:
        return float("nan")
    slope = (race_value.value(hi, laps_remaining) - race_value.value(lo, laps_remaining)) / (
        hi - lo
    )
    return -slope


def guidance(
    speed_mps: float,
    mass_kg: float,
    race_value,
    usable_energy_j: float,
    laps_remaining: int,
    eta_plus: float = 0.92,
    eta_minus: float = 0.92,
) -> GuidancePlan:
    """Assemble the costates and the resulting guidance cue."""
    lam_kin = kinetic_costate(speed_mps, mass_kg)
    lam_b = battery_costate(race_value, usable_energy_j, laps_remaining)
    state = CostateState(lam_kin, lam_b, eta_plus, eta_minus)
    cue = switching_cue(state)
    return GuidancePlan(
        cue=cue,
        lambda_kin=lam_kin,
        lambda_b=lam_b,
        ratio=state.ratio,
        max_deploy_w=0.0,
        guidance=_GUIDANCE[cue],
    )
