"""The Race Engineer: combines energy + overtake models into one live report.

Given the state around a focus driver, :class:`RaceEngineer` produces a
:class:`DecisionReport` containing the energy snapshot, the recommended
deployment mode, the overtake risk/reward assessment, and rule-compliance flags.
This is the object the replay UI renders.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .config import DEFAULT_CONFIG, ModelConfig
from .energy import (
    EnergyEstimator,
    EnergySnapshot,
    DeploymentAdvice,
    recommend_deployment_mode,
)
from .overtake import OvertakeAssessment, evaluate_overtake_window


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


@dataclass
class ComplianceFlag:
    label: str
    state: str   # "ok" | "warn" | "info"
    detail: str

    def as_dict(self) -> Dict[str, Any]:
        return {"label": self.label, "state": self.state, "detail": self.detail}


@dataclass
class DecisionReport:
    code: str
    energy: EnergySnapshot
    advice: DeploymentAdvice
    overtake: Optional[OvertakeAssessment]
    compliance: List[ComplianceFlag] = field(default_factory=list)
    summary: str = ""

    def as_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "energy": self.energy.as_dict(),
            "advice": self.advice.as_dict(),
            "overtake": self.overtake.as_dict() if self.overtake else None,
            "compliance": [c.as_dict() for c in self.compliance],
            "summary": self.summary,
        }


class RaceEngineer:
    """Builds decision reports from replay state."""

    def __init__(self, estimator: Optional[EnergyEstimator] = None,
                 config: Optional[ModelConfig] = None):
        self.config = config or DEFAULT_CONFIG
        self.estimator = estimator or EnergyEstimator(config=self.config)

    # -- energy -------------------------------------------------------------
    def estimate_energy(self, samples: List[Dict[str, Any]]) -> List[EnergySnapshot]:
        return self.estimator.estimate_series(samples)

    # -- compliance ---------------------------------------------------------
    @staticmethod
    def compliance_flags(
        soc: float,
        gap_ahead_s: Optional[float],
        drs: bool,
        track_status: Optional[str] = None,
        config: Optional[ModelConfig] = None,
    ) -> List[ComplianceFlag]:
        cfg = config or DEFAULT_CONFIG
        flags: List[ComplianceFlag] = []

        # Energy budget: the model treats SoC as a hard 0..100 budget.
        if soc <= 1.0:
            flags.append(ComplianceFlag("Energy budget", "warn", "Budget exhausted"))
        else:
            flags.append(ComplianceFlag("Energy budget", "ok", f"{soc:.0f}% within limit"))

        # DRS: only meaningful within the attack window of the car ahead.
        if drs:
            flags.append(ComplianceFlag("DRS", "info", "Active"))
        elif gap_ahead_s is not None and gap_ahead_s <= cfg.attack_max_gap_s:
            flags.append(ComplianceFlag("DRS", "info", "Eligible <1s"))
        else:
            flags.append(ComplianceFlag("DRS", "info", "Unavailable"))

        # Neutralisations forbid overtaking / deployment strategies.
        if track_status and str(track_status) in {"4", "5", "6", "7"}:
            flags.append(ComplianceFlag("Track status", "warn", "Neutralised - no overtaking"))

        return flags

    # -- full report --------------------------------------------------------
    def build_report(
        self,
        code: str,
        energy: EnergySnapshot,
        gap_ahead_s: Optional[float] = None,
        gap_behind_s: Optional[float] = None,
        speed_delta_kmh: float = 0.0,
        drs: bool = False,
        tyre_life: float = 0.0,
        laps_remaining: Optional[int] = None,
        position: Optional[int] = None,
        track_status: Optional[str] = None,
    ) -> DecisionReport:
        overtake: Optional[OvertakeAssessment] = None
        if gap_ahead_s is not None:
            overtake = evaluate_overtake_window(
                gap_ahead_s=gap_ahead_s,
                speed_delta_kmh=speed_delta_kmh,
                drs=drs,
                soc=energy.soc,
                tyre_life=tyre_life,
                laps_remaining=laps_remaining,
                position=position,
                config=self.config,
            )

        advice = recommend_deployment_mode(
            soc=energy.soc,
            gap_ahead_s=gap_ahead_s,
            laps_remaining=laps_remaining,
            drs=drs,
            tyre_life=tyre_life,
            overtake_score=overtake.score if overtake else 0.0,
            config=self.config,
        )

        compliance = self.compliance_flags(
            soc=energy.soc,
            gap_ahead_s=gap_ahead_s,
            drs=drs,
            track_status=track_status,
            config=self.config,
        )

        if overtake:
            summary = (
                f"{advice.mode}: {advice.reason}. "
                f"Overtake {overtake.verdict} "
                f"(reward {overtake.reward:.0f} / risk {overtake.risk:.0f})."
            )
        else:
            summary = f"{advice.mode}: {advice.reason}."

        return DecisionReport(
            code=code,
            energy=energy,
            advice=advice,
            overtake=overtake,
            compliance=compliance,
            summary=summary,
        )
