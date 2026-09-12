"""Presentation: recorded runs render to a self-contained page."""

from __future__ import annotations

from gridops.presentation.html import render_batch, render_page, render_run, write_report


def _run(label: str = "m vs conserving") -> dict:
    return {
        "label": label,
        "summary": {
            "run_mode": "simulation",
            "final_gap_m": -0.56,
            "ego_energy_spent_j": 426_000.0,
            "pass_events": 0,
            "catch_up_events": 57,
            "contacts": 0,
            "decisions": 2,
        },
        "decisions": [
            {
                "time_s": 0.0,
                "family": "probe",
                "status": "RECOMMEND",
                "reason_codes": ["AMBIGUOUS_CAPABILITY"],
                "p_k_dc_w": 50_000.0,
                "gap_m": 8.0,
                "belief": {"strong_rival_mass": 0.5},
            },
            {
                "time_s": 1.0,
                "family": "reference",
                "status": "RETAIN_REFERENCE",
                "reason_codes": ["NO_IMPROVEMENT"],
                "p_k_dc_w": 0.0,
                "gap_m": 7.4,
                "belief": {"strong_rival_mass": 0.6},
            },
        ],
        "trace": [
            {"t": 0.0, "gap": 8.0, "ego_v": 80.0, "rival_v": 80.0, "p_k_w": 50_000.0,
             "energy_j": 2_700_000.0, "tyre_temp_k": 360.0, "outcome": "none"},
            {"t": 0.2, "gap": 7.8, "ego_v": 81.0, "rival_v": 80.0, "p_k_w": 50_000.0,
             "energy_j": 2_690_000.0, "tyre_temp_k": 362.0, "outcome": "none"},
        ],
    }


def test_run_renders_charts_and_a_table() -> None:
    html = render_run(_run())
    assert "<svg" in html
    assert "Gap (rival" in html
    assert "AMBIGUOUS_CAPABILITY" in html
    assert "strong mass" in html


def test_missing_trace_says_so_rather_than_inventing() -> None:
    run = _run()
    run["trace"] = []
    html = render_run(run)
    assert "No trace recorded" in html


def test_page_marks_simulated_and_unavailable() -> None:
    html = render_page([_run()])
    assert "not recompute a recommendation" in html
    assert "simulated" in html


def test_batch_section_includes_claim_ledger() -> None:
    bundle = {
        "aggregate_by_split": {
            "development": [
                {
                    "controller": "m", "episodes": 10, "completed": 10,
                    "median_final_gap_m": 8.1, "mean_energy_spent_j": 1_600_000.0,
                    "total_passes": 0, "total_contacts": 0, "total_catch_ups": 50,
                }
            ]
        },
        "claim_ledger": [
            {"claim": "energy is conserved", "evidence": "test_battery", "status": "supported"}
        ],
        "split_claims": [],
        "limitations": ["all parameters are synthetic"],
    }
    html = render_batch(bundle)
    assert "Aggregate — development split" in html
    assert "energy is conserved" in html
    assert "all parameters are synthetic" in html


def test_write_report_creates_a_file(tmp_path) -> None:
    path = tmp_path / "report.html"
    write_report([_run()], None, str(path))
    text = path.read_text()
    assert text.startswith("<!doctype html>")
    assert "GRID//OPS" in text
