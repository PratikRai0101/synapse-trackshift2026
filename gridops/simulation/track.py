"""Fixed-path track geometry.

Geometry is either verified or explicitly synthetic. Synthetic here means the
parameters are declared assumptions, not an inferred real circuit.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..contracts.state import Track, TrackSample


def build_track(
    length_m: float,
    corner_zones: list[tuple[float, float, float]],
    n_samples: int = 240,
) -> Track:
    """Build a closed track from fractional corner zones.

    ``corner_zones`` entries are ``(start_fraction, end_fraction, radius_m)``.
    Straight sections have zero curvature.
    """
    samples: list[TrackSample] = []
    for i in range(n_samples):
        frac = i / n_samples
        s_m = length_m * frac
        curvature = 0.0
        for start, end, radius in corner_zones:
            if start <= frac < end and radius > 0.0:
                curvature = 1.0 / radius
                break
        samples.append(TrackSample(s_m=s_m, curvature_1_per_m=curvature))
    samples.append(TrackSample(s_m=length_m, curvature_1_per_m=0.0))
    return Track(length_m=length_m, samples=tuple(samples))


def synthetic_circuit() -> Track:
    """A declared synthetic circuit: long straights, mixed corners.

    ~5.8 km, intended for the demonstrator only. Not a verified real layout.
    """
    return build_track(
        length_m=5_800.0,
        corner_zones=[
            (0.08, 0.13, 90.0),
            (0.20, 0.24, 180.0),
            (0.33, 0.38, 60.0),
            (0.45, 0.48, 220.0),
            (0.58, 0.63, 75.0),
            (0.70, 0.73, 150.0),
            (0.82, 0.87, 55.0),
            (0.92, 0.95, 200.0),
        ],
        n_samples=240,
    )


@dataclass(frozen=True)
class TrackReference:
    """A distance-indexed reference speed profile for the plant tracker."""

    s_m: tuple[float, ...]
    speed_mps: tuple[float, ...]

    def speed_at(self, s_m: float) -> float:
        if not self.s_m:
            return 0.0
        if len(self.s_m) == 1:
            return self.speed_mps[0]
        s = s_m % self.s_m[-1] if self.s_m[-1] > 0 else s_m
        for i in range(len(self.s_m) - 1):
            if self.s_m[i] <= s <= self.s_m[i + 1]:
                a, b = self.s_m[i], self.s_m[i + 1]
                if b <= a:
                    return self.speed_mps[i]
                t = (s - a) / (b - a)
                return self.speed_mps[i] * (1 - t) + self.speed_mps[i + 1] * t
        return self.speed_mps[-1]
