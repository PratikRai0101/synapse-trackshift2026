#!/usr/bin/env python3
"""Stream a replay_ai closed-loop branch to the 3D viewer.

The recorded replay and a simulated branch must never be confused, so this runs
as its own process on the same TCP telemetry port the bridge already reads:

    python scripts/simulate_stream.py --action BURN   ->  bridge  ->  viewer3d

Every payload is marked ``run_mode: "simulated"`` and carries its provenance,
so a viewer can label it. Only public branch state enters the simulator; the
hidden rival mode used for evaluation is never published.

    --action BURN|HARVEST|"PROACTIVE TRAP"   forced action (default: reference)
    --steps N                                model steps of 0.1 s (default 60)
    --hz HZ                                  publish rate (default 10)
    --port PORT                              telemetry port (default 9999)
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    import _bootstrap  # noqa: F401
except ImportError:
    from . import _bootstrap  # noqa: F401

from src.intelligence.closed_loop import HiddenRivalMode
from src.intelligence.simulation_motion import DT_S, motion_packet


@dataclass
class RecordingBranch:
    """Publicly observed state a branch may start from.

    Defaults are a documented synthetic development start, not a claim about a
    real driver's battery. Feed real values when driving this from a replay.
    """

    frame_index: int = 0
    timestamp_s: float = 0.0
    driver: str = "EGO"
    rival: str = "RIV"
    own_speed_kmh: float = 275.0
    rival_speed_kmh: float = 275.0
    gap_s: float = 0.9
    own_energy: float = 70.0
    battery_temperature: float = 70.0
    battery_soh: float = 1.0
    lap: int = 1
    tags: dict = field(default_factory=dict)


def _loop_point(distance_m: float, perimeter: float = 2 * 900.0 + 2 * math.pi * 400.0):
    """Local copy of the display loop, used only to place the safety overlay."""
    d = distance_m % perimeter
    half = 450.0
    if d < 900.0:
        return (-half + d, -400.0)
    d -= 900.0
    if d < math.pi * 400.0:
        a = d / 400.0 - math.pi / 2
        return (half + math.cos(a) * 400.0, math.sin(a) * 400.0)
    d -= math.pi * 400.0
    if d < 900.0:
        return (half - d, 400.0)
    a = (d - 900.0) / 400.0 + math.pi / 2
    return (-half + math.cos(a) * 400.0, math.sin(a) * 400.0)


def stream(action: str | None, steps: int, hz: float, port: int,
           host: str = "127.0.0.1") -> None:
    import socket

    try:
        from src.services.stream import TelemetryStreamServer
        server = TelemetryStreamServer(host=host, port=port)
        server.start()
        publish = server.broadcast
        stop = server.stop
    except Exception:
        # Qt is unavailable in some headless environments; fall back to a
        # minimal server that speaks the same newline-delimited JSON protocol.
        clients: list[socket.socket] = []
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((host, port))
        listener.listen(5)

        def accept() -> None:
            while True:
                try:
                    connection, address = listener.accept()
                except OSError:
                    return
                print(f"[sim] viewer connected from {address}")
                clients.append(connection)

        threading.Thread(target=accept, daemon=True).start()

        def publish(payload: dict) -> None:
            message = json.dumps(payload).encode("utf-8") + b"\n"
            for connection in list(clients):
                try:
                    connection.sendall(message)
                except OSError:
                    clients.remove(connection)

        def stop() -> None:
            listener.close()

    branch = RecordingBranch()
    # One trace per action, reused so the published motion is deterministic and
    # a viewer attaching mid-run sees the same branch every time.
    payload = motion_packet(branch, action=action, steps=steps,
                           mode=HiddenRivalMode.MATCH)
    trace = payload["trace"]
    geometry = payload["track_geometry"]
    colors = payload["driver_colors"]

    print(f"[sim] action={action or 'reference'} steps={steps} "
          f"({steps * DT_S:.1f}s model time) -> {host}:{port}")
    print(f"[sim] run_mode={payload['run_mode']} | {payload['motion_provenance']}")

    interval = 1.0 / max(0.5, hz)
    index = 0
    try:
        while True:
            step = trace[min(index, len(trace) - 1)]
            drivers = {
                branch.driver: {
                    "x": step["ego_x"], "y": step["ego_y"],
                    "speed": step["ego_speed_kmh"], "gear": 7, "drs": 0,
                    "throttle": 100, "brake": 0, "tyre": 2, "lap": branch.lap,
                    "rel_dist": (step["ego_distance_m"] % payload["circuit_length_m"]) / payload["circuit_length_m"],
                    "position": 2,
                    "fraction": step["ego_distance_m"] / payload["circuit_length_m"],
                    "heading": step["ego_heading"], "in_pit": False,
                    "motion_quality": "sampled",
                },
                branch.rival: {
                    "x": step["rival_x"], "y": step["rival_y"],
                    "speed": step["rival_speed_kmh"], "gear": 7, "drs": 0,
                    "throttle": 100, "brake": 0, "tyre": 2, "lap": branch.lap,
                    "rel_dist": (step["rival_distance_m"] % payload["circuit_length_m"]) / payload["circuit_length_m"],
                    "position": 1,
                    "fraction": step["rival_distance_m"] / payload["circuit_length_m"],
                    "heading": step["rival_heading"], "in_pit": False,
                    "motion_quality": "sampled",
                },
            }
            publish({
                **{key: payload[key] for key in (
                    "source_id", "coordinate_units", "run_mode",
                    "geometry_provenance", "motion_provenance",
                    "circuit_length_m", "track_status", "total_frames",
                    "has_rc_data", "race_control_events", "selected_drivers",
                )},
                "frame_index": index,
                "frame": {"t": step["t_s"], "lap": branch.lap,
                          "drivers": drivers, "safety_car": None},
                "playback_speed": 1,
                "is_paused": False,
                "driver_colors": colors,
                "session_data": {
                    "time": "", "time_s": step["t_s"], "lap": branch.lap,
                    "leader": branch.rival, "total_laps": 0,
                },
                "track_geometry": geometry if index % 30 == 0 else None,
                "simulation": {
                    "command": action or "reference",
                    "gap_s": step["gap_s"],
                    "ego_energy": step["ego_energy"],
                    "contact": step["contact"],
                    "model": "replay_ai.closed_loop",
                },
            })
            # Loop so a viewer that attaches late still sees the whole branch.
            index = (index + 1) % len(trace)
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n[sim] stopped")
    finally:
        stop()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--action", default=None,
                        help="BURN, HARVEST, 'PROACTIVE TRAP', or omit for the reference policy")
    parser.add_argument("--steps", type=int, default=60)
    parser.add_argument("--hz", type=float, default=10.0)
    parser.add_argument("--port", type=int, default=9999)
    args = parser.parse_args()
    stream(args.action, max(1, args.steps), args.hz, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
