#!/usr/bin/env python3
"""
ORBIT Flight Route Exporter
============================

Unified KMZ export system for ORBIT flight planning that handles:
- Coordinate transformations from local metric to WGS84
- DJI WPML compliant KMZ file generation
- Configuration dialog for export parameters
- Both overview and underdeck flight route export

Author: ORBIT Flight Planning System
"""

import os
import zipfile
import math
import re
from lxml import etree as ET
from datetime import datetime
import time
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any

from PySide6.QtWidgets import (
    QMessageBox, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QComboBox, QPushButton, QSpinBox, QDoubleSpinBox, QCheckBox, QFileDialog
)

# Debug control functions - use the same pattern as main app
def debug_print(*args, **kwargs) -> None:
    """Print function that only outputs when DEBUG is True."""
    # Import DEBUG from main app context
    try:
        from .data_parser import DEBUG_PRINT
        if DEBUG_PRINT:
            print(*args, **kwargs)
    except ImportError:
        # Fallback: use main app's DEBUG if available
        try:
            import sys
            main_module = sys.modules.get('__main__')
            if hasattr(main_module, 'DEBUG') and main_module.DEBUG:
                print(*args, **kwargs)
        except:
            pass  # Silent fallback

def error_debug_print(*args, **kwargs) -> None:
    """Print function that always outputs (for errors)."""
    print(*args, **kwargs)


class FlightExportDialog(QDialog):
    """Dialog for configuring flight route export parameters."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Flight Route Export Configuration")
        self.setModal(True)
        self.resize(400, 300)  # Reduced height since we removed drone/payload dropdowns
        
        # Export configuration defaults
        self.config = {
            "height_mode": "EGM96",
            "global_speed": 2.0,
            "takeoff_security_height": 30.0,
            "min_altitude": 2.0,
            "adjust_low_altitudes": True,
            "export_combined_route": True
        }
        
        self._setup_ui()
        
    def _setup_ui(self):
        """Setup the UI for the export dialog."""
        layout = QVBoxLayout()
        
        # Height Mode
        height_layout = QHBoxLayout()
        height_layout.addWidget(QLabel("Height Mode:"))
        self.height_combo = QComboBox()
        self.height_combo.addItems([
            "EGM96",
            "relativeToStartPoint", 
            "ellipsoidHeight"
        ])
        self.height_combo.setCurrentText("EGM96")  # Default to EGM96
        height_layout.addWidget(self.height_combo)
        layout.addLayout(height_layout)
        
        # Height Mode Description
        height_desc = QLabel("EGM96: Heights in EGM96 datum\nrelativeToStartPoint: Heights relative to starting point (AGL)\nellipsoidHeight: Heights in WGS84 ellipsoid")
        height_desc.setStyleSheet("color: gray; font-size: 10px;")
        layout.addWidget(height_desc)
        
        # Note about drone and payload values
        info_label = QLabel("Note: Drone and payload values are automatically loaded from the parsed data")
        info_label.setStyleSheet("color: blue; font-size: 10px; font-style: italic;")
        layout.addWidget(info_label)
        
        # Flight Speed
        speed_layout = QHBoxLayout()
        speed_layout.addWidget(QLabel("Global Speed (m/s):"))
        self.speed_spin = QDoubleSpinBox()
        self.speed_spin.setRange(0.1, 15.0)
        self.speed_spin.setValue(2.0)
        self.speed_spin.setSingleStep(0.1)
        speed_layout.addWidget(self.speed_spin)
        layout.addLayout(speed_layout)
        
        # Minimum Altitude
        min_alt_layout = QHBoxLayout()
        min_alt_layout.addWidget(QLabel("Minimum Altitude (m):"))
        self.min_alt_spin = QDoubleSpinBox()
        self.min_alt_spin.setRange(0.5, 10.0)
        self.min_alt_spin.setValue(2.0)
        self.min_alt_spin.setSingleStep(0.1)
        min_alt_layout.addWidget(self.min_alt_spin)
        layout.addLayout(min_alt_layout)
        
        # Checkboxes
        self.adjust_check = QCheckBox("Auto-adjust altitudes below minimum")
        self.adjust_check.setChecked(True)
        layout.addWidget(self.adjust_check)
        
        self.combined_check = QCheckBox("Export combined route")
        self.combined_check.setChecked(True)
        layout.addWidget(self.combined_check)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        export_btn = QPushButton("Export KMZ")
        export_btn.clicked.connect(self.accept)
        button_layout.addWidget(export_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def get_config(self):
        """Get the current configuration from the dialog."""
        self.config.update({
            "height_mode": self.height_combo.currentText(),
            "global_speed": self.speed_spin.value(),
            "min_altitude": self.min_alt_spin.value(),
            "adjust_low_altitudes": self.adjust_check.isChecked(),
            "export_combined_route": self.combined_check.isChecked()
        })
        return self.config


class OrbitFlightExporter:
    """
    Unified flight route exporter for ORBIT with DJI WPML compliance.
    
    This class handles:
    - Coordinate transformation from local metric to WGS84
    - KMZ file generation with DJI WPML structure
    - Both overview and underdeck flight route export
    - Configuration management and validation
    """
    
    def __init__(self, app_instance, config: Dict[str, Any] = None):
        """
        Initialize the flight exporter.
        
        Args:
            app_instance: Reference to the main ORBIT application
            config: Export configuration dictionary (optional)
        """
        self.app = app_instance
        self.config = config or self._get_default_config()
        self.export_paths = []
        self.flight_speed_map = {}
        self.WPML_NS = "http://www.dji.com/wpmz/1.0.3"
        self.KML_NS  = "http://www.opengis.net/kml/2.2"
        # Load configuration from app instance if available
        self._load_app_configuration()
        
        # Set enum values based on parsed data
        self._update_enum_values()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default export configuration."""
        return {
            "height_mode": "EGM96",
            "global_speed": 2.0,
            "takeoff_security_height": 30.0,
            "min_altitude": 2.0,
            "adjust_low_altitudes": True,
            "export_combined_route": True
        }
    
    def _load_app_configuration(self):
        """Load drone enum, payload enum, flight speed mapping, and height information from app parsed data."""
        if not self.app or not hasattr(self.app, "parsed_data") or not self.app.parsed_data:
            return
            
        flight_data = self.app.parsed_data.get("flight_routes", {})
        
        # Get droneEnumValue from parsed data
        drone_enum = flight_data.get("droneEnumValue")
        if drone_enum is not None:
            self.config["drone_enum_value"] = str(drone_enum)
            debug_print(f"   🚁 Using droneEnumValue from parsed data: {drone_enum}")
        else:
            debug_print("   ⚠️  No droneEnumValue found in parsed data")
        
        # Get payloadEnumValue from parsed data
        payload_enum = flight_data.get("payloadEnumValue")
        if payload_enum is not None:
            self.config["payload_enum_value"] = str(payload_enum)
            debug_print(f"   📷 Using payloadEnumValue from parsed data: {payload_enum}")
        else:
            debug_print("   ⚠️  No payloadEnumValue found in parsed data")
        
        # Get flight speed mapping
        self.flight_speed_map = flight_data.get("flight_speed_map", {})
        if self.flight_speed_map:
            debug_print(f"   🚀 Loaded flight speed map with {len(self.flight_speed_map)} routes")
        
        # Load height mode and starting point information
        self.config["height_mode"] = flight_data.get("heightMode", self.config.get("height_mode", "EGM96"))
        self.starting_point_ellipsoid = flight_data.get("heightStartingPoint_Ellipsoid")
        self.starting_point_absolute = flight_data.get("heightStartingPoint_Reference")

        # Load global waypoint turn mode
        self.global_waypoint_turn_mode = flight_data.get("globalWaypointTurnMode", "toPointAndStopWithDiscontinuityCurvature")

        # Debug: Show loaded values
        debug_print(f"   📍 Starting point Ellipsoid height: {self.starting_point_ellipsoid}m")
        debug_print(f"   📍 Starting point Absolute height: {self.starting_point_absolute}m")
        debug_print(f"   📏 Initial height mode: {self.config['height_mode']}")
        debug_print(f"   🔄 Global waypoint turn mode: {self.global_waypoint_turn_mode}")
        debug_print(f"   🔍 Raw flight_data keys: {list(flight_data.keys()) if flight_data else 'None'}")

        # Note: Automatic fallback logic is handled in _calculate_waypoint_height()
        
        # Load bridge name and project directory if available
        project_data = self.app.parsed_data.get("project", {})
        if project_data:
            self.config["bridge_name"] = project_data.get("bridge_name", "Bridge")
            self.config["project_dir_base"] = project_data.get("project_dir_base", ".")
    
    def _update_enum_values(self):
        """Update drone and payload enum values based on parsed data or use defaults."""
        # Use parsed values if available, otherwise use defaults
        if "drone_enum_value" not in self.config:
            self.config["drone_enum_value"] = "77"  # Default to M3E
            debug_print("   🚁 Using default droneEnumValue: 77 (M3E)")
        
        if "payload_enum_value" not in self.config:
            self.config["payload_enum_value"] = "66"  # Default to L1
            debug_print("   📷 Using default payloadEnumValue: 66 (L1)")
    
    def _calculate_waypoint_height(self, waypoint_alt: float, waypoint_tag: str = "") -> tuple[float, float]:
        """
        Calculate the proper height values for a waypoint based on height mode and starting point information.

        This method implements the universal altitude strategy:
        - Always prefer ellipsoid mode (DJI "EGM96") for reliability
        - Handle any input coordinate system by linking to ellipsoid starting height
        - Fall back to relativeToStartPoint only when ellipsoid data is unavailable

        Args:
            waypoint_alt: The waypoint altitude from the route data (includes all offsets)
            waypoint_tag: Waypoint tag for debugging

        Returns:
            tuple: (height, ellipsoid_height) - both values are the same for DJI WPML
        """
        height_mode = self.config.get("height_mode", "EGM96")

        # Universal altitude strategy with automatic fallback
        if hasattr(self, 'starting_point_ellipsoid') and self.starting_point_ellipsoid is not None:
            # We have ellipsoid starting point

            if self.starting_point_ellipsoid == 0:
                # Ellipsoid height is 0 - this is invalid for ellipsoid mode, fallback to relative
                debug_print(f"   ⚠️ Ellipsoid height is 0 - falling back to relativeToStartPoint mode")
                debug_print(f"   📊 Relative mode: waypoint {waypoint_tag} alt={waypoint_alt}m (relative to starting point)")
                self.config["height_mode"] = "relativeToStartPoint"
                return waypoint_alt, waypoint_alt
            else:
                # Valid ellipsoid height - use ellipsoid mode (DJI "EGM96")
                if hasattr(self, 'starting_point_absolute') and self.starting_point_absolute is not None:
                    # Full information available - apply universal formula
                    ellipsoid_height = waypoint_alt + self.starting_point_ellipsoid - self.starting_point_absolute
                    debug_print(f"   📊 Universal ellipsoid: waypoint {waypoint_tag} orig={waypoint_alt}m + ellipsoid={self.starting_point_ellipsoid}m - reference={self.starting_point_absolute}m = {ellipsoid_height}m")
                else:
                    # Only ellipsoid available - assume waypoint is relative to ellipsoid
                    ellipsoid_height = waypoint_alt + self.starting_point_ellipsoid
                    debug_print(f"   📊 Ellipsoid only: waypoint {waypoint_tag} orig={waypoint_alt}m + ellipsoid={self.starting_point_ellipsoid}m = {ellipsoid_height}m")

                self.config["height_mode"] = "EGM96"
                return ellipsoid_height, ellipsoid_height

        else:
            # No ellipsoid information - fall back to relativeToStartPoint mode
            debug_print(f"   ⚠️ No ellipsoid starting point - falling back to relativeToStartPoint mode")
            debug_print(f"   📊 Relative mode: waypoint {waypoint_tag} alt={waypoint_alt}m (relative to starting point)")

            # Set height mode to relative
            self.config["height_mode"] = "relativeToStartPoint"
            return waypoint_alt, waypoint_alt
    
    def export_with_dialog(self, parent=None) -> List[str]:
        """
        Export flight routes with a configuration dialog.
        
        Args:
            parent: Parent widget for dialog
            
        Returns:
            List of exported file paths
        """
        # Show configuration dialog
        dialog = FlightExportDialog(parent)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            debug_print("📤 Flight route export cancelled by user")
            return []
        
        # Update configuration with dialog values
        self.config.update(dialog.get_config())
        
        # Get output directory
        output_dir = QFileDialog.getExistingDirectory(
            parent,
            "Select Output Directory for KMZ Files",
            str(Path.home() / "Desktop")
        )
        
        if not output_dir:
            debug_print("📤 Export cancelled - no output directory selected")
            return []
        
        return self.export_all_routes(output_dir)
    
    def export_all_routes(self, output_directory: str) -> List[str]:
        """
        Export all available flight routes to KMZ format.
        
        Args:
            output_directory: Directory to save KMZ files
            
        Returns:
            List of exported file paths
        """
        debug_print("\n" + "="*60)
        debug_print("🚀 ORBIT FLIGHT ROUTE EXPORT")
        debug_print("="*60)
        
        output_dir = Path(output_directory)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        self.export_paths = []
        
        # Get bridge name for file naming
        bridge_name = self._get_bridge_name()
        
        # Export overview routes
        if hasattr(self.app, "overview_flight_waypoints") and self.app.overview_flight_waypoints:
            self._export_route_type("overview", self.app.overview_flight_waypoints, 
                                  bridge_name, output_dir)
        else:
            debug_print("⚠️  No overview flight waypoints found")
        
        # Export underdeck routes (handles split vs combined logic)
        if hasattr(self.app, "underdeck_flight_waypoints") and self.app.underdeck_flight_waypoints:


            self._export_underdeck_routes(self.app.underdeck_flight_waypoints,
                                        bridge_name, output_dir)
        else:
            debug_print("⚠️  No underdeck flight waypoints found")
        

        
        debug_print(f"\n✅ Exported {len(self.export_paths)} KMZ files:")
        for path in self.export_paths:
            debug_print(f"   📄 {Path(path).name}")
        
        return self.export_paths
    
    def _export_route_type(self, route_type: str, waypoints: List[List],
                          bridge_name: str, output_dir: Path):
        """Export a specific route type (overview or underdeck)."""
        debug_print(f"📤 Exporting {route_type} flight routes...")

        # Transform to WGS84
        wgs84_waypoints = self._transform_to_wgs84(waypoints)
        if not wgs84_waypoints:
            debug_print(f"❌ Failed to transform {route_type} waypoints")
            return

        # Check if we need separate left/right exports for overview routes
        if route_type == "overview" and self._should_export_separate_sides():
            self._export_overview_separate_sides(wgs84_waypoints, bridge_name, output_dir)
        elif self.config["export_combined_route"]:
            # Export combined route
            route_name = f"{route_type.title()} Flight"
            filename = f"{bridge_name}_{route_type.title()}_Combined.kmz"
            filepath = output_dir / filename
            self._create_kmz_file(wgs84_waypoints, route_name, filepath)
            self.export_paths.append(str(filepath))

    def _should_export_separate_sides(self) -> bool:
        """Check if overview routes should be exported as separate left/right KMZ files."""
        if not hasattr(self.app, "parsed_data") or not self.app.parsed_data:
            return False

        flight_data = self.app.parsed_data.get("flight_routes", {})
        transition_mode = flight_data.get("transition_mode", 1)
        return transition_mode == 0  # Mode 0 = separate sides

    def _export_overview_separate_sides(self, waypoints: List[List], bridge_name: str, output_dir: Path):
        """Export overview routes as separate left and right side KMZ files."""
        debug_print("📋 Exporting overview routes as separate left/right KMZ files...")

        # Separate waypoints by side based on their tags
        left_waypoints = []
        right_waypoints = []
        transition_waypoints = []

        for waypoint in waypoints:
            if len(waypoint) >= 4:
                tag = waypoint[3]
                if tag in ["101", "102", "103", "104", "105", "106", "107", "108", "109", "110"]:  # Left side routes
                    left_waypoints.append(waypoint)
                elif tag in ["201", "202", "203", "204", "205", "206", "207", "208", "209", "210"]:  # Right side routes
                    right_waypoints.append(waypoint)
                elif tag == "transition":  # Transition waypoints
                    transition_waypoints.append(waypoint)

        debug_print(f"   📊 Left side waypoints: {len(left_waypoints)}")
        debug_print(f"   📊 Right side waypoints: {len(right_waypoints)}")
        debug_print(f"   📊 Transition waypoints: {len(transition_waypoints)}")

        # Export left side routes (physically positioned on right side of bridge)
        if left_waypoints:
            route_name = "Overview Flight - Bridge Right Side"
            filename = f"{bridge_name}_Overview_Right.kmz"
            filepath = output_dir / filename
            self._create_kmz_file(left_waypoints, route_name, filepath)
            self.export_paths.append(str(filepath))
            debug_print(f"   ✅ Exported left routes as right side: {filename}")

        # Export right side routes (physically positioned on left side of bridge)
        if right_waypoints:
            route_name = "Overview Flight - Bridge Left Side"
            filename = f"{bridge_name}_Overview_Left.kmz"
            filepath = output_dir / filename
            self._create_kmz_file(right_waypoints, route_name, filepath)
            self.export_paths.append(str(filepath))
            debug_print(f"   ✅ Exported right routes as left side: {filename}")

        # Note: Transition waypoints are typically not used in mode 0 (separate sides)

    def _export_underdeck_routes(self, waypoints: List[List], bridge_name: str, output_dir: Path):
        """Export underdeck routes with split logic based on underdeck_split parameter."""
        debug_print(f"📤 Exporting underdeck flight routes...")



        # Separate axial routes from regular underdeck routes
        underdeck_waypoints, axial_waypoints = self._separate_underdeck_and_axial_routes(waypoints)
        
        # Export regular underdeck routes
        if underdeck_waypoints:
            underdeck_split = self._get_underdeck_split_parameter()

            if underdeck_split == 0:
                # Export as combined route
                debug_print("   🔗 Exporting underdeck routes as combined route")
                self._export_route_type("underdeck", underdeck_waypoints, bridge_name, output_dir)
            else:
                # Export per section
                debug_print("   📋 Exporting underdeck routes per section")
                self._export_underdeck_routes_by_section(underdeck_waypoints, bridge_name, output_dir)
        else:
            debug_print("   ⚠️  No regular underdeck routes found")
        
        # Export axial routes separately
        if axial_waypoints:
            debug_print("   🔧 Exporting axial underdeck routes")
            self._export_axial_routes_by_section(axial_waypoints, bridge_name, output_dir)
        else:
            debug_print("   ⚠️  No axial routes found")
    
    def _separate_underdeck_and_axial_routes(self, waypoints: List[List]) -> Tuple[List[List], List[List]]:
        """Separate underdeck and axial routes based on their tags."""


        underdeck_waypoints = []
        axial_waypoints = []

        for waypoint in waypoints:
            if len(waypoint) >= 4:
                tag = waypoint[3]
                if tag.startswith("axial_"):
                    axial_waypoints.append(waypoint)
                else:
                    underdeck_waypoints.append(waypoint)
            else:
                # Fallback: assume it's a regular underdeck route
                underdeck_waypoints.append(waypoint)

        debug_print(f"   📊 Separated routes: {len(underdeck_waypoints)} underdeck, {len(axial_waypoints)} axial")

        return underdeck_waypoints, axial_waypoints
    
    def _get_underdeck_split_parameter(self) -> int:
        """Get the underdeck_split parameter from parsed data."""
        if hasattr(self.app, "parsed_data") and self.app.parsed_data:
            flight_data = self.app.parsed_data.get("flight_routes", {})
            return flight_data.get("underdeck_split", 1)
        return 1  # Default to split mode
    
    def _export_underdeck_routes_by_section(self, waypoints: List[List], bridge_name: str, output_dir: Path):
        """Export underdeck routes separated by their section tags."""
        # Group waypoints by section tag
        sections = {}
        for waypoint in waypoints:
            if len(waypoint) >= 4:
                tag = waypoint[3]
                # Extract section number from tag (supports both old and new tag formats)
                section_num = None

                # Handle connection tags (e.g., "connection_right_span1")
                if tag.startswith("connection_") and "span" in tag:
                    # Extract span number from connection tags
                    span_part = tag.split("span")[1]
                    section_num = span_part.split("_")[0] if "_" in span_part else span_part

                # Handle underdeck tags (e.g., "underdeck_span1_base1_pass1")
                elif tag.startswith("underdeck_") and "span" in tag:
                    # Extract span number from underdeck tags
                    span_part = tag.split("span")[1]
                    section_num = span_part.split("_")[0] if "_" in span_part else span_part

                # Handle legacy format (e.g., "underdeck_1")
                elif tag.startswith("underdeck_"):
                    section_num = tag.split("_")[1] if "_" in tag else "1"

                if section_num:
                    if section_num not in sections:
                        sections[section_num] = []
                    sections[section_num].append(waypoint)
        
        # Export each section separately
        for section_num, section_waypoints in sections.items():
            if len(section_waypoints) > 1:  # Only export if more than 1 waypoint
                route_name = f"Underdeck Section {section_num}"
                filename = f"{bridge_name}_Underdeck_Section_{section_num}.kmz"
                filepath = output_dir / filename
                
                # Transform to WGS84
                wgs84_waypoints = self._transform_to_wgs84(section_waypoints)
                if wgs84_waypoints:
                    self._create_kmz_file(wgs84_waypoints, route_name, filepath)
                    self.export_paths.append(str(filepath))
                    debug_print(f"   ✅ Exported section {section_num}: {len(section_waypoints)} waypoints")
                else:
                    debug_print(f"   ❌ Failed to transform section {section_num} waypoints")
    
    def _export_axial_routes_by_section(self, waypoints: List[List], bridge_name: str, output_dir: Path):
        """Export axial routes separated by their span tags."""
        # Group waypoints by span tag
        spans = {}
        for waypoint in waypoints:
            if len(waypoint) >= 4:
                tag = waypoint[3]
                # Extract span number from tag (e.g., "axial_span1_girder1", "axial_span2_girder1")
                if tag.startswith("axial_span"):
                    span_num = tag.split("span")[1].split("_")[0]
                    if span_num not in spans:
                        spans[span_num] = []
                    spans[span_num].append(waypoint)
        
        # Export each span separately
        for span_num, span_waypoints in spans.items():
            if len(span_waypoints) > 1:  # Only export if more than 1 waypoint
                route_name = f"Axial Underdeck Span {span_num}"
                filename = f"{bridge_name}_Axial_Underdeck_Span_{span_num}.kmz"
                filepath = output_dir / filename
                
                # Transform to WGS84
                wgs84_waypoints = self._transform_to_wgs84(span_waypoints)
                if wgs84_waypoints:
                    self._create_kmz_file(wgs84_waypoints, route_name, filepath)
                    self.export_paths.append(str(filepath))
                    debug_print(f"   ✅ Exported axial span {span_num}: {len(span_waypoints)} waypoints")
                else:
                    debug_print(f"   ❌ Failed to transform axial span {span_num} waypoints")
    

    
    def _transform_to_wgs84(self, waypoints: List[List]) -> List[List]:
        """
        Transform waypoints from local metric coordinates to WGS84.
        
        The waypoints are in a local metric coordinate system created during flight generation.
        This method handles both scenarios:
        1. Direct transformation function available (preferred)
        2. Manual transformation using bridge center point
        """
        transformed_waypoints = []
        
        # Method 1: Use direct transformation function if available
        if hasattr(self.app, 'local_metric_to_wgs84') and self.app.local_metric_to_wgs84:
            debug_print("   🔄 Using direct local_metric_to_wgs84 transformation")
            
            for waypoint in waypoints:
                if len(waypoint) < 3:
                    continue
                    
                x, y, z = waypoint[0], waypoint[1], waypoint[2]
                tag = waypoint[3] if len(waypoint) >= 4 else "unknown"
                
                try:
                    lat, lon, alt = self.app.local_metric_to_wgs84(x, y, z)
                    transformed_waypoints.append([lat, lon, alt, tag])
                except Exception as e:
                    debug_print(f"   ⚠️  Failed to transform point {x:.2f}, {y:.2f}: {e}")
                    continue
            
            debug_print(f"   ✅ Transformed {len(transformed_waypoints)} waypoints using direct function")
            return transformed_waypoints
        
        # Method 2: Manual transformation using bridge center
        center_lat, center_lon = self._find_bridge_center()
        if center_lat is None or center_lon is None:
            debug_print("   ❌ Cannot find bridge center for coordinate transformation!")
            return []
        
        debug_print(f"   📍 Using bridge center: {center_lat:.6f}, {center_lon:.6f}")
        
        for waypoint in waypoints:
            if len(waypoint) < 3:
                continue
                
            x, y, z = waypoint[0], waypoint[1], waypoint[2]
            tag = waypoint[3] if len(waypoint) >= 4 else "unknown"
            
            try:
                # Reverse the local metric transformation
                lat_rad_center = math.radians(center_lat)
                
                # Convert local metric (x, y) back to lat/lon offset from center
                lat_offset = y / 111132.954  # meters to degrees latitude
                lon_offset = x / (111132.954 * math.cos(lat_rad_center))  # meters to degrees longitude
                
                lat = center_lat + lat_offset
                lon = center_lon + lon_offset
                alt = z  # Altitude usually stays the same
                
                transformed_waypoints.append([lat, lon, alt, tag])
                
            except Exception as e:
                debug_print(f"   ⚠️  Failed to transform point {x:.2f}, {y:.2f}: {e}")
                continue
        
        debug_print(f"   ✅ Transformed {len(transformed_waypoints)} waypoints from local metric to WGS84")
        return transformed_waypoints
    
    def _find_bridge_center(self) -> Tuple[Optional[float], Optional[float]]:
        """Find the WGS84 center point of the bridge from available data sources."""
        debug_print("   🔍 Searching for bridge center coordinates:")
        
        # Method 1: Use trajectory_wgs84 (imported bridge data)
        if hasattr(self.app, 'trajectory_wgs84') and self.app.trajectory_wgs84 and len(self.app.trajectory_wgs84) > 0:
            trajectory_wgs84 = self.app.trajectory_wgs84
            center_lat = sum(pt[0] for pt in trajectory_wgs84) / len(trajectory_wgs84)
            center_lon = sum(pt[1] for pt in trajectory_wgs84) / len(trajectory_wgs84)
            debug_print(f"   ✅ Found trajectory_wgs84 with {len(trajectory_wgs84)} points")
            return center_lat, center_lon
        
        # Method 2: Use current_trajectory (manually drawn trajectories) 
        if hasattr(self.app, 'current_trajectory') and self.app.current_trajectory and len(self.app.current_trajectory) > 0:
            current_trajectory = self.app.current_trajectory
            center_lat = sum(pt[0] for pt in current_trajectory) / len(current_trajectory)
            center_lon = sum(pt[1] for pt in current_trajectory) / len(current_trajectory)
            debug_print(f"   ✅ Found current_trajectory with {len(current_trajectory)} points")
            return center_lat, center_lon
        
        # Method 3: Try to use trajectory_list if available (project coordinates)
        if hasattr(self.app, 'trajectory_list') and self.app.trajectory_list and len(self.app.trajectory_list) > 0:
            debug_print("   🔄 Found trajectory_list - attempting coordinate transformation")
            try:
                # Transform trajectory_list to WGS84 first 
                source_coord_sys = getattr(self.app, 'selected_coord_system', None) or "Lambert72"
                trajectory_wgs84 = self.app._transform_coordinates(
                    self.app.trajectory_list, source_coord_sys, "WGS84"
                )
                if trajectory_wgs84 and len(trajectory_wgs84) > 0:
                    center_lat = sum(pt[0] for pt in trajectory_wgs84) / len(trajectory_wgs84)
                    center_lon = sum(pt[1] for pt in trajectory_wgs84) / len(trajectory_wgs84)
                    debug_print(f"   ✅ Transformed trajectory_list to WGS84 center")
                    return center_lat, center_lon
            except Exception as e:
                debug_print(f"   ❌ Failed to transform trajectory_list: {e}")
        
        debug_print("   ❌ No valid trajectory data found for center calculation")
        return None, None
    
    def _get_bridge_name(self) -> str:
        """Get bridge name from various app data sources."""
        # Try parsed data
        if hasattr(self.app, "parsed_data") and self.app.parsed_data:
            project_data = self.app.parsed_data.get("project", {})
            bridge_name = project_data.get("bridge_name")
            if bridge_name:
                return self._sanitize_filename(bridge_name)
        
        # Try current project
        if hasattr(self.app, "current_project"):
            name = getattr(self.app.current_project, "name", None)
            if name:
                return self._sanitize_filename(name)
        
        return "Bridge"
    
    def _create_kmz_file(self, waypoints: List[List], route_name: str, output_path: Path):
        """Create a single KMZ file from waypoints with wmpz folder structure."""
        # Validate and adjust waypoints
        processed_waypoints = self._process_waypoints(waypoints)
        
        if not processed_waypoints:
            debug_print(f"❌ No valid waypoints for {route_name}")
            return
        
        # Create KML structure
        kml_root = self._build_dji_wpml_kml(processed_waypoints, route_name)
        
        # Create wmpz directory structure
        wmpz_dir = output_path.parent / "wmpz"
        wmpz_dir.mkdir(parents=True, exist_ok=True)
        
        try:
            # Write KML file (must be named "template.kml" for DJI compatibility)
            kml_file = wmpz_dir / "template.kml"
            tree = ET.ElementTree(kml_root)
            tree.write(str(kml_file), encoding="utf-8", pretty_print=True, xml_declaration=True)
            
            # Create KMZ file (zip of the wmpz folder)
            with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as kmz:
                # Add all files from wmpz directory to the zip
                for file_path in wmpz_dir.rglob("*"):
                    if file_path.is_file():
                        # Calculate the archive name (relative path within the zip)
                        archive_name = file_path.relative_to(wmpz_dir.parent)
                        kmz.write(file_path, archive_name)
            
            debug_print(f"   📁 Created KMZ with wmpz structure: {output_path.name}")
            
        finally:
            # Cleanup wmpz directory
            import shutil
            shutil.rmtree(wmpz_dir, ignore_errors=True)
    
    def _process_waypoints(self, waypoints: List[List]) -> List[List]:
        """Process and validate waypoints for KMZ export."""


        processed = []
        low_altitude_count = 0

        for i, waypoint in enumerate(waypoints):
            if len(waypoint) < 3:
                debug_print(f"⚠️  Skipping waypoint {i}: insufficient coordinates")
                continue
            
            lat, lon, alt = waypoint[0], waypoint[1], waypoint[2]
            tag = waypoint[3] if len(waypoint) >= 4 else f"wp_{i}"
            
            # Validate coordinates
            if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                debug_print(f"⚠️  Skipping waypoint {i}: invalid coordinates ({lat:.6f}, {lon:.6f})")
                continue
            
            # Handle altitude adjustments
            if alt < self.config["min_altitude"]:
                low_altitude_count += 1
                if self.config["adjust_low_altitudes"]:
                    alt = self.config["min_altitude"]
                    debug_print(f"   🔧 Adjusted waypoint {i} altitude to {alt}m")
            
            # Calculate heights for DJI WPML
            height_to_use, ellipsoid_height_to_use = self._calculate_waypoint_height(alt, tag)
            
            processed.append([lat, lon, height_to_use, tag])
        
        if low_altitude_count > 0 and not self.config["adjust_low_altitudes"]:
            debug_print(f"⚠️  {low_altitude_count} waypoints have altitude below {self.config['min_altitude']}m")

        # Remove consecutive duplicates
        processed = self._remove_consecutive_duplicates(processed)

        return processed
    
    def _remove_consecutive_duplicates(self, waypoints: List[List]) -> List[List]:
        """Remove consecutively following exactly identical waypoints.

        Preserves vertical connection points that have same X,Y but different Z coordinates,
        as these are intentional flight path maneuvers.
        """


        if len(waypoints) <= 1:
            return waypoints

        unique_waypoints = [waypoints[0]]  # Always keep the first waypoint
        removed_count = 0

        for i in range(1, len(waypoints)):
            current = waypoints[i]
            previous = waypoints[i - 1]

            # Check if points are exactly identical (all coordinates match)
            if (len(current) >= 3 and len(previous) >= 3 and
                current[0] == previous[0] and  # lat
                current[1] == previous[1] and  # lon
                current[2] == previous[2]):    # alt
                # Additional check: preserve points that are part of vertical connections
                # Vertical connections have same X,Y but different Z, and are typically tagged as "connection"
                current_tag = current[3] if len(current) >= 4 else ""
                previous_tag = previous[3] if len(previous) >= 4 else ""

                # If this is a true duplicate (same X,Y,Z AND same tag), remove it
                # But if it's a vertical connection point, preserve it
                if ("connection" in current_tag.lower() or
                    "connection" in previous_tag.lower() or
                    current_tag != previous_tag):
                    # Preserve vertical connections and points with different tags
                    unique_waypoints.append(current)
                    continue

                # This is a true duplicate, remove it
                removed_count += 1
                continue

            unique_waypoints.append(current)

        if removed_count > 0:
            debug_print(f"   ✅ Removed {removed_count} consecutive identical waypoints")

        return unique_waypoints
    
    def _build_dji_wpml_kml(self, waypoints: List[List], route_name: str) -> ET.Element:
        """Build the complete KML structure with DJI WPML elements."""
        # Define namespaces
        ns_map = {
            None: "http://www.opengis.net/kml/2.2",
            "wpml": "http://www.dji.com/wpmz/1.0.3"
        }

        # Create root KML element
        kml_element = ET.Element("kml", nsmap=ns_map)
        document = ET.SubElement(kml_element, "Document")
        
        # Add document metadata
        epoch_ms = int(time.time() * 1000)

        # local human-readable string in system timezone
        local_str = datetime.fromtimestamp(epoch_ms / 1000).strftime("%Y-%m-%d %H:%M:%S %Z")

        
        # DJI required fields
        ET.SubElement(document, f"{{{self.WPML_NS}}}createTime").text = str(epoch_ms)
        ET.SubElement(document, f"{{{self.WPML_NS}}}updateTime").text = str(epoch_ms)

        # Your own human-readable fields (not DJI spec, so DJI will ignore them)
        ET.SubElement(document, "humanCreateTime").text = local_str
        ET.SubElement(document, "humanUpdateTime").text = local_str
        
        # Add mission configuration
        self._add_mission_config(document, waypoints[0])
        
        # Add folder with waypoints
        folder = ET.SubElement(document, "Folder")
        ET.SubElement(folder, "name").text = route_name
        
        self._add_folder_config(folder, route_name)
        
        # Add all waypoints
        for index, waypoint in enumerate(waypoints):
            self._add_placemark(folder, waypoint, index)
        
        return kml_element
    
    def _add_mission_config(self, document: ET.Element, first_waypoint: List):
        """Add mission configuration elements."""
        mission_config = ET.SubElement(document, f"{{{self.WPML_NS}}}missionConfig")
        
        # Flight behavior
        ET.SubElement(mission_config, f"{{{self.WPML_NS}}}flyToWaylineMode").text = "safely"
        ET.SubElement(mission_config, f"{{{self.WPML_NS}}}finishAction").text = "goHome"
        ET.SubElement(mission_config, f"{{{self.WPML_NS}}}exitOnRCLost").text = "goContinue"
        
        # Takeoff reference point (first waypoint)
        lat, lon, alt = first_waypoint[:3]
        takeoff_point = f"{lat},{lon}"
        ET.SubElement(mission_config, f"{{{self.WPML_NS}}}takeOffRefPoint").text = takeoff_point
        ET.SubElement(mission_config, f"{{{self.WPML_NS}}}takeOffRefPointAGLHeight").text = str(alt)
        
        # Security and speed settings
        ET.SubElement(mission_config, f"{{{self.WPML_NS}}}takeOffSecurityHeight").text = str(self.config["takeoff_security_height"])
        ET.SubElement(mission_config, f"{{{self.WPML_NS}}}globalTransitionalSpeed").text = "0.2"
        
        # Drone information
        drone_info = ET.SubElement(mission_config, f"{{{self.WPML_NS}}}droneInfo")
        drone_enum = self.config.get("drone_enum_value", "60")
        ET.SubElement(drone_info, f"{{{self.WPML_NS}}}droneEnumValue").text = drone_enum
        ET.SubElement(drone_info, f"{{{self.WPML_NS}}}droneSubEnumValue").text = "0"
        
        # Payload information
        payload_info = ET.SubElement(mission_config, f"{{{self.WPML_NS}}}payloadInfo")
        payload_enum = self.config.get("payload_enum_value", "50")
        ET.SubElement(payload_info, f"{{{self.WPML_NS}}}payloadEnumValue").text = payload_enum
        ET.SubElement(payload_info, f"{{{self.WPML_NS}}}payloadSubEnumValue").text = "0"
        ET.SubElement(payload_info, f"{{{self.WPML_NS}}}payloadPositionIndex").text = "0"
    
    def _add_folder_config(self, folder: ET.Element, route_name: str):
        """Add folder configuration elements."""
        # Template configuration
        ET.SubElement(folder, f"{{{self.WPML_NS}}}templateType").text = "waypoint"
        ET.SubElement(folder, f"{{{self.WPML_NS}}}templateId").text = "0"
        
        # Coordinate system parameters
        wayline_coord_sys = ET.SubElement(folder, f"{{{self.WPML_NS}}}waylineCoordinateSysParam")
        ET.SubElement(wayline_coord_sys, f"{{{self.WPML_NS}}}coordinateMode").text = "WGS84"
        
        # Set height mode based on configuration
        height_mode = self.config.get("height_mode", "EGM96")
        if height_mode == "relativeToStartPoint" or height_mode == "AGL":
            height_mode_text = "relativeToStartPoint"
        else:
            height_mode_text = "EGM96"  # Default to EGM96 for other modes
        
        ET.SubElement(wayline_coord_sys, f"{{{self.WPML_NS}}}heightMode").text = height_mode_text
        ET.SubElement(wayline_coord_sys, f"{{{self.WPML_NS}}}positioningType").text = "GPS"
        
        # Flight parameters
        ET.SubElement(folder, f"{{{self.WPML_NS}}}autoFlightSpeed").text = str(self.config["global_speed"])
        ET.SubElement(folder, f"{{{self.WPML_NS}}}globalHeight").text = "100"
        ET.SubElement(folder, f"{{{self.WPML_NS}}}caliFlightEnable").text = "0"
        ET.SubElement(folder, f"{{{self.WPML_NS}}}gimbalPitchMode").text = "manual"
        
        # Waypoint heading parameters
        heading_param = ET.SubElement(folder, f"{{{self.WPML_NS}}}globalWaypointHeadingParam")
        ET.SubElement(heading_param, f"{{{self.WPML_NS}}}waypointHeadingMode").text = "manually"
        ET.SubElement(heading_param, f"{{{self.WPML_NS}}}waypointHeadingAngle").text = "0"
        ET.SubElement(heading_param, f"{{{self.WPML_NS}}}waypointPoiPoint").text = "0.000000,0.000000,0.000000"
        ET.SubElement(heading_param, f"{{{self.WPML_NS}}}waypointHeadingPoiIndex").text = "0"
        
        # Turn mode - Use configurable setting from parsed data
        ET.SubElement(folder, f"{{{self.WPML_NS}}}globalWaypointTurnMode").text = self.global_waypoint_turn_mode
        ET.SubElement(folder, f"{{{self.WPML_NS}}}globalUseStraightLine").text = "1"
    
    def _add_placemark(self, folder: ET.Element, waypoint: List, index: int):
        """Add a single waypoint placemark with per-waypoint speed mapping."""
        lat, lon, alt, tag = waypoint
        
        placemark = ET.SubElement(folder, "Placemark")
        
        # Point coordinates - Don't include Z value in coordinates element
        point = ET.SubElement(placemark, "Point")
        coordinates = ET.SubElement(point, "coordinates")
        coordinates.text = f"{lon},{lat}"  # No Z coordinate
        
        # WPML waypoint parameters
        ET.SubElement(placemark, f"{{{self.WPML_NS}}}index").text = str(index)
        
        # Heights are already calculated in _process_waypoints
        # Both height and ellipsoidHeight should be the same value for DJI WPML
        # The alt value here is already the processed height from _calculate_waypoint_height
        ET.SubElement(placemark, f"{{{self.WPML_NS}}}ellipsoidHeight").text = str(alt)
        ET.SubElement(placemark, f"{{{self.WPML_NS}}}height").text = str(alt)
        ET.SubElement(placemark, f"{{{self.WPML_NS}}}useGlobalHeight").text = "0"
        
        # Speed and behavior - Use per-waypoint speed if available
        waypoint_speed = self._get_flight_speed_for_tag(tag)
        ET.SubElement(placemark, f"{{{self.WPML_NS}}}useGlobalSpeed").text = "0"  # Use individual speed
        ET.SubElement(placemark, f"{{{self.WPML_NS}}}waypointSpeed").text = str(waypoint_speed)
        ET.SubElement(placemark, f"{{{self.WPML_NS}}}useGlobalHeadingParam").text = "1"
        ET.SubElement(placemark, f"{{{self.WPML_NS}}}useGlobalTurnParam").text = "1"
        ET.SubElement(placemark, f"{{{self.WPML_NS}}}useStraightLine").text = "1"
        ET.SubElement(placemark, f"{{{self.WPML_NS}}}isRisky").text = "0"
    
    def _get_flight_speed_for_tag(self, tag: str) -> float:
        """Get the flight speed for a specific waypoint tag."""
        # Try to match tag to speed map
        if self.flight_speed_map:
            # Direct match
            if tag in self.flight_speed_map:
                speed_info = self.flight_speed_map[tag]
                if isinstance(speed_info, dict) and "speed" in speed_info:
                    try:
                        return float(speed_info["speed"])
                    except (ValueError, TypeError):
                        pass
            
            # Pattern matching for tags like "101_1", "underdeck_2_3", etc.
            for route_key in self.flight_speed_map:
                if route_key in tag or tag.startswith(route_key):
                    speed_info = self.flight_speed_map[route_key]
                    if isinstance(speed_info, dict) and "speed" in speed_info:
                        try:
                            return float(speed_info["speed"])
                        except (ValueError, TypeError):
                            continue
        
        # Fallback to global speed
        return self.config.get("global_speed", 2.0)
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for safe file system usage."""
        # Remove or replace invalid characters
        sanitized = re.sub(r'[<>:"/\\|?*]', "_", filename)
        sanitized = re.sub(r'\s+', "_", sanitized)  # Replace spaces with underscores
        return sanitized[:50]  # Limit length

    def export_waypoints_to_ply(self, waypoints: List[List], filename: str, output_dir: Path) -> str:
        """
        Export flight route waypoints to PLY format for visualization (points and lines).
        Uses the same approach as the visualization widget.

        Args:
            waypoints: List of waypoints in format [x, y, z, tag] or [x, y, z]
            filename: Name of the PLY file (without extension)
            output_dir: Directory to save the PLY file

        Returns:
            Path to the created PLY file
        """
        try:
            import pyvista as pv
            import numpy as np
        except ImportError as e:
            debug_print(f"   ❌ PyVista not available for PLY export: {e}")
            return ""

        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)

        ply_filepath = output_dir / f"{filename}.ply"

        try:
            # Filter valid waypoints and extract coordinates (same as visualization widget)
            pts = []
            for wp in waypoints:
                if len(wp) >= 3:
                    pts.append(wp[:3])  # Only keep x, y, z

            if len(pts) < 2:
                debug_print(f"   ⚠️  Not enough valid waypoints for PLY export: {len(pts)}")
                return ""

            # Convert to numpy array
            pts_array = np.array(pts, dtype=float)

            # Create PolyData (same as visualization widget)
            poly = pv.PolyData(pts_array)

            # Create lines connecting consecutive points (same as visualization widget)
            # lines array = [nPointsSubLine, id0, id1, nPointsSubLine, ...]
            poly.lines = np.hstack([[2, i, i + 1] for i in range(len(pts_array) - 1)])

            # Export to PLY format with proper edges (manual method for guaranteed edge connectivity)
            with open(ply_filepath, 'w') as f:
                # PLY header for points and edges
                f.write("ply\n")
                f.write("format ascii 1.0\n")
                f.write(f"element vertex {len(pts_array)}\n")
                f.write("property float x\n")
                f.write("property float y\n")
                f.write("property float z\n")
                f.write(f"element edge {len(pts_array) - 1}\n")
                f.write("property int vertex1\n")
                f.write("property int vertex2\n")
                f.write("end_header\n")

                # Write vertex data (points)
                for point in pts_array:
                    f.write(f"{point[0]:.6f} {point[1]:.6f} {point[2]:.6f}\n")

                # Write edge data (connect consecutive points with edges)
                for i in range(len(pts_array) - 1):
                    f.write(f"{i} {i + 1}\n")

            debug_print(f"   ✅ Exported flight route with {len(pts_array)} points connected by {len(pts_array) - 1} edges to {ply_filepath}")
            return str(ply_filepath)

        except Exception as e:
            debug_print(f"   ❌ Failed to export PLY file: {e}")
            import traceback
            traceback.print_exc()
            return ""


# Convenience functions for backward compatibility and easy usage
def export_flight_routes_with_dialog(app_instance, parent=None) -> List[str]:
    """
    Convenience function to export flight routes with a configuration dialog.
    
    Args:
        app_instance: Reference to the main ORBIT application
        parent: Parent widget for dialog
        
    Returns:
        List of exported file paths
    """
    exporter = OrbitFlightExporter(app_instance)
    return exporter.export_with_dialog(parent)


def export_flight_routes(app_instance, output_directory: str, config: Dict[str, Any] = None) -> List[str]:
    """
    Convenience function to export flight routes directly.
    
    Args:
        app_instance: Reference to the main ORBIT application
        output_directory: Directory to save KMZ files
        config: Export configuration (optional)
        
    Returns:
        List of exported file paths
    """
    exporter = OrbitFlightExporter(app_instance, config)
    return exporter.export_all_routes(output_directory)