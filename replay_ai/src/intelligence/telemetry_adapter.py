"""Leakage-safe public telemetry contract for the AI replay copy.

The adapter intentionally accepts already-public replay frames. It never reads
future samples and records when each observation became available, allowing
training and backtests to enforce causal ordering.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Mapping, Optional


@dataclass(frozen=True)
class PublicTelemetryFrame:
    timestamp_s: float
    available_at_s: float
    driver: str
    rival: Optional[str]
    lap: int
    sector: int
    speed_kmh: float
    throttle_pct: float
    brake: float
    gap_s: Optional[float]
    active_aero: float
    tyre_life: float = 0.0
    source: str = "replay"

    def __post_init__(self) -> None:
        if self.available_at_s < self.timestamp_s:
            raise ValueError("available_at_s cannot precede timestamp_s")
        if not 0.0 <= self.active_aero <= 1.0:
            raise ValueError("active_aero must be normalized to [0, 1]")

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PublicTelemetryAdapter:
    """Convert a replay frame into one causal ego/rival observation."""

    def __init__(self, source: str = "fastf1-replay") -> None:
        self.source = source

    @staticmethod
    def _number(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def from_frame(
        self,
        frame: Mapping[str, Any],
        driver: str,
        rival: Optional[str],
        timestamp_s: float,
        available_at_s: Optional[float] = None,
    ) -> PublicTelemetryFrame:
        """Extract only fields that existed in the current replay frame."""
        drivers = frame.get("drivers", {})
        ego = drivers.get(driver, {}) or {}
        opponent = drivers.get(rival, {}) if rival else {}
        opponent = opponent or {}
        gap = frame.get("gap_s")
        if gap is None:
            gap = opponent.get("gap_s", frame.get("gap"))
        drs = opponent.get("drs", 0)
        aero = opponent.get("active_aero")
        if aero is None:
            aero = 1.0 if drs in (8, 10, 12, 14) else 0.0
        return PublicTelemetryFrame(
            timestamp_s=float(timestamp_s),
            available_at_s=float(timestamp_s if available_at_s is None else available_at_s),
            driver=driver,
            rival=rival,
            lap=int(opponent.get("lap", ego.get("lap", 0)) or 0),
            sector=int(opponent.get("sector", 0) or 0),
            speed_kmh=self._number(opponent.get("speed")),
            throttle_pct=self._number(opponent.get("throttle")),
            brake=self._number(opponent.get("brake")),
            gap_s=None if gap is None else self._number(gap),
            active_aero=max(0.0, min(1.0, self._number(aero))),
            tyre_life=self._number(opponent.get("tyre_life")),
            source=self.source,
        )

    def to_hmm_observation(self, frame: PublicTelemetryFrame):
        """Convert the contract to the hierarchical model's input type."""
        from .hierarchical import RivalTelemetry
        return RivalTelemetry(
            speed_kmh=frame.speed_kmh,
            throttle_pct=frame.throttle_pct,
            brake=frame.brake,
            gap_s=frame.gap_s or 0.0,
            active_aero=frame.active_aero,
            sector=frame.sector,
            lap=frame.lap,
            tyre_life=frame.tyre_life,
        )
