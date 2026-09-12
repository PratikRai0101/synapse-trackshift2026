import json

from scripts.generate_lap_training import generate, main


def test_generated_lap_records_contain_hidden_energy_truth():
    rows = list(generate(3, 4, 21))
    assert len(rows) == 12
    assert all(row["energy_source"] == "simulator-truth" for row in rows)
    assert all(row["battery_deployed"] >= 0 for row in rows)
    assert {row["split"] for row in rows} <= {"train", "validation", "test"}


def test_cli_writes_event_partitioned_dataset(tmp_path, monkeypatch):
    output = tmp_path / "laps"
    monkeypatch.setattr("sys.argv", ["generate_lap_training", "--events", "20",
                                      "--laps-per-event", "3", "--output", str(output)])
    main()
    manifest = json.loads((output / "manifest.json").read_text())
    assert sum(manifest["counts"].values()) == 60
