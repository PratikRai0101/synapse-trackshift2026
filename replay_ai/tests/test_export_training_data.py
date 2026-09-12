import io
import json

from scripts.export_training_data import export_frames


def test_exporter_writes_only_available_public_frames():
    frames = [{
        "t": 1.0, "lap": 1,
        "drivers": {
            "EGO": {"speed": 300},
            "RIV": {"speed": 305, "throttle": 100, "brake": 0, "drs": 12},
        },
    }]
    output = io.StringIO()
    assert export_frames(frames, "EGO", "RIV", output, stride=1) == 1
    record = json.loads(output.getvalue())
    assert record["schema"] == "public-telemetry.v1"
    assert record["available_at_s"] == record["timestamp_s"]
