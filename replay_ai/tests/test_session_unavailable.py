"""Regression: an empty/future session must fail clearly, not crash the pool."""
from types import SimpleNamespace

import pytest

from src import f1_data
from src.f1_data import (
    SessionUnavailableError,
    _session_has_data,
    get_race_telemetry,
)


class _EmptySession:
    """Mirrors how FastF1 presents a session that has not happened yet."""

    def __init__(self):
        self.event = {"EventName": "Italian Grand Prix"}
        self.drivers = []

    def load(self, telemetry=True, weather=True):
        # FastF1 does not raise here for an unrun event; it just loads nothing.
        return self

    @property
    def laps(self):
        raise RuntimeError("The data you are trying to access has not been loaded yet")


class _UnloadedSession:
    event = {"EventName": "Italian Grand Prix"}

    @property
    def drivers(self):
        raise RuntimeError("not loaded")

    @property
    def laps(self):
        raise RuntimeError("not loaded")


def test_session_without_data_is_reported_as_unavailable():
    assert _session_has_data(_EmptySession()) is False
    assert _session_has_data(_UnloadedSession()) is False


def test_load_session_reports_a_future_event_and_falls_back_once(monkeypatch):
    offline_calls = []
    empty = _EmptySession()

    def fake_get_session(year, round_number, session_type):
        return empty

    monkeypatch.setattr(f1_data.fastf1, "get_session", fake_get_session)
    monkeypatch.setattr(
        f1_data.fastf1.Cache, "offline_mode",
        lambda flag: offline_calls.append(flag),
    )

    with pytest.raises(SessionUnavailableError) as error:
        f1_data.load_session(2026, 13, "R")

    # Cache-only was tried first, then the online retry, and offline mode was
    # always restored afterwards.
    assert offline_calls[0] is True
    assert offline_calls[-1] is False
    assert offline_calls.count(True) == 1
    assert offline_calls.count(False) >= 2
    assert "Italian Grand Prix" in str(error.value)
    assert "may not have taken place yet" in str(error.value)


def test_race_telemetry_rejects_a_session_with_no_drivers():
    with pytest.raises(SessionUnavailableError):
        get_race_telemetry(_EmptySession(), session_type="R")


def test_pool_size_never_drops_below_one(monkeypatch):
    """Guards the original Pool(processes=0) crash path."""
    captured = {}
    session = SimpleNamespace(
        drivers=["1"],
        get_driver=lambda num: {"Abbreviation": "AAA"},
        event={"EventName": "X"},
    )

    class _FakePool:
        def __init__(self, processes=None):
            captured["processes"] = processes

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def map(self, func, args):
            return []

    monkeypatch.setattr(f1_data, "Pool", _FakePool)
    monkeypatch.setattr(f1_data, "load_precomputed", lambda *a, **k: None, raising=False)

    try:
        get_race_telemetry(session, session_type="R")
    except Exception:
        pass  # downstream work may fail; only the pool size matters here

    assert captured["processes"] >= 1
