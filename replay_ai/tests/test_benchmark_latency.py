from scripts.benchmark_latency import measure, pomcp_scaling


def test_every_architecture_block_is_timed_and_ordered():
    report = measure(20)
    assert report["schema"] == "latency-report.v1"
    expected = {
        "1_telemetry_features",
        "2_hmm_40_state_update",
        "3_level3_lap_dp",
        "4_level4_season_dp",
        "2_level2_full",
        "1_level1_mpc",
        "0_vehicle_plant_step",
        "END_TO_END_observe",
        "C_counterfactual_fork",
    }
    assert expected.issubset(report["blocks"])
    for stats in report["blocks"].values():
        assert stats["n"] > 0
        # Percentiles must be ordered for the budget comparison to mean anything.
        assert 0.0 <= stats["p50_ms"] <= stats["p95_ms"] <= stats["p99_ms"] <= stats["max_ms"]

    # The design budgets are carried with the report so regressions are visible.
    assert report["design_budgets_ms"]["1_level1_mpc"] == 10.0

    # Document where the tactical latency actually goes: the particle search
    # dominates, while the SOCP projection is close to free.
    full = report["blocks"]["2_level2_full"]["p50_ms"]
    heuristic = report["blocks"]["2_level2_heuristic_only"]["p50_ms"]
    socp = report["blocks"]["2b_socp_spatial_only"]["p50_ms"]
    assert full > heuristic + socp


def test_pomcp_cost_grows_with_the_search_budget():
    rows = pomcp_scaling()
    assert len(rows) == 4
    assert rows[0]["p50_ms"] < rows[-1]["p50_ms"]
