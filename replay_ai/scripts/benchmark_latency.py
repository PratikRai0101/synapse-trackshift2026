#!/usr/bin/env python3
"""Measure per-block latency of the hierarchical intelligence stack.

Each architecture block is timed independently so the reported budget can be
compared against the design targets (Level 1 every 10 ms, Level 2 per sector,
Level 3 per lap, Level 4 per race weekend).
"""
from __future__ import annotations

import argparse
import json
import platform
import statistics
import time
from pathlib import Path

try:
    import _bootstrap  # noqa: F401
except ImportError:
    from . import _bootstrap

from src.intelligence.closed_loop import ClosedLoopSimulator, HiddenRivalMode
from src.intelligence.control_layers import BoundedScenarioPlanner
from src.intelligence.hierarchical import (
    ERSMode,
    FeatureExtractor,
    FortyStateHMM,
    MotorsportIntelligence,
    RivalTelemetry,
    SeasonLifecycleManager,
)
from src.intelligence.lap_strategy import LapTimeMap, LapTimeSample, RaceEnergyPlanner
from src.intelligence.scenario_search import ParticlePOMCP, SearchConfig
from src.intelligence.spatial_planner import SpatialTrajectoryPlanner, TrackSample
from src.intelligence.socp_envelope import SOCPPerformanceEnvelope
from src.intelligence.vehicle_plant import VehiclePlant
from src.intelligence.zone_mpc import ZoneMPC


def percentiles(samples_ns: list[float]) -> dict:
    ordered = sorted(samples_ns)
    count = len(ordered)

    def pick(fraction: float) -> float:
        index = min(count - 1, max(0, int(round(fraction * (count - 1)))))
        return ordered[index]

    return {
        "n": count,
        "mean_ms": statistics.fmean(ordered) / 1e6,
        "p50_ms": pick(0.50) / 1e6,
        "p95_ms": pick(0.95) / 1e6,
        "p99_ms": pick(0.99) / 1e6,
        "max_ms": ordered[-1] / 1e6,
    }


def timeit(fn, iterations: int, warmup: int = 5) -> dict:
    for _ in range(warmup):
        fn()
    samples: list[float] = []
    for _ in range(iterations):
        start = time.perf_counter_ns()
        fn()
        samples.append(time.perf_counter_ns() - start)
    return percentiles(samples)


def _fitted_lap_map() -> LapTimeMap:
    rows = []
    for index in range(120):
        deployed = float(index % 30)
        rows.append(LapTimeSample(
            lap_time_s=92.0 - deployed * 0.05 + (index % 7) * 0.02,
            battery_deployed=deployed,
            fuel_deployed=float(index % 10),
            tyre_wear=(index % 40) / 40.0,
            mass_kg=800.0 + (index % 5) * 10.0,
            track_baseline_s=92.0,
        ))
    return LapTimeMap().fit(rows)


def _belief():
    hmm = FortyStateHMM()
    features = FeatureExtractor().update(RivalTelemetry(300, 100, 0, 0.8))
    return hmm.update(features)


def measure(iterations: int) -> dict:
    telemetry = RivalTelemetry(300, 100, 0, 0.8, lap=1, tyre_life=0.1)
    belief = _belief()
    extractor = FeatureExtractor()
    hmm = FortyStateHMM()
    lap_map = _fitted_lap_map()
    level3 = RaceEnergyPlanner(lap_map)
    level4 = SeasonLifecycleManager()
    track = tuple(TrackSample(index * 25.0, 0.001 + 0.0002 * index)
                  for index in range(5))
    plant = VehiclePlant()
    mpc = ZoneMPC()

    blocks: dict[str, dict] = {}
    blocks["1_telemetry_features"] = timeit(
        lambda: extractor.update(telemetry), iterations)
    blocks["2_hmm_40_state_update"] = timeit(
        lambda: hmm.update(belief.features), iterations)
    blocks["4_level4_season_dp"] = timeit(
        lambda: level4.decide(0.9, 90.0), iterations)
    blocks["3_level3_lap_dp"] = timeit(
        lambda: level3.plan(60.0, tyre_wear=0.3, battery_soh=0.95), max(20, iterations // 10))
    blocks["2_level2_heuristic_only"] = timeit(
        lambda: BoundedScenarioPlanner(use_search=False, use_spatial=False)
        .plan(belief, 300.0, 0.8, 60.0), iterations)
    blocks["2_level2_plus_socp"] = timeit(
        lambda: BoundedScenarioPlanner(use_search=False, use_spatial=True)
        .plan(belief, 300.0, 0.8, 60.0), iterations)
    blocks["2_level2_plus_pomcp"] = timeit(
        lambda: BoundedScenarioPlanner(use_search=True, use_spatial=False)
        .plan(belief, 300.0, 0.8, 60.0), max(10, iterations // 5))
    blocks["2_level2_full"] = timeit(
        lambda: BoundedScenarioPlanner().plan(belief, 300.0, 0.8, 60.0),
        max(10, iterations // 5))
    blocks["2a_pomcp_search_only"] = timeit(
        lambda: ParticlePOMCP().search(belief, 0.8, 60.0), max(10, iterations // 5))
    blocks["2b_socp_spatial_only"] = timeit(
        lambda: SpatialTrajectoryPlanner().plan(track, 300.0), iterations)
    blocks["2c_g_g_envelope_point"] = timeit(
        lambda: SOCPPerformanceEnvelope().solve([0.0], [300.0], [0.001], [8.0]),
        iterations)
    blocks["1_level1_mpc"] = timeit(
        lambda: mpc.solve(300.0, 60.0, 320.0), iterations)
    blocks["0_vehicle_plant_step"] = timeit(
        lambda: plant.step(0.8, 0.01, 0.001), iterations * 5)

    model = MotorsportIntelligence()
    blocks["END_TO_END_observe"] = timeit(
        lambda: model.observe(telemetry, own_speed_kmh=300.0, own_soc=60.0),
        max(10, iterations // 5))
    blocks["END_TO_END_closed_loop_step"] = timeit(
        lambda: ClosedLoopSimulator(HiddenRivalMode.MATCH, seed=1).step(),
        max(10, iterations // 10))
    blocks["C_counterfactual_fork"] = timeit(
        _counterfactual_call, max(3, iterations // 50))

    return {
        "schema": "latency-report.v1",
        "platform": platform.platform(),
        "processor": platform.processor() or platform.machine(),
        "python": platform.python_version(),
        "iterations": iterations,
        "blocks": blocks,
        "design_budgets_ms": {
            "1_level1_mpc": 10.0,
            "2_level2_full": 1000.0,
            "3_level3_lap_dp": 1000.0,
            "4_level4_season_dp": 1000.0,
        },
    }


def _counterfactual_call():
    from src.judge_mode import BranchStart, run_counterfactual

    start = BranchStart(
        frame_index=120, timestamp_s=42.0, driver="OCO", rival="HAM",
        own_speed_kmh=277.0, rival_speed_kmh=280.0, gap_s=13.2,
        own_energy=55.0, battery_temperature=85.0, battery_soh=0.97, lap=2,
    )
    return run_counterfactual(start, steps=20, seed=120)


def pomcp_scaling() -> list[dict]:
    belief = _belief()
    rows = []
    for simulations, particles in ((64, 32), (128, 64), (256, 128), (512, 256)):
        config = SearchConfig(simulations=simulations, particles=particles)
        search = ParticlePOMCP(config)
        result = timeit(lambda: search.search(belief, 0.8, 60.0), 20)
        rows.append({
            "simulations": simulations,
            "particles": particles,
            "p50_ms": result["p50_ms"],
            "p95_ms": result["p95_ms"],
        })
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iterations", type=int, default=200)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = measure(args.iterations)
    report["pomcp_scaling"] = pomcp_scaling()
    text = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    for name, stats in report["blocks"].items():
        print(f"{name:<32} mean {stats['mean_ms']:8.4f} ms   "
              f"p50 {stats['p50_ms']:8.4f}   p95 {stats['p95_ms']:8.4f}   "
              f"p99 {stats['p99_ms']:8.4f}")
    print("\nPOMCP scaling:")
    for row in report["pomcp_scaling"]:
        print(f"  sims={row['simulations']:<4} particles={row['particles']:<4} "
              f"p50 {row['p50_ms']:7.3f} ms   p95 {row['p95_ms']:7.3f} ms")


if __name__ == "__main__":
    main()
