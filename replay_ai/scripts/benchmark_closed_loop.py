#!/usr/bin/env python3
"""Benchmark the hierarchical reference controller against hidden rival modes."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

try:
    import _bootstrap  # noqa: F401
except ImportError:
    from . import _bootstrap  # noqa: F401

from src.intelligence.closed_loop import ClosedLoopSimulator, HiddenRivalMode


def run_episode(mode: HiddenRivalMode, steps: int,
                hmm_artifact: str | None = None) -> dict:
    simulator = ClosedLoopSimulator(mode, hmm_artifact=hmm_artifact)
    trace = simulator.run(steps)
    commands = Counter(step.decision.command for step in trace)
    return {
        "rival_mode": mode.value,
        "hmm_source": simulator.model.hmm_source,
        "steps": len(trace),
        "final_gap_s": simulator.ego.gap_s,
        "final_ego_speed_kmh": simulator.ego.speed_kmh,
        "final_ego_energy": simulator.ego.energy,
        "commands": dict(commands),
        "completed": len(trace) == steps,
    }


def benchmark(steps: int = 100, hmm_artifact: str | None = None) -> dict:
    episodes = [run_episode(mode, steps, hmm_artifact) for mode in HiddenRivalMode]
    return {
        "schema": "closed-loop-benchmark.v1",
        "steps": steps,
        "episodes": episodes,
        "completion_rate": sum(e["completed"] for e in episodes) / len(episodes),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--steps", type=int, default=100)
    parser.add_argument("--artifact", type=Path,
                        help="calibrated HMM emissions JSON artifact")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = benchmark(args.steps, str(args.artifact) if args.artifact else None)
    text = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text, end="")


if __name__ == "__main__":
    main()
