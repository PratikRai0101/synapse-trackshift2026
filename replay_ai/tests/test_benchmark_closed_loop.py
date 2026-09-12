from scripts.benchmark_closed_loop import benchmark, run_episode
from src.intelligence.closed_loop import HiddenRivalMode


def test_benchmark_covers_all_hidden_rival_modes():
    report = benchmark(steps=12)
    assert report["completion_rate"] == 1.0
    assert {episode["rival_mode"] for episode in report["episodes"]} == {
        mode.value for mode in HiddenRivalMode
    }
    assert all(episode["steps"] == 12 for episode in report["episodes"])


def test_episode_reports_command_counts_and_physical_metrics():
    result = run_episode(HiddenRivalMode.MATCH, 8)
    assert result["completed"]
    assert result["commands"]
    assert result["final_ego_energy"] >= 0.0
    assert result["final_gap_s"] >= 0.0
