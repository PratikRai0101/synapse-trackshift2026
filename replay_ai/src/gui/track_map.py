"""Render and cache circuit-layout thumbnails from FastF1 telemetry.

The carousel needs a picture of each circuit. FastF1 exposes no track image,
but the fastest lap's X/Y telemetry traces the layout precisely, so we render
that to a transparent PNG and cache it under ``computed_data/track_maps``.

Rendering downloads/loads a session, so callers should run
:func:`render_track_map` on a background thread. Returns ``None`` when the
session is unavailable (e.g. offline), letting the UI fall back to a
placeholder.
"""

from __future__ import annotations

import os
from typing import Optional, Tuple

TRACK_MAP_DIR = os.path.join("computed_data", "track_maps")


def track_map_path(year: int, round_number: int) -> str:
    return os.path.join(TRACK_MAP_DIR, f"{int(year)}_{int(round_number):02d}.png")


def cached_track_map(year: int, round_number: int) -> Optional[str]:
    path = track_map_path(year, round_number)
    return path if os.path.exists(path) else None


def render_track_map(
    year: int,
    round_number: int,
    session_type: str = "Q",
    out_path: Optional[str] = None,
    size: Tuple[int, int] = (760, 460),
    allow_fallback: bool = True,
) -> Optional[str]:
    """Render a circuit outline PNG. Returns the path, or None on failure.

    If this year's session is unavailable (e.g. a future race), the same
    circuit is looked up in previous seasons and that layout is used instead.
    """
    out_path = out_path or track_map_path(year, round_number)

    # Try qualifying first (clean single-car trace), then race.
    for stype in (session_type, "R"):
        try:
            path = _render_with_session(year, round_number, stype, out_path, size)
            if path:
                return path
        except Exception:
            continue

    if allow_fallback:
        previous = _find_previous_year_round(year, round_number)
        if previous:
            py, pr = previous
            for stype in (session_type, "R"):
                try:
                    path = _render_with_session(py, pr, stype, out_path, size)
                    if path:
                        return path
                except Exception:
                    continue
    return None


def _find_previous_year_round(year: int, round_number: int, max_back: int = 3):
    """Find (year, round) of the same circuit in a previous season, or None."""
    import fastf1

    try:
        from src.f1_data import enable_cache

        enable_cache()
    except Exception:
        pass

    try:
        current = fastf1.get_event_schedule(int(year))
        rows = current[current["RoundNumber"] == int(round_number)]
        if rows.empty:
            return None
        loc = str(rows.iloc[0].get("Location", "") or "")
        name = str(rows.iloc[0].get("EventName", "") or "")
    except Exception:
        return None

    for back in range(1, int(max_back) + 1):
        try:
            sched = fastf1.get_event_schedule(int(year) - back)
        except Exception:
            continue
        for _, ev in sched.iterrows():
            try:
                if ev.is_testing():
                    continue
            except Exception:
                pass
            ev_loc = str(ev.get("Location", "") or "")
            ev_name = str(ev.get("EventName", "") or "")
            if (loc and ev_loc == loc) or (name and ev_name == name):
                return int(year) - back, int(ev["RoundNumber"])
    return None


def _render_with_session(year, round_number, session_type, out_path, size):
    import numpy as np
    import fastf1

    try:
        from src.f1_data import enable_cache

        enable_cache()
    except Exception:
        pass

    session = fastf1.get_session(int(year), int(round_number), session_type)
    session.load(telemetry=True, weather=False, messages=False)

    lap = session.laps.pick_fastest()
    if lap is None:
        return None
    tel = lap.get_telemetry()
    if "X" not in tel or "Y" not in tel or len(tel) < 10:
        return None

    x = np.asarray(tel["X"], dtype=float)
    y = np.asarray(tel["Y"], dtype=float)

    # Rotate so the circuit is oriented like a broadcast map (FastF1 convention
    # is often roughly 90° off); a light rotation keeps the aspect pleasing.
    theta = np.deg2rad(-90.0)
    xr = x * np.cos(theta) - y * np.sin(theta)
    yr = x * np.sin(theta) + y * np.cos(theta)

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    dpi = 100
    fig = plt.figure(figsize=(size[0] / dpi, size[1] / dpi), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.plot(xr, yr, color="#E10600", linewidth=4.5, solid_capstyle="round", zorder=3)

    # Start/finish marker at the first sample.
    ax.plot([xr[0]], [yr[0]], marker="o", markersize=7, color="#FFFFFF", zorder=4)

    ax.set_aspect("equal")
    ax.axis("off")
    fig.patch.set_alpha(0.0)
    ax.patch.set_alpha(0.0)
    fig.savefig(out_path, transparent=True, bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)
    return out_path
