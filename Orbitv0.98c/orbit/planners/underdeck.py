from __future__ import annotations

"""Under-deck inspection flight-path planner.

This is a **first-cut** modular replacement for the hard-wired logic that lived
in the legacy Jupyter notebook.  It supports:

• Any number of spans (deduced from pillar count).
• Separate check-boxes in the GUI for generating *normal* and/or *axial* routes
  per span (exposed via the `span_recipe` parameter).
• Three connection styles between right/left side passes:
    – UNDERDECK  (existing behaviour)
    – OVERDECK   (rise to `overdeck_height` then descend)
    – NONE       (no connection – keeps sides separate)

Future extensions (horizontal-offset tweaking, route merging, etc.) can be
implemented by subclassing or extending parameter dataclass.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Dict, Tuple

import numpy as np

from ..io.models import Bridge, FlightRoute
from ..io.context import ProjectContext
from .overview_flight_generator import PhotogrammetricPlanner  # reuse normal computation helpers
from .safety import filter_route_outside_zones


class FlyThroughMode(Enum):
    UNDERDECK = auto()
    OVERDECK = auto()
    NONE = auto()


@dataclass
class SpanRecipe:
    """What routes to generate for a given span index (0-based)."""

    generate_normal: bool = True
    generate_axial: bool = False


@dataclass
class UnderdeckPlanParameters:
    # Offsets & heights
    horizontal_offset: float = 6.0   # metres each side from trajectory
    vertical_clearance: float = 2.0  # metres below deck for *normal* route
    axial_connection_height: float = 3.0  # vertical hop between passes

    # Fly-through / connection behaviour
    flythrough_mode: FlyThroughMode = FlyThroughMode.UNDERDECK
    overdeck_height: float = 30.0   # m above deck for OVERDECK mode

    # Per-span recipe. Key = span index (0..N-1)
    span_recipe: Dict[int, SpanRecipe] | None = None  # set in planner if None


class UnderdeckPlanner:
    def __init__(self, ctx: ProjectContext, params: UnderdeckPlanParameters | None = None):
        self.ctx = ctx
        self.params = params or UnderdeckPlanParameters()

    # ------------------------------------------------------------------
    def plan(self, bridge: Bridge) -> List[FlightRoute]:
        spans = self._deduce_spans(bridge)
        if not spans:
            raise ValueError("At least one span required – please add pillars")

        # Default recipes: middle span normal only
        if self.params.span_recipe is None:
            mid = len(spans) // 2
            self.params.span_recipe = {mid: SpanRecipe(generate_normal=True, generate_axial=False)}

        routes: List[FlightRoute] = []
        for idx, (s_start, s_end) in enumerate(spans):
            recipe = self.params.span_recipe.get(idx, SpanRecipe(False, False))
            if not (recipe.generate_normal or recipe.generate_axial):
                continue
            span_points = bridge.trajectory.points[s_start : s_end + 1]
            normals = PhotogrammetricPlanner._compute_normals(span_points)  # type: ignore[attr-defined]

            if recipe.generate_normal:
                routes.extend(self._build_normal_routes(idx, span_points, normals, bridge))
            if recipe.generate_axial:
                routes.extend(self._build_axial_routes(idx, span_points, normals, bridge))
        return routes

    # ------------------------------------------------------------------
    def _build_normal_routes(self, span_idx, points, normals, bridge) -> List[FlightRoute]:
        offset = self.params.horizontal_offset
        down = -self.params.vertical_clearance
        right = points + normals * offset + np.array([0, 0, down])
        left = points - normals * offset + np.array([0, 0, down])

        # Connection between sides depending on mode
        if self.params.flythrough_mode == FlyThroughMode.NONE:
            pts = np.vstack([right, left])  # separate logically but one route for now
        elif self.params.flythrough_mode == FlyThroughMode.UNDERDECK:
            pts = np.vstack([right, left[::-1]])  # simple U-turn underneath
        else:  # OVERDECK
            mid_right = right[-1]
            mid_left = left[0]
            over = np.array([mid_right[0], mid_right[1], mid_right[2] + self.params.overdeck_height])
            pts = np.vstack([right, over, mid_left, left])

        pts = self._apply_safety(pts, bridge)
        tag = f"underdeck_span{span_idx+1}_normal"
        return [FlightRoute(pts, tags=[tag] * len(pts))]

    def _build_axial_routes(self, span_idx, points, normals, bridge) -> List[FlightRoute]:
        # Axial zig-zag between girders placeholder: simple vertical connections
        offset = self.params.horizontal_offset / 2
        right = points + normals * offset
        left = points - normals * offset
        connection_height = self.params.axial_connection_height
        seq = []
        for r, l in zip(right, left):
            seq.append(r)
            seq.append(r + np.array([0, 0, connection_height]))
            seq.append(l + np.array([0, 0, connection_height]))
            seq.append(l)
        pts = np.asarray(seq)
        pts = self._apply_safety(pts, bridge)
        tag = f"underdeck_span{span_idx+1}_axial"
        return [FlightRoute(pts, tags=[tag] * len(pts))]

    # ------------------------------------------------------------------
    def _apply_safety(self, pts: np.ndarray, bridge: Bridge) -> np.ndarray:
        if bridge.safety_zones:
            pts = filter_route_outside_zones(pts, bridge.safety_zones)
        return pts

    # ------------------------------------------------------------------
    @staticmethod
    def _deduce_spans(bridge: Bridge) -> List[Tuple[int, int]]:
        """Return list of (start_idx, end_idx) indices into trajectory for each span."""
        n_pillars = len(bridge.pillars)
        if n_pillars < 2:
            return [(0, len(bridge.trajectory.points) - 1)]

        # Approximate by mapping each pillar to nearest trajectory index (x-y distance)
        traj_xy = bridge.trajectory.points[:, :2]
        pillar_xy = np.array([[p.x, p.y] for p in bridge.pillars])
        idxs = []
        for p in pillar_xy:
            dists = np.linalg.norm(traj_xy - p, axis=1)
            idxs.append(int(np.argmin(dists)))
        idxs = sorted(idxs)
        spans = []
        prev = 0
        for idx in idxs:
            spans.append((prev, idx))
            prev = idx
        spans.append((prev, len(traj_xy) - 1))
        return spans 