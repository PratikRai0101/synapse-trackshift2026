from scripts.model_mismatch import report


def test_model_mismatch_report_covers_modes_and_stress_conditions():
    result = report([0, 1], steps=20)
    assert result["schema"] == "model-mismatch.v1"
    assert len(result["episodes"]) == 2 * 3 * 3
    assert 0.0 <= result["metrics"]["decision_alignment"] <= 1.0
    assert result["metrics"]["speed_target_mae_kmh"] >= 0.0
    assert result["metrics"]["resistance_mismatch"] >= 0.0
    assert result["limitations"]
