from scripts.benchmark_matrix import benchmark


def test_paired_benchmark_reuses_seeded_initial_conditions_and_reports_ci():
    report = benchmark([0, 1, 2], steps=20)
    assert report["schema"] == "paired-benchmark.v1"
    assert len(report["episodes"]) == 3 * 3 * 2
    summary = report["summaries"]["full:deplete"]
    assert summary["gap_s"]["n"] == 3
    assert summary["gap_s"]["ci95"] is not None
    assert summary["completion_rate"] == 1.0


def test_full_and_no_mpc_are_paired_per_seed_and_mode():
    report = benchmark([7], steps=20)
    episodes = {(row["controller"], row["rival_mode"], row["seed"]): row
                for row in report["episodes"]}
    assert len(episodes) == 6
    assert all(("full", mode, 7) in episodes and ("no_mpc", mode, 7) in episodes
               for mode in ("conserve", "deplete", "match"))
