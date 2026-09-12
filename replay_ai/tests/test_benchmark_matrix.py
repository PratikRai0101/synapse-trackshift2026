from scripts.benchmark_matrix import benchmark


def test_paired_benchmark_reuses_seeded_initial_conditions_and_reports_ci():
    report = benchmark([0, 1, 2], steps=20)
    assert report["schema"] == "paired-benchmark.v1"
    assert len(report["episodes"]) == 3 * 3 * 3 * 5
    summary = report["summaries"]["full:deplete:energy_stress"]
    assert summary["gap_s"]["n"] == 3
    assert summary["gap_s"]["ci95"] is not None
    assert summary["completion_rate"] == 1.0


def test_full_and_no_mpc_are_paired_per_seed_and_mode():
    report = benchmark([7], steps=20)
    episodes = {(row["controller"], row["rival_mode"], row["scenario"], row["seed"]): row
                for row in report["episodes"]}
    assert len(episodes) == 45
    assert all((controller, mode, scenario, 7) in episodes
               for scenario in ("nominal", "energy_stress", "thermal_stress")
               for controller in ("full", "no_mpc", "no_search", "no_soh", "no_spatial")
               for mode in ("conserve", "deplete", "match"))
