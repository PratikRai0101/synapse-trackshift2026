"""DRS zone ranges broadcast to downstream consumers (the 3D viewer).

The viewer holds the outer edge polyline already, so only the index range is
sent. These tests pin the sanitising behaviour: reversed zones are dropped,
out-of-range ends are clamped, and malformed input must not break a broadcast.
"""

from src.interfaces.race_replay import F1RaceReplayWindow


class _FakeWindow:
    def __init__(self, outer_len, zones):
        self.x_outer = [0.0] * outer_len
        self.drs_zones = zones


def _zone(start, end):
    return {"start": {"index": start}, "end": {"index": end}}


def test_ranges_are_forwarded_unchanged_when_valid():
    window = _FakeWindow(100, [_zone(10, 40)])
    assert F1RaceReplayWindow._drs_zone_ranges(window) == [{"start": 10, "end": 40}]


def test_end_index_is_clamped_to_the_outer_edge():
    window = _FakeWindow(100, [_zone(95, 200)])
    assert F1RaceReplayWindow._drs_zone_ranges(window) == [{"start": 95, "end": 99}]


def test_reversed_and_negative_zones_are_dropped():
    window = _FakeWindow(100, [_zone(60, 55), _zone(-1, 10)])
    assert F1RaceReplayWindow._drs_zone_ranges(window) == []


def test_missing_or_malformed_zones_return_empty():
    assert F1RaceReplayWindow._drs_zone_ranges(_FakeWindow(10, None)) == []
    assert F1RaceReplayWindow._drs_zone_ranges(_FakeWindow(10, [{"start": {}, "end": {}}])) == []
