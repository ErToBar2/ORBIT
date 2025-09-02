from __future__ import annotations

"""Template management for cross-section images and default project data."""

import os
from pathlib import Path
from typing import Dict, Any


def get_resource_path() -> Path:
    """Return the path to the resources directory."""
    return Path(__file__).parent


def get_crosssection_templates() -> Dict[str, Path]:
    """Return available cross-section template images."""
    resource_dir = get_resource_path()
    templates = {}
    
    box_template = resource_dir / "crosssection_template_box.png"
    if box_template.exists():
        templates["box"] = box_template
        
    igirder_template = resource_dir / "crosssection_template_I-girder.png"
    if igirder_template.exists():
        templates["i-girder"] = igirder_template
        
    return templates


def get_default_project_data(bridge_type: str = "box") -> str:
    """Return default project configuration text based on bridge type."""
    if bridge_type.lower() == "i-girder":
        return """bridge_name = "DefaultBridge_IGirder"
trajectory_heights = [10, 12, 15]
input_scale_meters = 1
import_dir = "C:\\Code\\02 FlightPlanning\\01_BridgeData\\01_Input"
takeoff_altitude = 0
epsilonInput = 0.001
bridge_type = "i-girder"
bridge_width = 25.0

# Coordinate System Configuration
epsg_code = 4326
vertical_reference = "AGL"
ground_elevation = 0.0

# File Handling Configuration
supported_file_extensions = ["xlsx", "xls", "kml", "kmz", "txt", "csv"]
default_export_directory = "C:\\Code\\02 FlightPlanning\\01_BridgeData\\04_Export"
kmz_export_path = "{import_dir}/../04_Export"
"""
    else:  # box girder default
        return """bridge_name = "DefaultBridge_Box"
trajectory_heights = [8, 10, 12]
input_scale_meters = 1
import_dir = "C:\\Code\\02 FlightPlanning\\01_BridgeData\\01_Input"
takeoff_altitude = 0
epsilonInput = 0.001
bridge_type = "box"
bridge_width = 20.0

# Coordinate System Configuration
epsg_code = 4326
vertical_reference = "AGL"
ground_elevation = 0.0

# File Handling Configuration
supported_file_extensions = ["xlsx", "xls", "kml", "kmz", "txt", "csv"]
default_export_directory = "C:\\Code\\02 FlightPlanning\\01_BridgeData\\04_Export"
kmz_export_path = "{import_dir}/../04_Export"
"""


def get_default_flight_route_settings() -> str:
    """Return default flight route settings configuration."""
    return """# Flight Route Settings
# Photogrammetric flight:
flight_route_offset_V_base = 10
flight_route_offset_H_base = 5
photogrammetric_flight_angle = 0
order = ["101", "reverse 101", "102", "reverse 102", "underdeck_safe_flythrough", "201", "reverse 201", "202", "reverse 202"]

# Underdeck flights:
num_points = [3, 7, 3]  # Base points per section
horizontal_offsets_underdeck = [13, 13, 13]  # H_Offset of base points
height_offsets_underdeck = [[5.25, 5.5, 6], [6, 5.5, 5.25, 5, 5.25, 5.5, 6], [6, 5.55, 5.2]]  # Vertical offset from trajectory
general_height_offset = 1
thresholds_zones = [(10, 5), (7, 7), (5, 10)]  # Threshold distance
custom_zone_angles = []  # [2.16, 2.20, 2.24]  # Adjust angle

# Underdeck Planner Span Configuration
num_spans = 3
span_normal_enabled = [True, True, True]
span_axial_enabled = [False, False, False]
flythrough_mode = "Under-deck"  # "Under-deck", "Over-deck", "None"

# Safety Zones:
safety_zones_clearance = [[0,20],[0,20],[0,20],[0,20]]  # min, max local
safety_zones_clearance_adjust = [[20],[20],[20],[20]]  # adjust points inside zones. 0 = delete points, -1 find closest exit
default_safety_zone_z_min = 0
default_safety_zone_z_max = 50
safety_margin = 2.0

# Mission Builder Options
include_photogrammetry = True
include_underdeck = True
include_safety_zones = True
export_format = "KMZ"  # "KMZ", "KML", "CSV"

# GUI Slider Configuration
x_offset_range = [-50, 50]
y_offset_range = [-50, 50]
z_offset_range = [-20, 20]

# Export Modus:
heightMode = "relativeToStartPoint"  # or EGM96

# Additional features:
flythrough_underdeck_PF = True  # Not implemented
nsamplePointsTrajectory = 50  # smooth trajectory quadratically
perpendicular_distances = [0, 0, 0]  # Not implemented
connection_height = 20  # vertical flight height for connections
num_passes = 2  # num passes underdeck flights
safety_check_photo = 1
safety_check_underdeck = [[0],[0],[0]]  # 1 = execute safety check
safety_check_underdeck_axial = [[0],[0],[0]]  # 1 = execute safety check
n_girders = 5

standard_flight_routes = {
    "101": {"vertical_offset": 8, "distance_offset": 5},
    "102": {"vertical_offset": 3, "distance_offset": 2},
    "201": {"vertical_offset": 8, "distance_offset": 5},
    "202": {"vertical_offset": 3, "distance_offset": 2}
}

flight_speed_map = {
    "101": {"speed": "6"}, "102": {"speed": "4"},
    "201": {"speed": "6"}, "202": {"speed": "4"},
    "103": {"speed": "3"}, "203": {"speed": "3"},
    "104": {"speed": "3"}, "105": {"speed": "2"},
    "204": {"speed": "3"}, "205": {"speed": "2"},
    "underdeck_1": {"speed": "0.8"},
    "underdeck_2": {"speed": "1.0"},
    "underdeck_3": {"speed": "0.8"},
    "axial_underdeck_1": {"speed": "1.0"},
    "axial_underdeck_2": {"speed": "1.0"},
    "axial_underdeck_3": {"speed": "1.0"},
    "underdeck_safe_flythrough": {"speed": "2"}
}
"""


def create_default_input_folder(project_dir: Path, bridge_name: str) -> Path:
    """Create input folder structure with default files if needed."""
    input_dir = project_dir / bridge_name / "01_Input"
    input_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy appropriate template if no crosssection exists
    templates = get_crosssection_templates()
    crosssection_files = list(input_dir.glob(f"{bridge_name}_crosssection_edit.*"))
    
    if not crosssection_files and templates:
        # Use box template as default
        default_template = templates.get("box", next(iter(templates.values())))
        target_file = input_dir / f"{bridge_name}_crosssection_edit.png"
        
        # Copy template to target location
        import shutil
        shutil.copy2(default_template, target_file)
        
    return input_dir 