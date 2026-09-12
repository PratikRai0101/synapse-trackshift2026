import json

from scripts.fit_hmm_emissions import fit


def test_fit_uses_only_labelled_records(tmp_path):
    source = tmp_path / "labelled.jsonl"
    rows = [
        {"event": "a", "ers_mode": "Lderate", "speed_kmh": 300,
         "throttle_pct": 100, "brake": 0, "gap_s": 1},
        {"event": "a", "ers_mode": "Lderate", "speed_kmh": 301,
         "throttle_pct": 100, "brake": 0, "gap_s": 0.8},
        # Unlabelled: must be ignored, not silently counted as some mode.
        {"event": "a", "speed_kmh": 301, "throttle_pct": 100,
         "brake": 0, "gap_s": 0.7},
    ]
    source.write_text("\n".join(json.dumps(row) for row in rows))
    means, sigma, counts = fit(source)
    assert counts == {"Lderate": 2}
    assert "H" not in means
    assert set(sigma) == {"dgap", "throttle_clip", "brake_delta"}
