"""Pre-render and cache circuit-layout maps for a season.

Run once (e.g. before a demo) so the GP carousel is instant:

    python scripts/prewarm_track_maps.py 2026

Already-cached maps are skipped. Sessions come from the FastF1 cache, so this
only has to parse them once.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from datetime import date as _date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.disable(logging.CRITICAL)

from src.f1_data import enable_cache, get_race_weekends_by_year  # noqa: E402
from src.gui.track_map import cached_track_map, render_track_map  # noqa: E402


def _is_upcoming(ev: dict) -> bool:
    date_str = str(ev.get("date", ""))
    if not date_str:
        return False
    try:
        return _date.fromisoformat(date_str[:10]) > _date.today()
    except ValueError:
        return False


def main(year: int) -> int:
    enable_cache()
    events = get_race_weekends_by_year(year)
    total = len(events)
    ok = 0
    for i, ev in enumerate(events, 1):
        try:
            rn = int(ev.get("round_number"))
        except (TypeError, ValueError):
            continue
        if _is_upcoming(ev):
            ok += 1
            print(f"[{i}/{total}] round {rn:02d} upcoming, skip", flush=True)
            continue
        if cached_track_map(year, rn):
            ok += 1
            print(f"[{i}/{total}] round {rn:02d} cached, skip", flush=True)
            continue
        t0 = time.time()
        path = render_track_map(year, rn)
        status = path or "FAILED"
        print(
            f"[{i}/{total}] round {rn:02d} {ev.get('event_name','')}: "
            f"{status} ({time.time() - t0:.1f}s)",
            flush=True,
        )
        if path:
            ok += 1
    print(f"done: {ok}/{total} maps available for {year}", flush=True)
    return 0 if ok == total else 1


if __name__ == "__main__":
    y = int(sys.argv[1]) if len(sys.argv) > 1 else 2026
    raise SystemExit(main(y))
