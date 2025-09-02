from __future__ import annotations

"""Coordinate Reference System (CRS) utilities.

All coordinate transformations in Orbit go through this module so that we can
support arbitrary regional or global projections (UTM, national grids, etc.).
"""

from dataclasses import dataclass, field
from typing import Tuple

from pyproj import CRS, Transformer

# WGS84 is our canonical geographic reference
WGS84 = CRS.from_epsg(4326)


@dataclass
class CoordinateSystem:
    """A convenience wrapper around *pyproj* that caches forward/ inverse transformers.

    Parameters
    ----------
    epsg: int | str
        EPSG code of the *project* CRS (e.g. ``31370`` for Belgian Lambert 72).
    always_xy: bool, default ``True``
        Whether to enforce ``(lon, lat)`` axis order regardless of EPSG axis
        conventions. We pick *True* to stay consistent across libraries.
    """

    epsg: int | str
    always_xy: bool = True
    
    # These attributes are set in __post_init__ and need to be declared for slots=True
    crs: CRS = field(init=False)
    _fwd: Transformer = field(init=False)
    _inv: Transformer = field(init=False)

    def __post_init__(self) -> None:
        self.crs = CRS.from_user_input(self.epsg)
        self._fwd = Transformer.from_crs(WGS84, self.crs, always_xy=self.always_xy)
        self._inv = Transformer.from_crs(self.crs, WGS84, always_xy=self.always_xy)
    
    @classmethod
    def from_epsg(cls, epsg_code: int, always_xy: bool = True) -> "CoordinateSystem":
        """Create a CoordinateSystem from an EPSG code."""
        return cls(epsg_code, always_xy)

    # ---------------------------------------------------------------------
    # Transform helpers
    # ---------------------------------------------------------------------
    def to_project(self, lon: float, lat: float, z: float | None = None) -> Tuple[float, float, float | None]:
        """Transform a WGS84 coordinate to the project CRS."""
        if z is None:
            x, y = self._fwd.transform(lon, lat)
            return x, y, None
        x, y, z_out = self._fwd.transform(lon, lat, z)
        return x, y, z_out

    def to_wgs84(self, x: float, y: float, z: float | None = None) -> Tuple[float, float, float | None]:
        """Transform a project coordinate to WGS84."""
        if z is None:
            lon, lat = self._inv.transform(x, y)
            return lon, lat, None
        lon, lat, z_out = self._inv.transform(x, y, z)
        return lon, lat, z_out

    # ------------------------------------------------------------------
    # Convenience dunder methods
    # ------------------------------------------------------------------
    def __repr__(self) -> str:  # pragma: no cover
        axis = "lon/lat" if self.always_xy else "lat/lon"
        return f"CoordinateSystem(epsg={self.crs.to_epsg()}, axis_order={axis})" 