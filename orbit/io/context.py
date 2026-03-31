from __future__ import annotations

"""Project context encapsulating coordinate reference system + vertical datum.

This module provides global coordinate system functionality supporting any CRS.
"""

from dataclasses import dataclass
from enum import Enum, auto
import re
from typing import Any, Dict, List, Tuple, Optional

from .crs import CoordinateSystem


class VerticalRef(Enum):
    """Vertical reference - simplified to always use ellipsoid heights.

    The vertical datum is now handled by heightStartingPoint_Ellipsoid
    and heightStartingPoint_Reference values in the flight export.
    """
    ELLIPSOID = auto()  # Height above reference ellipsoid (always used)
    MSL = auto()        # Mean Sea Level (mapped to ellipsoid for compatibility)


@dataclass
class ProjectContext:
    """Encapsulates CRS + vertical reference for all coordinate transformations."""
    
    crs: CoordinateSystem
    vertical_ref: VerticalRef
    ground_elev: float = 0.0  # Only relevant if vertical_ref == AGL
    
    @classmethod
    def from_epsg(cls, epsg_code: int, vertical_ref: VerticalRef, ground_elev: float = 0.0) -> ProjectContext:
        return cls(CoordinateSystem.from_epsg(epsg_code), vertical_ref, ground_elev)
    
    # ---------------------------------------------------------------------
    # Coordinate transformation methods
    # ---------------------------------------------------------------------
    def project_to_wgs84(self, x: float, y: float, z: float | None = None) -> Tuple[float, float, float | None]:
        lon, lat, z_ellipsoid = self.crs.to_wgs84(x, y, z)
        alt = self._to_output_altitude(z_ellipsoid)
        return lon, lat, alt

    def wgs84_to_project(self, lon: float, lat: float, alt: float | None = None) -> Tuple[float, float, float | None]:
        z_ellipsoid = self._from_input_altitude(alt)
        return self.crs.to_project(lon, lat, z_ellipsoid)

    # ------------------------------------------------------------------
    # Internal altitude conversions
    # ------------------------------------------------------------------
    def _to_output_altitude(self, z_ellipsoid: float | None) -> float | None:
        """Always return ellipsoid height - vertical datum conversion handled by heightStartingPoint."""
        return z_ellipsoid

    def _from_input_altitude(self, alt: float | None) -> float | None:
        """Always treat input as ellipsoid height - vertical datum conversion handled by heightStartingPoint."""
        return alt


class CoordinateSystemRegistry:
    """Registry for predefined coordinate systems that users can easily extend."""

    # To add a new convention, add one entry in PREDEFINED_SYSTEMS.
    # Dialogs and transformation lookups are generated from this registry.
    DEFAULT_COORDINATE_SYSTEM_KEY = "Lambert2008"
    CUSTOM_EPSG_PLACEHOLDER = "e.g. 3812 (Lambert2008) or 31370 (Lambert72)"

    # Standard coordinate systems - users can add more here
    PREDEFINED_SYSTEMS = {
        # Belgian systems
        "Lambert2008": {
            "epsg": 3812,
            "name": "Lambert2008 (EPSG:3812) - Belgium",
            "description": "ETRS89 / Belgian Lambert 2008 (typically used with ellipsoidal heights)",
            "unit": "meters",
            "datum": "ETRS89",
            "vertical_datum": "Ellipsoidal height",
            "aliases": [
                "Lambert 2008",
                "Belgian Lambert 2008",
                "LB08",
                "ETRS89 Lambert 2008",
                "EPSG:3812",
                "3812",
            ],
            "typical_regions": ["Belgium"]
        },
        "Lambert72": {
            "epsg": 31370,
            "name": "Lambert72 (EPSG:31370) - Belgium",
            "description": "Belgian Lambert 72 / Belge 1972",
            "unit": "meters",
            "datum": "BD72",
            "aliases": [
                "Lambert 72",
                "Belgian Lambert 72",
                "Belge 1972",
                "BD72",
                "EPSG:31370",
                "31370",
            ],
            "typical_regions": ["Belgium"]
        },

        # Geographic systems
        "WGS84": {
            "epsg": 4326,
            "name": "WGS84 (EPSG:4326) - Geographic",
            "description": "World Geodetic System 1984 - Global",
            "unit": "degrees",
            "datum": "WGS84",
            "aliases": [
                "WGS 84",
                "EPSG:4326",
                "4326",
            ],
            "typical_regions": ["Global"]
        }
    }
    
    # Vertical reference systems - simplified to only ellipsoid
    # Vertical datum conversion is now handled by heightStartingPoint values
    VERTICAL_REFERENCES = {
        "ellipsoid": {
            "enum": VerticalRef.ELLIPSOID,
            "name": "Ellipsoid Height",
            "description": "Height above reference ellipsoid - vertical datum handled by heightStartingPoint",
            "typical_use": "All applications (vertical datum conversion via flight export)"
        }
    }
    
    @classmethod
    def get_coordinate_systems(cls) -> List[Tuple[str, str]]:
        """Get list of (key, display_name) for coordinate systems."""
        systems = []
        for key, info in cls.PREDEFINED_SYSTEMS.items():
            systems.append((key, info["name"]))
        systems.append(("custom", "Custom EPSG..."))
        return systems

    @classmethod
    def get_default_coordinate_system_key(cls) -> str:
        """Return default CRS key used by dialogs and runtime fallbacks."""
        if cls.DEFAULT_COORDINATE_SYSTEM_KEY in cls.PREDEFINED_SYSTEMS:
            return cls.DEFAULT_COORDINATE_SYSTEM_KEY
        if cls.PREDEFINED_SYSTEMS:
            return next(iter(cls.PREDEFINED_SYSTEMS.keys()))
        return "WGS84"

    @classmethod
    def get_custom_epsg_placeholder(cls) -> str:
        """Return placeholder example text for custom EPSG input fields."""
        return cls.CUSTOM_EPSG_PLACEHOLDER
    
    @classmethod 
    def get_vertical_references(cls) -> List[Tuple[str, str]]:
        """Get list of (key, display_name) for vertical references."""
        return [(key, info["name"]) for key, info in cls.VERTICAL_REFERENCES.items()]
    
    @classmethod
    def get_system_info(cls, key: str) -> Optional[Dict]:
        """Get detailed information about a coordinate system."""
        if key in cls.PREDEFINED_SYSTEMS:
            return cls.PREDEFINED_SYSTEMS.get(key)
        resolved = cls.resolve_coordinate_system_key(key)
        if resolved and resolved != "custom":
            return cls.PREDEFINED_SYSTEMS.get(resolved)
        return None
    
    @classmethod
    def get_vertical_info(cls, key: str) -> Optional[Dict]:
        """Get detailed information about a vertical reference."""
        return cls.VERTICAL_REFERENCES.get(key)

    @staticmethod
    def _normalize_identifier(value: Any) -> str:
        """Normalize CRS label tokens for robust lookup."""
        return re.sub(r"[^a-z0-9]+", "", str(value).lower())

    @classmethod
    def get_key_by_epsg(cls, epsg_code: int) -> Optional[str]:
        """Resolve predefined system key by EPSG code."""
        try:
            epsg_int = int(epsg_code)
        except Exception:
            return None

        for key, info in cls.PREDEFINED_SYSTEMS.items():
            try:
                if int(info.get("epsg")) == epsg_int:
                    return key
            except Exception:
                continue
        return None

    @classmethod
    def resolve_coordinate_system_key(cls, value: Any) -> Optional[str]:
        """Resolve CRS key from key/name/alias/EPSG-style labels."""
        if value is None:
            return None

        if isinstance(value, (int, float)):
            return cls.get_key_by_epsg(int(value))

        raw = str(value).strip()
        if not raw:
            return None
        if raw.lower() == "custom":
            return "custom"

        upper = raw.upper()
        if upper.startswith("EPSG:"):
            epsg_text = upper.split(":", 1)[1].strip()
            if epsg_text.isdigit():
                return cls.get_key_by_epsg(int(epsg_text))
        if raw.isdigit():
            return cls.get_key_by_epsg(int(raw))

        target = cls._normalize_identifier(raw)
        for key, info in cls.PREDEFINED_SYSTEMS.items():
            tokens = [
                key,
                info.get("name", ""),
                str(info.get("epsg", "")),
                f"EPSG:{info.get('epsg', '')}",
            ]
            tokens.extend(info.get("aliases", []))
            for token in tokens:
                if token and cls._normalize_identifier(token) == target:
                    return key
        return None

    @classmethod
    def resolve_epsg(cls, value: Any, custom_epsg: Optional[int] = None) -> Optional[int]:
        """Resolve an EPSG integer from key/name/alias/custom inputs."""
        if value is None:
            return None

        if isinstance(value, (int, float)):
            try:
                return int(value)
            except Exception:
                return None

        raw = str(value).strip()
        if not raw:
            return None
        if raw.lower() == "custom":
            if custom_epsg is None:
                return None
            try:
                return int(custom_epsg)
            except Exception:
                return None

        upper = raw.upper()
        if upper.startswith("EPSG:"):
            raw = upper.split(":", 1)[1].strip()
        if raw.isdigit():
            return int(raw)

        key = cls.resolve_coordinate_system_key(raw)
        if key and key != "custom":
            info = cls.PREDEFINED_SYSTEMS.get(key)
            if info and info.get("epsg") is not None:
                try:
                    return int(info["epsg"])
                except Exception:
                    return None
        return None

    @classmethod
    def create_project_context(cls, coord_key: str, vertical_key: str, 
                              custom_epsg: Optional[int] = None, 
                              ground_elevation: float = 0.0) -> ProjectContext:
        """Create a ProjectContext from registry keys."""

        resolved_key = cls.resolve_coordinate_system_key(coord_key)

        # Handle coordinate system
        if resolved_key == "custom" or (isinstance(coord_key, str) and coord_key.strip().lower() == "custom"):
            if custom_epsg is None:
                raise ValueError("Custom EPSG code must be provided")
            epsg_code = custom_epsg
        else:
            epsg_code = cls.resolve_epsg(coord_key, custom_epsg=custom_epsg)
            if epsg_code is None:
                raise ValueError(f"Unknown coordinate system: {coord_key}")

        # Handle vertical reference - simplified to always use ellipsoid
        # Vertical datum conversion is now handled by heightStartingPoint values
        return ProjectContext.from_epsg(epsg_code, VerticalRef.ELLIPSOID, ground_elevation) 
