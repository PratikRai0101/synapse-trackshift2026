"""Generative plant: battery, track and longitudinal dynamics."""

from .battery import (
    TerminalPowerResult,
    chemical_energy_j,
    integrate as integrate_battery,
    max_transferable_power_w,
    open_circuit_voltage,
    resistance,
    soc_for_chemical_energy_j,
    solve_terminal_power,
    usable_energy_j,
)
from .plant import Plant, PlantStep, initial_state
from .track import TrackReference, build_track, synthetic_circuit
from .geometry import (
    Footprint,
    PassMonitor,
    PassOutcome,
    Pose,
    TrackPath,
    footprint_corners,
    footprint_within_track,
    rectangles_overlap,
)

__all__ = [
    "TerminalPowerResult",
    "chemical_energy_j",
    "integrate_battery",
    "max_transferable_power_w",
    "open_circuit_voltage",
    "resistance",
    "soc_for_chemical_energy_j",
    "solve_terminal_power",
    "usable_energy_j",
    "Plant",
    "PlantStep",
    "initial_state",
    "TrackReference",
    "build_track",
    "synthetic_circuit",
    "Footprint",
    "PassMonitor",
    "PassOutcome",
    "Pose",
    "TrackPath",
    "footprint_corners",
    "footprint_within_track",
    "rectangles_overlap",
]
