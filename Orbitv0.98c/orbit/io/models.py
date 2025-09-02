from __future__ import annotations

"""Core domain models used throughout Orbit.

These classes are intentionally lightweight (plain dataclasses) and do **not**
include any heavy computation – algorithms live in ``orbit.planners`` or other
packages so that models stay serialisable and easy to test.
"""

from dataclasses import dataclass, field
from typing import List
import numpy as np


@dataclass
class Pillar:
    """Concrete bridge support element."""

    id: str
    x: float  # metres (project CRS)
    y: float  # metres (project CRS)
    z: float  # metres (project CRS)

    def as_array(self) -> np.ndarray:
        return np.asarray([self.x, self.y, self.z], dtype=float)


@dataclass
class Trajectory:
    """3-D centreline of the bridge (project CRS)."""

    points: np.ndarray  # shape (N, 3)

    def __post_init__(self):
        self.points = np.atleast_2d(self.points).astype(float)
        if self.points.shape[1] != 3:
            raise ValueError("Trajectory points must be an (N, 3) array")

    @property
    def length(self) -> float:
        """Euclidean length calculated in the *XY* plane."""
        diffs = np.diff(self.points[:, :2], axis=0)
        return np.sum(np.linalg.norm(diffs, axis=1))


@dataclass
class FlightRoute:
    """A sequence of way-points with optional semantic *tag* information."""

    points: np.ndarray  # shape (N, 3)
    tags: List[str] = field(default_factory=list)

    def __post_init__(self):
        self.points = np.atleast_2d(self.points).astype(float)
        if self.points.shape[1] != 3:
            raise ValueError("FlightRoute points must be an (N, 3) array")
        if self.tags and len(self.tags) != len(self.points):
            raise ValueError("Length of tags must match number of points")


@dataclass
class SafetyZone:
    """Forbidden or caution area represented as a 2-D polygon with vertical limits."""

    id: str
    polygon: List[tuple[float, float]]  # list of (x, y) in project CRS
    z_min: float  # metres (project CRS)
    z_max: float  # metres (project CRS)

    def contains_point(self, x: float, y: float) -> bool:
        # Simple ray-casting algorithm (even–odd rule) – placeholder; real check should use shapely in algorithms.
        inside = False
        n = len(self.polygon)
        px, py = x, y
        for i in range(n):
            x1, y1 = self.polygon[i]
            x2, y2 = self.polygon[(i + 1) % n]
            cond = ((y1 > py) != (y2 > py)) and (px < (x2 - x1) * (py - y1) / (y2 - y1 + 1e-9) + x1)
            if cond:
                inside = not inside
        return inside


@dataclass
class Bridge:
    """Aggregate model representing all bridge-related data."""

    name: str
    trajectory: Trajectory
    pillars: List[Pillar]
    safety_zones: List[SafetyZone] = field(default_factory=list)

    def pillar_ids(self) -> List[str]:
        return [p.id for p in self.pillars] 