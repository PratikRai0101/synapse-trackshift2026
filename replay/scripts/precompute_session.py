"""Precompute and cache session telemetry so the replay opens instantly.

The first time a round is opened, the app has to download the session and build
every frame (which can take minutes and produces a large pickle). Run this ahead
of time to pay that cost once. Sessions already cached are loaded instantly.

    python scripts/precompute_session.py 2026 3 --race
    python scripts/precompute_session.py 2026 3 --quali
"""

from __future__ import annotations

import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.disable(logging.CRITICAL)

from src.f1_data import (  # noqa: E402
    enable_cache,
    get_quali_telemetry,
    get_race_telemetry,
    load_session,
)

CACHE_DIR = "computed_data"


def main(argv) -> int:
    positional = [a for a in argv if not a.startswith("--")]
    if len(positional) < 2:
        print(__doc__)
        return 2
    year, round_number = int(positional[0]), int(positional[1])

    session_type = "R"
    if "--quali" in argv:
        session_type = "Q"
    elif "--sprint" in argv:
        session_type = "S"
    elif "--sprint-quali" in argv:
        session_type = "SQ"

    enable_cache()
    t0 = time.time()
    print(f"Loading {year} round {round_number} session {session_type}…", flush=True)
    session = load_session(year, round_number, session_type)
    print(f"  loaded in {time.time() - t0:.1f}s", flush=True)

    t1 = time.time()
    if session_type in ("Q", "SQ"):
        print("Computing qualifying telemetry (caches to computed_data/)…", flush=True)
        get_quali_telemetry(session, session_type=session_type)
    else:
        print("Computing race telemetry (caches to computed_data/)…", flush=True)
        get_race_telemetry(session, session_type=session_type)
    print(f"done in {time.time() - t1:.1f}s — next launch will be instant.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
