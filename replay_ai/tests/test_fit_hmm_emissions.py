import json

from scripts.fit_hmm_emissions import fit


def test_fit_uses_only_labelled_records(tmp_path):
    source = tmp_path / "labelled.jsonl"
    rows = [
        {"event": "a", "ers_mode": "Lderate", "speed_kmh": 300,
         "throttle_pct": 100, "brake": 0, "gap_s": 1},
        {"event": "a", "ers_mode": "Lderate", "speed_kmh": 301,
         "throttle_pct": 100, "brake": 0, "gap_s": 0.8},
        {"event": "a", "speed_kmh": 301, "throttle_pct": 100,
         "brake": 0, "gap_s": 0.7},
    ]
    source.write_text("\n".join(json.dumps(row) for row in rows))
    result = fit(source)
    assert result["Lderate"]["samples"] == 2
    assert "H" not in result
