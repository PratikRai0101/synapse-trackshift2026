import pytest

from src.intelligence.telemetry_adapter import PublicTelemetryAdapter


def test_adapter_emits_causal_public_contract_and_aero_proxy():
    adapter = PublicTelemetryAdapter()
    frame = {
        "drivers": {
            "EGO": {"lap": 4, "speed": 300},
            "RIV": {"lap": 4, "speed": 305, "throttle": 100,
                    "brake": 0, "drs": 12, "tyre_life": 7},
        },
        "gap": 0.72,
    }
    record = adapter.from_frame(frame, "EGO", "RIV", timestamp_s=12.0)
    assert record.available_at_s == 12.0
    assert record.active_aero == 1.0
    assert record.gap_s == 0.72
    assert adapter.to_hmm_observation(record).speed_kmh == 305


def test_adapter_rejects_future_availability_ordering():
    with pytest.raises(ValueError):
        from src.intelligence.telemetry_adapter import PublicTelemetryFrame
        PublicTelemetryFrame(10, 9, "E", None, 1, 0, 0, 0, 0, None, 0)
