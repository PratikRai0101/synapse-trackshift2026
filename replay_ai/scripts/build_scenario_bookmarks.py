#!/usr/bin/env python3
"""Precompute deterministic Judge Mode scenario bookmarks for one race.

The live pitch must not depend on scrubbing to an interesting moment. This
scans each requested driver's recorded public telemetry once and writes
``computed_data/scenario_bookmarks_<year>_<round>.json``; the replay then loads
the artifact at startup so pressing 5-0 is instant and reproducible.

Example::

    python scripts/build_scenario_bookmarks.py --year 2026 --round 13
"""
from __future__ import annotations

import argparse
import os
import pickle
import sys
import time
from pathlib import Path
from typing import Optional

try:
    import _bootstrap  # noqa: F401  (adds project root to sys.path)
except ImportError:  # imported as ``scripts.<name>`` by the test suite
    from . import _bootstrap  # noqa: F401

from src.intelligence.scenarios import (
    SCENARIOS,
    build_energy_soc,
    save_scenario_artifact,
    scan_recorded_driver,
    scenario_artifact_path,
    select_scenario_frames,
)


def _find_cached_telemetry(year: int, round_number: int) -> Optional[str]:
    import glob

    patterns = (
        f"computed_data/{year}_Season_Round_{round_number}*race_telemetry.pkl",
        f"computed_data/*Round_{round_number}*race_telemetry.pkl",
        "computed_data/*race_telemetry.pkl",
    )
    for pattern in patterns:
        hits = sorted(glob.glob(pattern))
        if hits:
            return hits[0]
    return None


def _load_telemetry(path: str) -> dict:
    with open(path, "rb") as source:
        return pickle.load(source)


def _driver_codes(frames) -> list[str]:
    for frame in frames:
        codes = sorted(frame.get("drivers", {}))
        if codes:
            return codes
    return []


def build(year: int, round_number: int, telemetry_path: str, *,
          sample_step: int = 50, drivers: Optional[list[str]] = None,
          hmm_artifact: Optional[str] = None, out_path: Optional[str] = None,
          min_lap: int = 2) -> dict[str, dict[str, int]]:
    telemetry = _load_telemetry(telemetry_path)
    frames = telemetry.get("frames", [])
    if not frames:
        raise ValueError(f"no frames in {telemetry_path}")
    codes = drivers or _driver_codes(frames)
    targets: dict[str, dict[str, int]] = {}
    started = time.perf_counter()
    for index, driver in enumerate(codes, start=1):
        soc = build_energy_soc(frames, driver)
        observations = scan_recorded_driver(
            frames, driver, soc,
            hmm_artifact=hmm_artifact,
            sample_step=sample_step,
            min_lap=min_lap,
        )
        chosen = select_scenario_frames(observations)
        if chosen:
            targets[driver] = chosen
        found = ", ".join(f"{key}={chosen.get(key, '-')}"
                          for key in (spec.key for spec in SCENARIOS))
        print(f"[{index}/{len(codes)}] {driver}: {found}")
    destination = out_path or scenario_artifact_path(year, round_number)
    save_scenario_artifact(
        destination, targets,
        year=year, round_number=round_number, sample_step=sample_step,
    )
    elapsed = time.perf_counter() - started
    print(f"Wrote {len(targets)} drivers to {destination} in {elapsed:.1f}s")
    return targets


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--round", type=int, required=True)
    parser.add_argument("--telemetry", type=str, default=None,
                        help="Cached race telemetry pkl (auto-detected if omitted)")
    parser.add_argument("--out", type=str, default=None)
    parser.add_argument("--sample-step", type=int, default=50)
    parser.add_argument("--min-lap", type=int, default=2)
    parser.add_argument("--drivers", type=str, default=None,
                        help="Comma-separated driver codes (default: whole field)")
    parser.add_argument("--hmm-artifact", type=str, default=None)
    args = parser.parse_args(argv)

    telemetry_path = args.telemetry or _find_cached_telemetry(args.year, args.round)
    if not telemetry_path or not os.path.exists(telemetry_path):
        print("No cached race telemetry found; pass --telemetry PATH", file=sys.stderr)
        return 2
    drivers = ([code.strip().upper() for code in args.drivers.split(",") if code.strip()]
               if args.drivers else None)
    default_hmm = Path(__file__).resolve().parents[1] / "artifacts" / "hmm-emissions.json"
    hmm_artifact = args.hmm_artifact or (str(default_hmm)
                                         if default_hmm.exists() else None)
    build(
        args.year, args.round, telemetry_path,
        sample_step=args.sample_step, drivers=drivers,
        hmm_artifact=hmm_artifact, out_path=args.out,
        min_lap=args.min_lap,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
