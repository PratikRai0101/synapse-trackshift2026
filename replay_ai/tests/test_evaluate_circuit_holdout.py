import json

from scripts.evaluate_circuit_holdout import evaluate


def test_leave_one_circuit_out_evaluation_prevents_circuit_leakage(tmp_path):
    rows = []
    for circuit, baseline in (("alpha", 90.0), ("beta", 100.0), ("gamma", 110.0)):
        for index in range(2):
            rows.append({
                "circuit": circuit,
                "lap_time_s": baseline + index,
                "battery_deployed": float(index),
                "track_baseline_s": baseline,
            })
    (tmp_path / "dataset.jsonl").write_text("\n".join(json.dumps(row) for row in rows))
    result = evaluate(tmp_path)
    assert result["schema"] == "circuit-holdout-evaluation.v1"
    assert result["circuit_count"] == 3
    assert result["pooled_samples"] == 6
    assert all(item["status"] == "evaluated" for item in result["reports"].values())
