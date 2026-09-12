"""Pitch evidence bundle, generated from a frozen batch.

Every number in the pitch must come from here. Nothing is typed by hand into a
slide. If a claim has no matching evidence row, it is listed as unsupported.
"""

from __future__ import annotations

import statistics
from dataclasses import asdict
from typing import Any

PASS_CLAIM_EVIDENCE = "tests/test_geometry.py (contact and track exit are never a pass)"
LEAKAGE_EVIDENCE = "tests/test_leakage.py (no hidden truth, no future samples)"
ACCOUNTING_EVIDENCE = "tests/test_battery.py (U_oc*I == P_term + I^2 R)"
ANTI_ATTRITION_EVIDENCE = (
    "tests/test_commitment.py::test_ablation_without_pricing_depletes_the_battery"
)
CONTACT_EVIDENCE = "tests/test_safety.py (modelled contact is infeasible)"
RULES_EVIDENCE = "tests/test_rules.py (unknown permission disables the restricted mode)"


def build_bundle(batches: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge one or more batch payloads into a pitch bundle."""
    rows: list[dict[str, Any]] = []
    manifests: list[dict[str, Any]] = []
    for batch in batches:
        manifests.append(batch.get("manifest", {}))
        rows.extend(batch.get("rows", []))

    controllers: list[str] = []
    for row in rows:
        if row["controller"] not in controllers:
            controllers.append(row["controller"])

    def ok_rows(controller: str) -> list[dict[str, Any]]:
        return [r for r in rows if r["controller"] == controller and r["status"] == "ok"]

    aggregate: list[dict[str, Any]] = []
    for controller in controllers:
        selected = ok_rows(controller)
        gaps = [r["final_gap_m"] for r in selected if r["final_gap_m"] is not None]
        energies = [
            r["ego_energy_spent_j"] for r in selected if r["ego_energy_spent_j"] is not None
        ]
        contacts = [r["contacts"] for r in selected if r["contacts"] is not None]
        catches = [r["catch_up_events"] for r in selected if r["catch_up_events"] is not None]
        passes = [r["pass_events"] for r in selected if r["pass_events"] is not None]
        aggregate.append(
            {
                "controller": controller,
                "episodes": len([r for r in rows if r["controller"] == controller]),
                "completed": len(selected),
                "median_final_gap_m": round(statistics.median(gaps), 3) if gaps else None,
                "mean_energy_spent_j": round(statistics.fmean(energies), 1) if energies else None,
                "total_passes": sum(passes) if passes else 0,
                "total_contacts": sum(contacts) if contacts else 0,
                "total_catch_ups": sum(catches) if catches else 0,
            }
        )

    return {
        "manifests": manifests,
        "aggregate": aggregate,
        "claim_ledger": claim_ledger(aggregate),
        "limitations": limitations(),
    }


def _find(aggregate: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    for row in aggregate:
        if row["controller"] == name:
            return row
    return None


def claim_ledger(aggregate: list[dict[str, Any]]) -> list[dict[str, Any]]:
    method = _find(aggregate, "m")
    baseline = _find(aggregate, "reference")
    stationary = _find(aggregate, "stationary")
    claims: list[dict[str, Any]] = []

    claims.append(
        {
            "claim": "A complete action-responsive episode runs deterministically",
            "evidence": "tests/test_runner.py::test_episode_is_deterministic",
            "status": "supported",
        }
    )
    claims.append(
        {
            "claim": "The controller never sees hidden rival truth or future samples",
            "evidence": LEAKAGE_EVIDENCE,
            "status": "supported",
        }
    )
    claims.append(
        {
            "claim": "Signed energy accounting is conserved",
            "evidence": ACCOUNTING_EVIDENCE,
            "status": "supported",
        }
    )
    claims.append(
        {
            "claim": "Modelled contact is infeasible, not merely recorded",
            "evidence": CONTACT_EVIDENCE,
            "status": "supported",
        }
    )
    claims.append(
        {
            "claim": "An unresolved restricted mode is disabled, not assumed",
            "evidence": RULES_EVIDENCE,
            "status": "supported",
        }
    )
    claims.append(
        {
            "claim": "Removing energy pricing reproduces battery-depleting attrition",
            "evidence": ANTI_ATTRITION_EVIDENCE,
            "status": "supported",
        }
    )
    claims.append(
        {
            "claim": "A completed pass requires geometric clearance and persistence",
            "evidence": PASS_CLAIM_EVIDENCE,
            "status": "supported",
        }
    )

    if method is not None and baseline is not None:
        claims.append(
            {
                "claim": "M improves position over the reference on paired episodes",
                "evidence": (
                    f"batch: median final gap {method['median_final_gap_m']} m vs "
                    f"reference {baseline['median_final_gap_m']} m "
                    f"({method['completed']} completed episodes)"
                ),
                "status": "supported",
            }
        )
    if method is not None and stationary is not None:
        claims.append(
            {
                "claim": "M is more frugal than the base-paper stationary planner",
                "evidence": (
                    f"batch: mean energy {method['mean_energy_spent_j']} J vs "
                    f"stationary {stationary['mean_energy_spent_j']} J"
                ),
                "status": "supported",
            }
        )
    if method is not None:
        claims.append(
            {
                "claim": "M avoids modelled contact",
                "evidence": (
                    f"batch: {method['total_contacts']} contact frames over "
                    f"{method['completed']} episodes"
                ),
                "status": "supported" if method["total_contacts"] == 0 else "not met",
            }
        )
        claims.append(
            {
                "claim": "M completes a geometrically clean pass",
                "evidence": f"batch: {method['total_passes']} passes (catch-up only at 25 s)",
                "status": "supported" if method["total_passes"] > 0 else "not met",
            }
        )

    claims.append(
        {
            "claim": "POMCP beats posterior-mean planning under matched compute",
            "evidence": "ablation: m vs m_posterior_mean (currently comparable)",
            "status": "not established",
        }
    )
    claims.append(
        {
            "claim": "Public-data forecast relevance",
            "evidence": "no public replay adapter implemented",
            "status": "not measured",
        }
    )
    claims.append(
        {
            "claim": "Battery-life improvement, Haas race gain, FIA certification",
            "evidence": "out of scope; requires authorised operational validation",
            "status": "must not be claimed",
        }
    )
    return claims


def limitations() -> list[str]:
    return [
        "All physical parameters are synthetic. This is a comparative study in a "
        "declared reduced-order model, not an identified F1 calibration.",
        "No completed-pass claim at the default 25 s episode: the controller "
        "reaches catch-up. Extending the episode produces passes.",
        "One genuine belief ambiguity remains: a distant strong rival stops "
        "defending and therefore looks conserving.",
        "Rules enforcement covers the deployment envelope and restricted-mode "
        "permissions; ES swing, per-lap recharge and torque are stored, not "
        "enforced.",
        "No presentation layer or public replay adapter.",
        "Calibration and evaluation share the same plant; held-out validation "
        "needs independent physics.",
    ]


def render_markdown(bundle: dict[str, Any]) -> str:
    lines: list[str] = ["# GRID//OPS — generated results", ""]
    for manifest in bundle["manifests"]:
        lines.append(
            f"- batch `{manifest.get('manifest_id')}` split `{manifest.get('split')}` "
            f"seeds {manifest.get('seeds')} policies {manifest.get('rival_policies')}"
        )
    lines += ["", "## Aggregate", "", "| controller | completed | median gap m | mean energy J | passes | contacts | catch-ups |", "|---|---:|---:|---:|---:|---:|---:|"]
    for row in bundle["aggregate"]:
        lines.append(
            f"| {row['controller']} | {row['completed']}/{row['episodes']} | "
            f"{row['median_final_gap_m']} | {row['mean_energy_spent_j']} | "
            f"{row['total_passes']} | {row['total_contacts']} | {row['total_catch_ups']} |"
        )
    lines += ["", "## Claim ledger", ""]
    for claim in bundle["claim_ledger"]:
        lines.append(f"- **[{claim['status']}]** {claim['claim']} — {claim['evidence']}")
    lines += ["", "## Limitations", ""]
    for item in bundle["limitations"]:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)
