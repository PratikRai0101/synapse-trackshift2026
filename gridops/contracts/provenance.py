"""Provenance vocabulary.

A value must be labelled with where it came from. ``None`` means unknown or
unavailable -- never zero. Synthetic values are allowed; pretending they were
measured is not.
"""

from __future__ import annotations

from enum import Enum


class Provenance(str, Enum):
    """Source identity carried by every externally exchanged value."""

    PUBLIC_OBSERVATION = "public_observation"
    DERIVED_OBSERVATION = "derived_observation"
    SIMULATED_MEASUREMENT = "simulated_measurement"
    MODEL_ESTIMATE = "model_estimate"
    SYNTHETIC_PARAMETER = "synthetic_parameter"
    VERIFIED_RULE = "verified_rule"
    UNKNOWN = "unknown"

    def is_measured(self) -> bool:
        return self in {
            Provenance.PUBLIC_OBSERVATION,
            Provenance.DERIVED_OBSERVATION,
            Provenance.SIMULATED_MEASUREMENT,
        }

    def is_synthetic(self) -> bool:
        return self is Provenance.SYNTHETIC_PARAMETER
