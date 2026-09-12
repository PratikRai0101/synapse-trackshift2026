"""Canonical SI units and conversions.

Every internal quantity is SI. Display conversions live here so that no module
invents its own factor. If a value has no declared unit it is a bug.
"""

from __future__ import annotations

KELVIN_OFFSET = 273.15
AH_TO_COULOMB = 3600.0
KMH_TO_MPS = 1.0 / 3.6
MPS_TO_KMH = 3.6
J_PER_MJ = 1_000_000.0
J_PER_KWH = 3_600_000.0
GRAVITY = 9.80665


def c_to_k(celsius: float) -> float:
    return celsius + KELVIN_OFFSET


def k_to_c(kelvin: float) -> float:
    return kelvin - KELVIN_OFFSET


def kmh_to_mps(kmh: float) -> float:
    return kmh * KMH_TO_MPS


def mps_to_kmh(mps: float) -> float:
    return mps * MPS_TO_KMH


def ah_to_c(ampere_hours: float) -> float:
    return ampere_hours * AH_TO_COULOMB


def c_to_ah(coulombs: float) -> float:
    return coulombs / AH_TO_COULOMB


def mj_to_j(megajoules: float) -> float:
    return megajoules * J_PER_MJ


def j_to_mj(joules: float) -> float:
    return joules / J_PER_MJ
