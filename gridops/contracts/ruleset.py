"""Event rules: versioned permissions and a deployment envelope.

Only explicitly represented and verified predicates may be checked. A permission
that is UNKNOWN disables the affected restricted mode rather than being assumed
granted. This is not a certification of real-world compliance.

The envelope table below restates the reviewed FIA 2026 Technical Section C
paragraphs (Issue 20, 5 August 2026) as published in
``work/f1-haas-data-constraints.md``. Event supplements remain unresolved, so
event-specific fields stay None and restricted modes stay disabled.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class Permission(str, Enum):
    GRANTED = "granted"
    DENIED = "denied"
    UNKNOWN = "unknown"


REASON_ELIGIBILITY_UNKNOWN = "ELIGIBILITY_UNKNOWN"
REASON_ELIGIBILITY_DENIED = "ELIGIBILITY_DENIED"


def normal_power_limit_kw(speed_kmh: float) -> float:
    """C5.2.7 / C5.2.8(i-ii): normal deployment envelope, kW."""
    if speed_kmh < 340.0:
        return min(350.0, 1800.0 - 5.0 * speed_kmh)
    if speed_kmh < 345.0:
        return max(0.0, 6900.0 - 20.0 * speed_kmh)
    return 0.0


def overtake_power_limit_kw(speed_kmh: float) -> float:
    """Overtake envelope: 350 kW retained through 337.5 km/h, zero at 355."""
    if speed_kmh < 355.0:
        return min(350.0, 7100.0 - 20.0 * speed_kmh)
    return 0.0


@dataclass(frozen=True)
class Ruleset:
    ruleset_id: str
    edition: str
    verified: bool
    mgu_k_absolute_limit_w: float = 350_000.0
    es_swing_limit_j: float = 4_000_000.0
    lap_recharge_limit_j: float = 8_500_000.0
    mgu_k_torque_limit_nm: float = 500.0
    overtake: Permission = Permission.UNKNOWN
    active_aero: Permission = Permission.UNKNOWN
    detection_gap_s: float | None = None
    detection_line_m: float | None = None
    activation_line_m: float | None = None
    provenance: str = "verified_rule"

    def deployment_limit_w(
        self, speed_mps: float, overtake_requested: bool = False
    ) -> tuple[float, str | None]:
        """Return ``(limit_w, fallback_reason)``.

        Requesting overtake when it is not granted falls back to the normal
        envelope and reports why. It never silently uses the restricted envelope.
        """
        speed_kmh = speed_mps * 3.6
        reason: str | None = None
        if overtake_requested:
            if self.overtake is Permission.GRANTED:
                limit_kw = overtake_power_limit_kw(speed_kmh)
            else:
                limit_kw = normal_power_limit_kw(speed_kmh)
                reason = (
                    REASON_ELIGIBILITY_UNKNOWN
                    if self.overtake is Permission.UNKNOWN
                    else REASON_ELIGIBILITY_DENIED
                )
        else:
            limit_kw = normal_power_limit_kw(speed_kmh)
        return min(limit_kw * 1000.0, self.mgu_k_absolute_limit_w), reason

    def mode_available(self, mode: str) -> tuple[bool, str | None]:
        """A restricted mode is available only when explicitly granted."""
        permission = {
            "overtake": self.overtake,
            "active_aero": self.active_aero,
        }.get(mode)
        if permission is None:
            return False, "UNKNOWN_MODE"
        if permission is Permission.GRANTED:
            return True, None
        return False, (
            REASON_ELIGIBILITY_UNKNOWN
            if permission is Permission.UNKNOWN
            else REASON_ELIGIBILITY_DENIED
        )

    def to_dict(self) -> dict:
        data = {k: v for k, v in self.__dict__.items()}
        data["overtake"] = self.overtake.value
        data["active_aero"] = self.active_aero.value
        return data


def default_ruleset() -> Ruleset:
    """Demonstrator ruleset: known limits, unresolved event permissions."""
    return Ruleset(
        ruleset_id="fia-2026-unresolved-event",
        edition="Technical C Issue 20 / Sporting B Issue 08, 2026-08-05",
        verified=False,
        overtake=Permission.UNKNOWN,
        active_aero=Permission.UNKNOWN,
    )


def ruleset_from_dict(data: dict) -> Ruleset:
    payload = dict(data)
    payload["overtake"] = Permission(payload.get("overtake", "unknown"))
    payload["active_aero"] = Permission(payload.get("active_aero", "unknown"))
    known = {f for f in Ruleset.__dataclass_fields__}
    return Ruleset(**{k: v for k, v in payload.items() if k in known})


def load_ruleset(path: str | Path) -> Ruleset:
    return ruleset_from_dict(json.loads(Path(path).read_text()))
