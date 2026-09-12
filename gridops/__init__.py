"""GRID//OPS — energy and overtake decision support engine.

Separate from the replay application. This package is headless and pure
Python/NumPy: it must import and run with ``arcade`` and ``fastf1`` absent.

The main seams are:

- ``contracts``   versioned records, units and provenance
- ``simulation``  the generative plant (truth side)
- ``decision``    belief, commitment, POMCP search, supervisor
- ``race_value``  remaining-race resource value
- ``evaluation``  deterministic runner, baselines, batches
"""

__version__ = "0.1.0"
__all__ = ["__version__"]
