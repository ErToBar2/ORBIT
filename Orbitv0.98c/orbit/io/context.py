from __future__ import annotations

"""Project context encapsulating coordinate reference system + vertical datum.

This module provides global coordinate system functionality supporting any CRS.
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List, Tuple, Optional

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
    
    # Standard coordinate systems - users can add more here
    PREDEFINED_SYSTEMS = {
        # Geographic systems
        "WGS84": {
            "epsg": 4326,
            "name": "WGS84 (EPSG:4326) - Geographic",
            "description": "World Geodetic System 1984 - Global",
            "unit": "degrees",
            "typical_regions": ["Global"]
        },

        # European systems
        "Lambert72": {
            "epsg": 31370,
            "name": "Lambert72 (EPSG:31370) - Belgium",
            "description": "Belgian Lambert 72 / Belge 1972",
            "unit": "meters",
            "typical_regions": ["Belgium"]
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
    def get_vertical_references(cls) -> List[Tuple[str, str]]:
        """Get list of (key, display_name) for vertical references."""
        return [(key, info["name"]) for key, info in cls.VERTICAL_REFERENCES.items()]
    
    @classmethod
    def get_system_info(cls, key: str) -> Optional[Dict]:
        """Get detailed information about a coordinate system."""
        return cls.PREDEFINED_SYSTEMS.get(key)
    
    @classmethod
    def get_vertical_info(cls, key: str) -> Optional[Dict]:
        """Get detailed information about a vertical reference."""
        return cls.VERTICAL_REFERENCES.get(key)
    
    @classmethod
    def create_project_context(cls, coord_key: str, vertical_key: str, 
                              custom_epsg: Optional[int] = None, 
                              ground_elevation: float = 0.0) -> ProjectContext:
        """Create a ProjectContext from registry keys."""
        
        # Handle coordinate system
        if coord_key == "custom":
            if custom_epsg is None:
                raise ValueError("Custom EPSG code must be provided")
            epsg_code = custom_epsg
        else:
            system_info = cls.get_system_info(coord_key)
            if not system_info:
                raise ValueError(f"Unknown coordinate system: {coord_key}")
            epsg_code = system_info["epsg"]
        
        # Handle vertical reference - simplified to always use ellipsoid
        # Vertical datum conversion is now handled by heightStartingPoint values
        return ProjectContext.from_epsg(epsg_code, VerticalRef.ELLIPSOID, ground_elevation) 