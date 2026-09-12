"""Tests for circuit map caching helpers (no network / rendering)."""

import os

from src.gui import track_map


def test_track_map_path_format():
    p = track_map.track_map_path(2026, 13)
    assert p.endswith(os.path.join("computed_data", "track_maps", "2026_13.png"))


def test_track_map_path_zero_pads_round():
    assert track_map.track_map_path(2026, 3).endswith("2026_03.png")


def test_cached_track_map_missing_returns_none():
    # Round 999 will never have been rendered.
    assert track_map.cached_track_map(2026, 999) is None


def test_cached_track_map_returns_existing(monkeypatch, tmp_path):
    target = track_map.track_map_path(2026, 998)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w") as f:
        f.write("x")
    try:
        assert track_map.cached_track_map(2026, 998) == target
    finally:
        os.remove(target)


def test_render_track_map_falls_back_to_previous_year(monkeypatch):
    calls = []

    def fake_render(year, rnd, stype, out_path, size):
        calls.append((year, rnd, stype))
        if year == 2026:
            raise RuntimeError("no telemetry")
        return out_path

    monkeypatch.setattr(track_map, "_render_with_session", fake_render)
    monkeypatch.setattr(track_map, "_find_previous_year_round", lambda y, r: (2025, 4))

    path = track_map.render_track_map(2026, 14)
    assert path
    assert any(c[0] == 2025 and c[1] == 4 for c in calls)


def test_render_track_map_no_fallback_returns_none(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("no telemetry")

    monkeypatch.setattr(track_map, "_render_with_session", boom)
    monkeypatch.setattr(track_map, "_find_previous_year_round", lambda y, r: (2025, 4))
    assert track_map.render_track_map(2026, 14, allow_fallback=False) is None
