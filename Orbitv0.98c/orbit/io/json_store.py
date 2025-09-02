from __future__ import annotations

"""Lightweight JSON persistence for Bridge objects used by auto-save editing sessions."""

import json
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

from .models import Bridge, Pillar, Trajectory, SafetyZone


# -----------------------------------------------------------------------------
# Serialisation helpers
# -----------------------------------------------------------------------------

def _pillar_to_dict(p: Pillar) -> Dict[str, Any]:
    return {"id": p.id, "x": p.x, "y": p.y, "z": p.z}


def _pillar_from_dict(d: Dict[str, Any]) -> Pillar:
    return Pillar(d["id"], d["x"], d["y"], d["z"])


def _zone_to_dict(z: SafetyZone) -> Dict[str, Any]:
    return {"id": z.id, "polygon": z.polygon, "z_min": z.z_min, "z_max": z.z_max}


def _zone_from_dict(d: Dict[str, Any]) -> SafetyZone:
    return SafetyZone(d["id"], d["polygon"], d["z_min"], d["z_max"])


def bridge_to_dict(bridge: Bridge) -> Dict[str, Any]:
    return {
        "name": bridge.name,
        "trajectory": bridge.trajectory.points.tolist(),  # type: ignore[arg-type]
        "pillars": [_pillar_to_dict(p) for p in bridge.pillars],
        "safety_zones": [_zone_to_dict(z) for z in bridge.safety_zones],
    }


def bridge_from_dict(data: Dict[str, Any]) -> Bridge:
    # Handle empty trajectory case - ensure it has shape (0, 3)
    traj_data = data.get("trajectory", [])
    if not traj_data:
        traj_array = np.empty((0, 3))
    else:
        traj_array = np.asarray(traj_data)
    traj = Trajectory(traj_array)
    pillars = [_pillar_from_dict(d) for d in data.get("pillars", [])]
    zones = [_zone_from_dict(d) for d in data.get("safety_zones", [])]
    return Bridge(name=data.get("name", "unknown"), trajectory=traj, pillars=pillars, safety_zones=zones)


# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------

def save_bridge_json(bridge: Bridge, path: str | Path):
    path = Path(path)
    path.write_text(json.dumps(bridge_to_dict(bridge), indent=2))


def load_bridge_json(path: str | Path) -> Bridge:
    data = json.loads(Path(path).read_text())
    return bridge_from_dict(data) 