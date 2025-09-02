from __future__ import annotations

"""Generic data import utilities.

Supports Excel, KML/KMZ and plain-text CSV files that define bridge geometry.
Each loader converts raw input into Orbit domain objects *in the project CRS*.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Tuple, Type
import zipfile
import csv
import re

import numpy as np
import pandas as pd
from lxml import etree as ET

from .context import ProjectContext
from .models import Bridge, Pillar, Trajectory
from .crs import CoordinateSystem


# -----------------------------------------------------------------------------
# Loader registry
# -----------------------------------------------------------------------------
class BaseLoader(ABC):
    """Abstract base class for all import loaders."""

    extensions: Tuple[str, ...] = ()  # to be overridden like (".xlsx",)

    @classmethod
    def can_handle(cls, path: Path) -> bool:
        return path.suffix.lower() in cls.extensions

    @abstractmethod
    def load(self, path: Path, project: ProjectContext, input_cs: CoordinateSystem | None = None) -> Bridge:
        """Parse *path* and return a Bridge in the *project* coordinate system."""


# -----------------------------------------------------------------------------
# Excel loader
# -----------------------------------------------------------------------------
class ExcelLoader(BaseLoader):
    extensions = (".xls", ".xlsx")

    def load(self, path: Path, project: ProjectContext, input_cs: CoordinateSystem | None = None) -> Bridge:
        name = path.stem
        
        # Try to read Excel file and analyze all sheets
        excel_file = pd.ExcelFile(path)
        sheet_names = excel_file.sheet_names
        
        print(f"Excel file has {len(sheet_names)} sheets: {sheet_names}")
        
        # Look specifically for "00_Input" sheet first, then fallback to other sheets
        selected_sheet = None
        
        if "00_Input" in sheet_names:
            selected_sheet = "00_Input"
            print(f"Found target sheet: {selected_sheet}")
        else:
            # Fallback: analyze sheets to find one with coordinates
            sheet_analysis = {}
            for sheet_name in sheet_names:
                try:
                    df = pd.read_excel(path, sheet_name=sheet_name)
                    analysis = self._analyze_sheet_for_coordinates(df, sheet_name)
                    sheet_analysis[sheet_name] = analysis
                    
                    print(f"Sheet '{sheet_name}': {analysis['summary']}")
                    
                    # Priority selection for fallback
                    if not selected_sheet:
                        if "sortedgcp" in sheet_name.lower() or "gcp" in sheet_name.lower():
                            selected_sheet = sheet_name
                            print(f"Selected MOW-style sheet: {sheet_name}")
                        elif analysis['has_coordinates'] and analysis['data_points'] > 0:
                            selected_sheet = sheet_name
                            print(f"Selected coordinate sheet: {sheet_name}")
                
                except Exception as e:
                    print(f"Error reading sheet '{sheet_name}': {e}")
                    continue
            
            # If still no good sheet found, use first sheet
            if not selected_sheet and sheet_names:
                selected_sheet = sheet_names[0]
                print(f"Using first sheet as fallback: {selected_sheet}")
        
        if not selected_sheet:
            raise ValueError("No readable sheets found in Excel file")
        
        # Load the selected sheet
        df = pd.read_excel(path, sheet_name=selected_sheet)
        
        # Analyze the selected sheet if we haven't already
        if "00_Input" in sheet_names and selected_sheet == "00_Input":
            analysis = self._analyze_sheet_for_coordinates(df, selected_sheet)
        else:
            analysis = sheet_analysis.get(selected_sheet, {})
        
        print(f"Loading data from sheet: {selected_sheet}")
        
        # Handle different data formats
        if analysis.get('has_coordinates', False):
            return self._load_coordinate_data(df, name, analysis, project, input_cs)
        else:
            # Try to load as generic tabular data
            return self._load_generic_data(df, name, project, input_cs)
    
    def _analyze_sheet_for_coordinates(self, df: pd.DataFrame, sheet_name: str) -> dict:
        """Analyze a sheet to determine if it contains coordinate data."""
        analysis = {
            'sheet_name': sheet_name,
            'rows': len(df),
            'columns': list(df.columns),
            'has_coordinates': False,
            'coordinate_columns': {},
            'data_points': 0,
            'summary': '',
            'sample_data': []
        }
        
        if len(df) == 0:
            analysis['summary'] = "Empty sheet"
            return analysis
        
        # Check for coordinate columns with flexible matching
        coord_indicators = {
            'x': ['x', 'X', 'easting', 'lon', 'longitude', 'east'],
            'y': ['y', 'Y', 'northing', 'lat', 'latitude', 'north'],
            'z': ['z', 'Z', 'elevation', 'height', 'alt', 'altitude', 'elev'],
            'element': ['element', 'Element', 'type', 'Type', 'label', 'name']
        }
        
        found_coords = {}
        for coord_type, indicators in coord_indicators.items():
            for col in df.columns:
                col_str = str(col).lower()
                if any(indicator.lower() in col_str for indicator in indicators):
                    found_coords[coord_type] = col
                    break
        
        # Check if we have at least X and Y coordinates
        has_xy = 'x' in found_coords and 'y' in found_coords
        analysis['has_coordinates'] = has_xy
        analysis['coordinate_columns'] = found_coords
        
        if has_xy:
            # Count rows with valid coordinate data
            x_col, y_col = found_coords['x'], found_coords['y']
            valid_rows = 0
            for _, row in df.iterrows():
                try:
                    x_val = float(row[x_col])
                    y_val = float(row[y_col])
                    if not (pd.isna(x_val) or pd.isna(y_val)):
                        valid_rows += 1
                except:
                    continue
            
            analysis['data_points'] = valid_rows
            analysis['summary'] = f"{valid_rows} coordinate points with columns {list(found_coords.values())}"
        else:
            # Check for numeric columns that might be coordinates
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            if len(numeric_cols) >= 2:
                analysis['summary'] = f"{len(df)} rows, numeric columns: {numeric_cols[:3]}"
            else:
                analysis['summary'] = f"{len(df)} rows, no clear coordinate columns"
        
        # Get sample data
        if len(df) > 0:
            analysis['sample_data'] = df.head(3).to_dict('records')
        
        return analysis
    
    def _load_coordinate_data(self, df: pd.DataFrame, name: str, analysis: dict, 
                            project: ProjectContext, input_cs: CoordinateSystem | None) -> Bridge:
        """Load data when we've identified coordinate columns."""
        coord_cols = analysis['coordinate_columns']
        
        x_col = coord_cols['x']
        y_col = coord_cols['y']
        z_col = coord_cols.get('z', None)
        elem_col = coord_cols.get('element', None)
        
        # Extract coordinate data
        coords_data = []
        elements = []
        
        for _, row in df.iterrows():
            try:
                x_val = float(row[x_col])
                y_val = float(row[y_col])
                z_val = float(row[z_col]) if z_col and pd.notna(row[z_col]) else 0.0
                
                if pd.isna(x_val) or pd.isna(y_val):
                    continue
                
                coords_data.append([x_val, y_val, z_val])
                
                # Get element type if available
                if elem_col and pd.notna(row[elem_col]):
                    elements.append(str(row[elem_col]))
                else:
                    elements.append("trajectory")  # Default to trajectory
                    
            except (ValueError, TypeError):
                continue
        
        if not coords_data:
            raise ValueError("No valid coordinate data found")
        
        coords = np.array(coords_data)
        
        # Determine or use provided input CRS
        input_cs = input_cs or _guess_crs(coords)
        
        # Convert to project CRS and build models
        traj_points: List[np.ndarray] = []
        pillars: List[Pillar] = []
        
        for (x_val, y_val, z_val), elem in zip(coords, elements):
            x_proj, y_proj, z_proj = _transform_point(input_cs, project.crs, x_val, y_val, z_val)
            
            if "traj" in elem.lower() or "trajectory" in elem.lower():
                traj_points.append([x_proj, y_proj, z_proj])
            elif "pillar" in elem.lower() or "pier" in elem.lower():
                pid = f"{elem}-{len(pillars)+1}"
                pillars.append(Pillar(pid, x_proj, y_proj, z_proj))
            else:
                # Default to trajectory for unknown elements
                traj_points.append([x_proj, y_proj, z_proj])
        
        trajectory = Trajectory(np.asarray(traj_points)) if traj_points else Trajectory(np.empty((0, 3)))
        
        print(f"Loaded {len(traj_points)} trajectory points and {len(pillars)} pillars")
        
        return Bridge(name=name, trajectory=trajectory, pillars=pillars)
    
    def _load_generic_data(self, df: pd.DataFrame, name: str, 
                          project: ProjectContext, input_cs: CoordinateSystem | None) -> Bridge:
        """Fallback loader for sheets without clear coordinate columns."""
        print("Attempting to load as generic tabular data...")
        
        # Try to find numeric columns that might be coordinates
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        
        if len(numeric_cols) < 2:
            # No coordinate data - return empty bridge
            trajectory = Trajectory(np.empty((0, 3)))
            return Bridge(name=name, trajectory=trajectory, pillars=[])
        
        # Assume first 2-3 numeric columns are X, Y, [Z]
        x_col = numeric_cols[0]
        y_col = numeric_cols[1]
        z_col = numeric_cols[2] if len(numeric_cols) > 2 else None
        
        print(f"Using columns as coordinates: X={x_col}, Y={y_col}, Z={z_col}")
        
        # Extract data
        coords_data = []
        for _, row in df.iterrows():
            try:
                x_val = float(row[x_col])
                y_val = float(row[y_col])
                z_val = float(row[z_col]) if z_col and pd.notna(row[z_col]) else 0.0
                
                if pd.isna(x_val) or pd.isna(y_val):
                    continue
                    
                coords_data.append([x_val, y_val, z_val])
            except:
                continue
        
        if not coords_data:
            # Return empty bridge
            trajectory = Trajectory(np.empty((0, 3)))
            return Bridge(name=name, trajectory=trajectory, pillars=[])
        
        coords = np.array(coords_data)
        input_cs = input_cs or _guess_crs(coords)
        
        # Convert all points to trajectory (assume no pillars)
        traj_points = []
        for x_val, y_val, z_val in coords:
            x_proj, y_proj, z_proj = _transform_point(input_cs, project.crs, x_val, y_val, z_val)
            traj_points.append([x_proj, y_proj, z_proj])
        
        trajectory = Trajectory(np.asarray(traj_points))
        
        print(f"Loaded {len(traj_points)} trajectory points (generic format)")
        
        return Bridge(name=name, trajectory=trajectory, pillars=[])


# -----------------------------------------------------------------------------
# KML / KMZ loader
# -----------------------------------------------------------------------------
class KMLLoader(BaseLoader):
    extensions = (".kml", ".kmz")

    def load(self, path: Path, project: ProjectContext, input_cs: CoordinateSystem | None = None) -> Bridge:
        # Extract if KMZ
        kml_path = path
        if path.suffix.lower() == ".kmz":
            with zipfile.ZipFile(path, "r") as zf:
                # pick first .kml file
                for info in zf.infolist():
                    if info.filename.lower().endswith(".kml"):
                        data = zf.read(info.filename)
                        kml_path = Path(path.parent, "__tmp__.kml")
                        kml_path.write_bytes(data)
                        break
        tree = ET.parse(kml_path)
        root = tree.getroot()
        ns = {"kml": "http://www.opengis.net/kml/2.2"}
        coords_texts = root.xpath("//kml:coordinates", namespaces=ns)
        coords: List[Tuple[float, float, float]] = []
        for ct in coords_texts:
            lon, lat, *alt = map(float, ct.text.strip().split(","))
            z = alt[0] if alt else 0.0
            coords.append((lon, lat, z))

        if not coords:
            raise ValueError("No coordinates found in KML/KMZ file")

        # KML coordinates are always WGS-84 lon/lat.
        input_cs = CoordinateSystem(4326)

        # Convert and build models (assume they are trajectory points)
        traj_pts = []
        for lon, lat, z in coords:
            x, y, z_proj = _transform_point(input_cs, project.crs, lon, lat, z)
            traj_pts.append([x, y, z_proj])

        trajectory = Trajectory(np.asarray(traj_pts))
        return Bridge(name=path.stem, trajectory=trajectory, pillars=[])


class TextLoader(BaseLoader):
    extensions = (".txt", ".csv", ".dat", ".xyz", ".pts", ".tsv", "")  # include empty suffix

    @classmethod
    def can_handle(cls, path: Path) -> bool:
        ext = (path.suffix or "").lower()
        if ext in cls.extensions:
            return True
        # Heuristic: treat unknown ext as text if first lines contain at least 2 numbers
        try:
            head = path.read_text(encoding="utf-8", errors="ignore").splitlines()[:200]
            float_re = re.compile(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?')
            return sum(1 for ln in head if len(float_re.findall(ln)) >= 2) >= 3
        except Exception:
            return False

    def _split_labeled_sections(self, lines: list[str]) -> tuple[list[str], list[str]]:
        traj, pil = [], []
        current = None
        for raw in lines:
            line = raw.strip()
            if not line:
                continue
            key = line.lower()
            if key.startswith("trajectory"):
                current = "traj"; continue
            if key.startswith("pillars") or key.startswith("pillar"):
                current = "pil"; continue
            if current == "traj":
                traj.append(line)
            elif current == "pil":
                pil.append(line)
        return (traj, pil) if traj else ([], [])

    def _parse_any_format(self, lines: List[str]) -> List[List[float]]:
        """
        Universal tolerant parser:
        - accepts 2D or 3D: x y, x,y, x;y;z, x<TAB>y, [x y], (x,y,z), etc.
        - ignores comments after '#'
        - extracts numbers anywhere in the line
        """
        rows: List[List[float]] = []
        float_re = re.compile(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?')
        for raw in lines:
            line = raw.strip()
            if not line:
                continue
            if '#' in line:
                line = line.split('#', 1)[0].strip()
                if not line:
                    continue
            nums = [float(m.group(0)) for m in float_re.finditer(line)]
            if len(nums) >= 2:
                rows.append(nums[:3])  # keep up to 3 numbers
        return rows

    # legacy names delegate to the universal parser
    def _parse_bracket_format(self, lines: List[str]) -> List[List[float]]: return self._parse_any_format(lines)
    def _parse_csv_format(self,     lines: List[str]) -> List[List[float]]: return self._parse_any_format(lines)
    def _parse_space_format(self,   lines: List[str]) -> List[List[float]]: return self._parse_any_format(lines)

    def load(self, path: Path, project: ProjectContext, input_cs: CoordinateSystem | None = None) -> Bridge:
        print(f"Loading text file: {path}")
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()

        traj_section, pil_section = self._split_labeled_sections(lines)
        trajectory_rows: list[list[float]] = []
        pillar_rows: list[list[float]] = []

        if traj_section:
            #print("[TEXT_LOADER] Detected labelled TXT format (Trajectory / Pillars).")
            trajectory_rows = self._parse_any_format(traj_section)
            if pil_section:
                pillar_rows = self._parse_any_format(pil_section)

        if not trajectory_rows:
            for parser in (self._parse_any_format, self._parse_bracket_format, self._parse_csv_format, self._parse_space_format):
                try:
                    rows = parser(lines)
                    if rows:
                        trajectory_rows = rows
                        print(f"Successfully parsed {len(trajectory_rows)} coordinates using {parser.__name__}")
                        break
                except Exception as e:
                    print(f"Failed to parse with {parser.__name__}: {e}")
                    continue

        if not trajectory_rows:
            raise ValueError("No coordinate data found in text file")

        # pad Z where missing (z=0.0)
        trajectory_rows = [[r[0], r[1], (r[2] if len(r) > 2 else 0.0)] for r in trajectory_rows]
        if pillar_rows:
            pillar_rows = [[r[0], r[1], (r[2] if len(r) > 2 else 0.0)] for r in pillar_rows]

        # optional Swap X/Y from dialog (default False)
        swap_xy = bool(getattr(project, "swap_xy", False))
        if swap_xy:
            print("[TEXT_LOADER] Swapping X/Y coordinates as requested by user")
            print(f"[TEXT_LOADER] Before swap - First 5 trajectory points: {trajectory_rows[:5]}")
            if pillar_rows:
                print(f"[TEXT_LOADER] Before swap - First 5 pillar points: {pillar_rows[:5]}")

            trajectory_rows = [[y, x, z] for (x, y, z) in trajectory_rows]
            if pillar_rows:
                pillar_rows = [[y, x, z] for (x, y, z) in pillar_rows]

            print(f"[TEXT_LOADER] After swap - First 5 trajectory points: {trajectory_rows[:5]}")
            if pillar_rows:
                print(f"[TEXT_LOADER] After swap - First 5 pillar points: {pillar_rows[:5]}")
        else:
            print("[TEXT_LOADER] No X/Y swap requested, keeping original coordinate order")

        # Transform trajectory
        coords = np.asarray(trajectory_rows, dtype=float)
        input_cs = input_cs or _guess_crs(coords)

        traj_pts = []
        for x_in, y_in, z_in in coords:
            x, y, z_proj = _transform_point(input_cs, project.crs, float(x_in), float(y_in), float(z_in))
            traj_pts.append([x, y, z_proj])

        #print(f"[TEXT_LOADER] First transformed trajectory points (project CRS)")
        # for i, p in enumerate(traj_pts[:5]):
        #     print(f"  P{i+1:02d}: x={p[0]:.2f}, y={p[1]:.2f}, z={p[2]:.2f}")

        trajectory = Trajectory(np.asarray(traj_pts))

        # Transform pillars if present
        pillars: list[Pillar] = []
        if pillar_rows:
            for idx, (x_in, y_in, z_in) in enumerate(pillar_rows):
                x, y, z_proj = _transform_point(input_cs, project.crs, float(x_in), float(y_in), float(z_in))
                pillars.append(Pillar(id=f"TXT_P{idx+1}", x=x, y=y, z=z_proj))
            #print(f"[TEXT_LOADER] Parsed {len(pillars)} pillar points from labelled section")

        return Bridge(name=path.stem, trajectory=trajectory, pillars=pillars)

# -----------------------------------------------------------------------------
# Public factory
# -----------------------------------------------------------------------------
_LOADERS: List[Type[BaseLoader]] = [ExcelLoader, KMLLoader, TextLoader]


def load_bridge(
    file_path: str | Path,
    project: ProjectContext,
    input_epsg: int | str | None = None,
) -> Bridge:
    """Load *file_path* (any supported format) and convert to project CRS."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(path)

    # Build input coordinate system object if your loaders accept it; otherwise leave None.
    # Adjust factory to your codebase (e.g., CoordinateSystemRegistry / ProjectContext helpers).
    try:
        input_cs = CoordinateSystem(input_epsg) if input_epsg else None
    except Exception:
        input_cs = None

    ext = (path.suffix or "").lower()
    text_like_exts = {'.txt', '.csv', '.dat', '.xyz', '.pts', '.tsv', ''}

    # First try the registered loaders
    for loader_cls in _LOADERS:
        try:
            if hasattr(loader_cls, "can_handle") and loader_cls.can_handle(path):
                return loader_cls().load(path, project, input_cs)
        except Exception:
            # If a loader's can_handle explodes, ignore and try others
            continue

    # If no registry match, but the file is text-like, route to TextLoader explicitly
    if ext in text_like_exts:
        
        
        return TextLoader().load(path, project, input_cs)

    # As a last resort, try TextLoader when the content *looks* numeric, even with unknown ext
    try:
        head = path.read_text(encoding="utf-8", errors="ignore").splitlines()[:200]
        import re
        float_re = re.compile(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?')
        num_lines = sum(1 for ln in head if len(float_re.findall(ln)) >= 2)
        if num_lines >= 3:  # at least a few coordinate-like lines
            
            
            return TextLoader().load(path, project, input_cs)
    except Exception:
        pass

    raise ValueError(f"Unsupported file extension or format: {path.suffix or '(no extension)'}")


# -----------------------------------------------------------------------------
# Helper utilities
# -----------------------------------------------------------------------------

def _transform_point(source: CoordinateSystem, target: CoordinateSystem, x: float, y: float, z: float | None):
    lon, lat, z_tmp = source.to_wgs84(x, y, z)
    return target.to_project(lon, lat, z_tmp)


def _find_col(df: pd.DataFrame, candidates: set[str]) -> str:
    for c in df.columns:
        if c.lower() in candidates:
            return c
    raise ValueError(f"None of {candidates} columns found in Excel file")


def _guess_crs(coords: np.ndarray) -> CoordinateSystem:
    """Very rough heuristic: if all values fit lon/lat range, assume WGS84."""
    xs, ys = coords[:, 0], coords[:, 1]
    if (np.abs(xs) <= 180).all() and (np.abs(ys) <= 90).all():
        return CoordinateSystem(4326)  # WGS84 geo
    # Else we cannot guess; raise to prompt user
    raise ValueError("Cannot determine coordinate system automatically; please specify EPSG code")


def _identify_coordinate_columns(columns) -> Tuple[str, str, str]:
    """Identify X, Y, Z coordinate columns from DataFrame columns"""
    x_col = y_col = z_col = None
    
    columns_lower = [str(col).lower() for col in columns]
    
    # Look for X coordinate
    for i, col in enumerate(columns_lower):
        if any(keyword in col for keyword in ['x', 'east', 'easting']):
            x_col = columns[i]
            break
    
    # Look for Y coordinate
    for i, col in enumerate(columns_lower):
        if any(keyword in col for keyword in ['y', 'north', 'northing']):
            y_col = columns[i]
            break
    
    # Look for Z coordinate
    for i, col in enumerate(columns_lower):
        if any(keyword in col for keyword in ['z', 'elev', 'elevation', 'height', 'alt', 'altitude']):
            z_col = columns[i]
            break
    
    return x_col, y_col, z_col


def load_bridge_from_excel(file_path: Path, context: ProjectContext) -> Bridge:
    """Load bridge data from Excel file"""
    try:
        # Reduce debug output - only show essential info
        print(f"Loading bridge data from: {file_path.name}")
        
        # Read Excel file and find target sheet
        all_sheets = pd.read_excel(file_path, sheet_name=None, nrows=0)
        target_sheet = None
        
        # Look for "00_Input" sheet first, then try other sheets
        if "00_Input" in all_sheets:
            target_sheet = "00_Input"
            print(f"Found target sheet: {target_sheet}")
        else:
            # Try other sheets with likely names
            for sheet_name in all_sheets.keys():
                if any(keyword in sheet_name.lower() for keyword in ['input', 'data', 'coordinates', 'points']):
                    target_sheet = sheet_name
                    print(f"Using sheet: {target_sheet}")
                    break
            
            if not target_sheet:
                target_sheet = list(all_sheets.keys())[0]
                print(f"Using first sheet: {target_sheet}")
        
        # Load the data
        print(f"Loading data from sheet: {target_sheet}")
        df = pd.read_excel(file_path, sheet_name=target_sheet)
        
        # Parse the data with numbering interpretation
        trajectory_points, pillars = _parse_coordinate_data_with_numbering(df, context)
        
        # Essential output only
        print(f"Loaded {len(trajectory_points)} trajectory points and {len(pillars)} pillars")
        
        # Create trajectory from points
        if trajectory_points:
            trajectory_array = np.array(trajectory_points)
            trajectory = Trajectory(points=trajectory_array)
        else:
            # Create empty trajectory if no points
            trajectory = Trajectory(points=np.empty((0, 3)))
        
        # Create bridge
        bridge_name = file_path.stem.replace('_', ' ').title()
        bridge = Bridge(
            name=bridge_name,
            trajectory=trajectory,
            pillars=pillars
        )
        
        return bridge
        
    except Exception as e:
        print(f"Error loading Excel file: {e}")
        raise


def _parse_coordinate_data_with_numbering(df: pd.DataFrame, context: ProjectContext) -> Tuple[List[np.ndarray], List[Pillar]]:
    """
    Parse coordinate data with numbering interpretation logic:
    - First digit: side (1 = right, 2 = left)
    - Second digit: component (1 = abutment, 2 = superstructure, 3 = pillar)
    - Digits 3-4: sequential numbers
    Example: 1301, 2301 are right and left points of first pillar
    """
    trajectory_points = []
    pillars = []
    
    # Find coordinate columns
    x_col, y_col, z_col = _identify_coordinate_columns(df.columns)
    
    if not x_col or not y_col:
        print("Warning: Could not identify coordinate columns")
        return trajectory_points, pillars
    
    # Find numbering column (nr., number, etc.)
    nr_col = None
    print(f"[DEBUG] Available columns: {list(df.columns)}")
    for col in df.columns:
        col_lower = str(col).lower()
        print(f"[DEBUG] Checking column '{col}' (lower: '{col_lower}')")
        if any(keyword in col_lower for keyword in ['nr', 'number', 'num', 'id']):
            nr_col = col
            print(f"[DEBUG] Found numbering column: {nr_col}")
            break
    
    if not nr_col:
        print("Warning: Could not find numbering column")
        print(f"[DEBUG] Searched for keywords: ['nr', 'number', 'num', 'id'] in columns: {list(df.columns)}")
        # Fall back to simple sequential numbering
        return _parse_coordinate_data_simple(df, context)
    
    print(f"Using columns: X={x_col}, Y={y_col}, Z={z_col}, Nr={nr_col}")
    
    # Debug: Show sample data from numbering column
    print(f"[DEBUG] Sample values from {nr_col}: {df[nr_col].head().tolist()}")
    
    # Group points by numbering logic
    pillar_points = {}        # {seq: {'right':pt,'left':pt}}
    abutment_pairs = {}       # {seq: {'right':pt,'left':pt}}
    superstructure_pairs = {} # {seq: {'right':pt,'left':pt}}
    
    for idx, row in df.iterrows():
        try:
            # Get coordinates
            x = float(row[x_col])
            y = float(row[y_col])
            z = float(row[z_col]) if z_col and pd.notna(row[z_col]) else 0.0
            
            # Parse numbering: clean to digits only (handles values like 1301.0)
            raw_val = str(row[nr_col]).strip()
            nr_value = "".join(ch for ch in raw_val if ch.isdigit())
            if len(nr_value) < 4:
                # Not enough digits for our scheme – skip
                continue

            side = int(nr_value[0])        # 1 = right, 2 = left
            component = int(nr_value[1])   # 1 = abutment, 2 = superstructure, 3 = pillar
            sequence = int(nr_value[2:4])  # sequence ID
            
            point = np.array([x, y, z])
            
            if component == 1:  # Abutment
                if sequence not in abutment_pairs:
                    abutment_pairs[sequence] = {}
                abutment_pairs[sequence]['right' if side == 1 else 'left'] = point
            elif component == 2:  # Superstructure (centreline)
                if sequence not in superstructure_pairs:
                    superstructure_pairs[sequence] = {}
                superstructure_pairs[sequence]['right' if side == 1 else 'left'] = point
            elif component == 3:  # Pillar
                if sequence not in pillar_points:
                    pillar_points[sequence] = {}
                pillar_points[sequence]['right' if side == 1 else 'left'] = point
                
        except (ValueError, IndexError) as e:
            print(f"Warning: Could not parse row {idx}: {e}")
            continue
    
    # ---- Build trajectory & debug ----
    trajectory_points = []
    for seq in sorted(superstructure_pairs.keys()):
        pair = superstructure_pairs[seq]
        if 'right' in pair and 'left' in pair:
            mid = (pair['right'] + pair['left']) / 2
            trajectory_points.append(mid)
        else:
            # fallback: single point (whichever side)
            trajectory_points.append(next(iter(pair.values())))
    
    # Create pillars from pillar points
    for pillar_id in sorted(pillar_points.keys()):
        pillar_data = pillar_points[pillar_id]
        
        # Create pillar if we have both right and left points
        if 'right' in pillar_data and 'left' in pillar_data:
            # Calculate center point of pillar
            right_pt = pillar_data['right']
            left_pt = pillar_data['left']
            center = (right_pt + left_pt) / 2
            
            pillar = Pillar(
                id=f"Pillar_{pillar_id}",
                x=center[0],
                y=center[1],
                z=center[2]
            )
            pillars.append(pillar)
        else:
            print(f"Warning: Incomplete pillar data for pillar {pillar_id}")
    
    # Debug prints
    print(f"[DEBUG] Total superstructure pairs: {len(superstructure_pairs)} -> Trajectory points: {len(trajectory_points)}")
    print(f"[DEBUG] Total pillar pairs found: {len(pillar_points)}")
    print(f"[DEBUG] Total abutment pairs found: {len(abutment_pairs)}")
    print(f"[DEBUG] trajectory: {[pt.tolist() for pt in trajectory_points]}")
    
    return trajectory_points, pillars


def _parse_coordinate_data_simple(df: pd.DataFrame, context: ProjectContext) -> Tuple[List[np.ndarray], List[Pillar]]:
    """Simple fallback parsing without numbering logic"""
    trajectory_points = []
    
    # Find coordinate columns
    x_col, y_col, z_col = _identify_coordinate_columns(df.columns)
    
    if not x_col or not y_col:
        return trajectory_points, []
    
    for idx, row in df.iterrows():
        try:
            x = float(row[x_col])
            y = float(row[y_col])
            z = float(row[z_col]) if z_col and pd.notna(row[z_col]) else 0.0
            
            point = np.array([x, y, z])
            trajectory_points.append(point)
            
        except (ValueError, TypeError):
            continue
    
    return trajectory_points, []


def _separate_structural_components(df: pd.DataFrame) -> Tuple[dict, dict, dict]:
    """Return three dictionaries: abutment_pairs, superstructure_pairs, pillar_pairs.

    Each dict maps *sequence* -> {'right': np.ndarray, 'left': np.ndarray}
    Only rows having at least X & Y (and optional Z) and a 4-digit number are considered.
    """
    # Identify coordinate columns first
    x_col, y_col, z_col = _identify_coordinate_columns(df.columns)
    if not x_col or not y_col:
        raise ValueError("Could not identify X/Y coordinate columns in sheet")

    abut_pairs: dict[int, dict[str, np.ndarray]] = {}
    super_pairs: dict[int, dict[str, np.ndarray]] = {}
    pillar_pairs: dict[int, dict[str, np.ndarray]] = {}

    # determine nr column
    nr_col = None
    for col in df.columns:
        if any(k in str(col).lower() for k in ["nr", "number", "num", "id"]):
            nr_col = col
            break
    if not nr_col:
        raise ValueError("No numbering column (nr./id) found in sheet")

    for _, row in df.iterrows():
        raw_val = str(row[nr_col]).strip()
        nr_digits = "".join(ch for ch in raw_val if ch.isdigit())
        if len(nr_digits) < 4:
            continue

        side = int(nr_digits[0])          # 1 right, 2 left
        component = int(nr_digits[1])      # 1 abut, 2 super, 3 pillar
        seq = int(nr_digits[2:4])

        try:
            x = float(row[x_col]); y = float(row[y_col])
            z = float(row[z_col]) if z_col and pd.notna(row[z_col]) else 0.0
        except ValueError:
            continue

        pt = np.array([x, y, z])

        target = {1: abut_pairs, 2: super_pairs, 3: pillar_pairs}.get(component)
        if target is None:
            continue

        if seq not in target:
            target[seq] = {}
        target[seq]['right' if side == 1 else 'left'] = pt 

    return abut_pairs, super_pairs, pillar_pairs 