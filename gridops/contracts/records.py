"""Versioned external records.

These are the contract between the engine and any client (CLI, replay
application, notebook). ``None`` means unknown/unavailable, never zero.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .provenance import Provenance

SCHEMA_VERSION = "gridops.record.v1"


@dataclass(frozen=True)
class RecordHeader:
    run_id: str
    record_id: str
    time_s: float
    source: str
    provenance: Provenance
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "record_id": self.record_id,
            "time_s": self.time_s,
            "source": self.source,
            "provenance": self.provenance.value,
        }


@dataclass
class ObservationFrame:
    """A causal observation. Only usable once ``available_at_s`` has passed."""

    header: RecordHeader
    sampled_at_s: float
    available_at_s: float
    channels: dict[str, float | None]
    units: dict[str, str] = field(default_factory=dict)
    valid: dict[str, bool] = field(default_factory=dict)

    def visible_at(self, t_s: float) -> bool:
        return self.available_at_s <= t_s

    def get(self, channel: str) -> float | None:
        if not self.valid.get(channel, True):
            return None
        return self.channels.get(channel)

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.header.to_dict(),
            "sampled_at_s": self.sampled_at_s,
            "available_at_s": self.available_at_s,
            "channels": self.channels,
            "units": self.units,
            "valid": self.valid,
        }


class DecisionStatus(str):
    RECOMMEND = "RECOMMEND"
    RETAIN_REFERENCE = "RETAIN_REFERENCE"
    FALLBACK = "FALLBACK"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass
class DecisionInput:
    """Permitted decision input.

    By construction this carries only public/own-car fields. Hidden rival
    battery state, policy label and future samples must never be added here.
    """

    time_s: float
    run_mode: str
    ego_progress_m: float
    ego_speed_mps: float
    ego_usable_energy_j: float
    ego_battery_temp_k: float
    gap_m: float
    laps_remaining: int
    opponent_speed_mps: float | None = None
    observations: list[ObservationFrame] = field(default_factory=list)
    versions: dict[str, str] = field(default_factory=dict)

    def visible_observations(self) -> list[ObservationFrame]:
        return [frame for frame in self.observations if frame.visible_at(self.time_s)]


@dataclass
class Recommendation:
    """The decision-module output contract (subset of PRD section 5)."""

    status: str
    action_family: str
    reason_codes: list[str]
    plan_p_k_dc_w: list[float] = field(default_factory=list)
    plan_time_s: list[float] = field(default_factory=list)
    reference_id: str = "reference"
    alternatives: list[dict[str, Any]] = field(default_factory=list)
    belief_summary: dict[str, Any] = field(default_factory=dict)
    resource_forecast: dict[str, Any] = field(default_factory=dict)
    constraint_report: dict[str, Any] = field(default_factory=dict)
    runtime: dict[str, float] = field(default_factory=dict)
    trace: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "action_family": self.action_family,
            "reason_codes": list(self.reason_codes),
            "plan_p_k_dc_w": list(self.plan_p_k_dc_w),
            "plan_time_s": list(self.plan_time_s),
            "reference_id": self.reference_id,
            "alternatives": [dict(a) for a in self.alternatives],
            "belief_summary": dict(self.belief_summary),
            "resource_forecast": dict(self.resource_forecast),
            "constraint_report": dict(self.constraint_report),
            "runtime": dict(self.runtime),
            "trace": dict(self.trace),
        }
