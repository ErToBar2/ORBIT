#!/usr/bin/env python3
"""
ORBIT Main GUI Application

This module provides the main GUI class that integrates the ORBIT backend
with the PySide6 interface for the flight planning application.
"""

# Outout variables:
# Final Overview flight route: self.app.overview_flight_waypoints
# Final Underdeck flight route: self.app.underdeck_flight_waypoints
# Final Underdeck flight  Axial:  self.app.underdeck_flight_waypoints


from __future__ import annotations

# ——— Standard library ——————————————————————————————————————————————
import copy
import html
import json
import math
import os
import platform
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import traceback
import zipfile
from datetime import datetime
from pathlib import Path
from copy import deepcopy

# ——— Third-party ————————————————————————————————————————————————
import cv2
import numpy as np
import pandas as pd
import pyvista as pv
from lxml import etree as ET
from pyproj import Transformer
from tqdm import tqdm

# ——— Qt (PySide6) ————————————————————————————————————————————————
from PySide6.QtCore import (
    QFile,
    QEventLoop,
    QObject,
    QTimer,
    QUrl,
    Qt,
    Signal,
    Slot,
)
from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDockWidget,
    QDoubleSpinBox,
    QFileDialog,
    QGraphicsScene,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QProgressDialog,
    QSlider,
    QSpinBox,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QCheckBox
)



# ——— First-party (orbit) ————————————————————————————————————————————
from orbit.resources import resources_rc 
from orbit.io.context import CoordinateSystemRegistry, ProjectContext, VerticalRef
from orbit.io.crs import CoordinateSystem
from orbit.io.data_parser import parse_text_boxes, set_debug_print
from orbit.io.bridge_loader import BridgeDataLoader
from orbit.gui.bridge_modeler import BridgeModeler
from orbit.gui.pillar_modeler import PillarModeler
from orbit.gui.visualization_widget import VisualizationWidget
from orbit.io.flight_exporter import FlightExportDialog, OrbitFlightExporter
from orbit.io.importers import _separate_structural_components  # consider making public
# from orbit.mission import MissionBuilder

from orbit.planners.overview_flight_generator import (
    PhotogrammetricPlanner,
    PhotoPlanParameters,
)
from orbit.planners.overview_flight_path_constructor import FlightPathConstructor
from orbit.planners.underdeck import UnderdeckPlanner, UnderdeckPlanParameters
from orbit.planners.underdeck_flight_generator import generate_underdeck_routes

DEBUG = False
set_debug_print(DEBUG)

def debug_print(*args, **kwargs) -> None:
    """Print function that only outputs when DEBUG is True."""
    if DEBUG:
        print(*args, **kwargs)

def error_debug_print(*args, **kwargs) -> None:
    """Print function that always outputs (for errors)."""
    print(*args, **kwargs)

# Custom debug page to capture JavaScript console output
class DebugWebEnginePage(QWebEnginePage):
    def javaScriptConsoleMessage(self, lvl, msg, line, src):
        debug_print(f"[JS console] {msg} (line {line})")

class MapBridge(QObject):
    """Bridge class for WebChannel communication with JavaScript."""
    
    # Define signals for communication
    map_clicked = Signal(str)  # Signal to emit when map is clicked
    
    def __init__(self):
        super().__init__()
        self.click_handler = None  # Will be set by main app
        
    @Slot(str)
    def handle_coordinates(self, coords_json):
        """Handle coordinate data from JavaScript - legacy method."""
        debug_print(f"[JS] Legacy coordinates: {coords_json}")

    @Slot(str)
    def handle_map_click(self, click_data_json):
        """Handle map click data from JavaScript."""
        debug_print(f"[BRIDGE] Received map click: {click_data_json}")
        # Emit signal instead of direct call
        self.map_clicked.emit(click_data_json)

class OrbitMainApp(QMainWindow):
    """Main application window for ORBIT flight planning GUI."""
    
    def __init__(self):
        super().__init__()
        self.ui = QUiLoader().load(QFile(str(Path(__file__).parent / "ORBIT_UI4.ui")))
        
        # Initialize attributes
        self.current_bridge = None
        self.current_context = None
        self.drawing_mode = None
        
        # Initialize cross-section data
        self.current_crosssection_path = None  # Track selected cross-section image path
        
        # Initialize drawing data
        self.current_trajectory = []
        self.current_pillars = []
        
                # Initialize globally accessible extracted data
        self.trajectory_list = []  # [[x,y,z], [x,y,z], ...] - globally accessible
        self.pillars_list = []     # [[[x,y,z], [x,y,z]], [[x,y,z], [x,y,z]]] - globally accessible
        self.abutment_list = []    # [[[x,y,z], [x,y,z]], ...] - globally accessible
        
        # Initialize WGS84 transformed data for map visualization
        self.trajectory_wgs84 = []  # [[lat,lon], [lat,lon], ...] - globally accessible
        self.pillars_wgs84 = []     # [[[lat,lon], [lat,lon]], [[lat,lon], [lat,lon]]] - globally accessible
        self.abutments_wgs84 = []   # [[[lat,lon], [lat,lon]], ...] - globally accessible
        
        # Initialize coordinate system variables for zoom functionality
        self.selected_coord_system = None  # Store selected coordinate system
        
        
        # NEW: Store original Z values before transformation
        self.trajectory_original_z = []  # Store original Z values from imported data
        self.trajectory_heights = []     # Parsed from textbox

        
        # NEW: holder for the PyVista 3-D viewer widget
        self.visualizer = None
        
        # Initialize proper history system for undo/redo
        self.trajectory_history = []  # For tracking main trajectory
        self.trajectory_redo_stack = []
        self.pillar_history = []  # For tracking main pillars
        self.pillar_redo_stack = []
        self.safety_zones_redo_stack = []
        # Redo stack for individual safety zone points (when undoing points within a zone)
        self.zone_points_redo_stack = []
        
        # Initialize session and data loader
        self.bridge_session = None
        self.data_loader = None
        
        # Safety zone data
        self.current_safety_zones = []  # List of completed zones
        self.current_zone_points = []   # Points for zone being drawn
        self.current_zone_id = 0
        self.safety_zones_history = []
        
        self._last_coordinate_system = getattr(self, "_last_coordinate_system", "WGS84_Fallback")

        # Load UI
        self.load_ui()
        
        # Connect signals
        self.connect_signals()
        
        # Set window properties
        self.setWindowTitle("ORBIT - Flight Planning Application")
        
        # Parse both text boxes once on start-up
        self.parsed_data = {"project": {}, "flight_routes": {}}
        self._update_parsed_data()
    
        
        # Initialize waypoints display
        self._update_waypoints_display()
        
    def set_data_parser_debug(self, enabled: bool) -> None:
        """Enable or disable debug output from the data parser.
        
        Args:
            enabled: True to enable debug output, False to disable
        """
        set_debug_print(enabled)
        debug_print(f"[ORBIT] Data parser debug output {'enabled' if enabled else 'disabled'}")
        
    def load_ui(self):
        """Load the UI file and set up the interface."""
        ui_file_path = Path(__file__).parent / "ORBIT_UI4.ui"
        
        if not ui_file_path.exists():
            raise FileNotFoundError(f"UI file not found: {ui_file_path}")
        
        ui_file = QFile(str(ui_file_path))
        if not ui_file.open(QFile.ReadOnly):
            raise RuntimeError(f"Could not open UI file: {ui_file_path}")
        
        loader = QUiLoader()
        self.ui = loader.load(ui_file)
        ui_file.close()
        
        if self.ui is None:
            raise RuntimeError("Failed to load UI widget")
            
        # Get references to key widgets
        self.left_panel_stacked = self.ui.findChild(QWidget, "leftPanelStackedWidget")
        self.tab_widget = self.ui.findChild(QWidget, "tabWidget")
        self.project_text_edit = self.ui.findChild(QWidget, "tab0_textEdit1_Photo")
        self.flight_routes_text_edit = self.ui.findChild(QWidget, "tab0_textEdit1_Photo_2")
        self.cross_section_view = self.ui.findChild(QWidget, "graphicsView_crosssection_2")
        

        
        # Get reference to waypoints display text box
        self.waypoints_text_box = self.ui.findChild(QTextEdit, "WaypointsTextBox")
        if self.waypoints_text_box:
            self.waypoints_text_box.setReadOnly(True)
            debug_print("✅ Found waypoints display text box")
        else:
            debug_print("⚠️ Waypoints display text box not found")
            self.waypoints_text_box = None
            
        # Get references to waypoints control widgets
        self.waypoints_slider = self.ui.findChild(QSlider, "WaypointsSlider")
        self.waypoints_line_edit = self.ui.findChild(QLineEdit, "WaypointsQLineEdit")
        
        if self.waypoints_slider and self.waypoints_line_edit:
            debug_print("✅ Found waypoints control widgets")
            self._setup_waypoints_controls()
        else:
            debug_print("⚠️ Waypoints control widgets not found")
            self.waypoints_slider = None
            self.waypoints_line_edit = None
    

    
        # Replace placeholder label with QWebEngineView in Tab 1
        placeholder = self.ui.findChild(QWidget, "tab1_QWebEngineView")
        if placeholder:
            parent_layout = placeholder.parent().layout()
            self.web_view = QWebEngineView(self.ui)
            self.web_view.setMinimumSize(800, 600)  # Ensure visible size
            
            # Set up debug page to capture JS console output
            self.debug_page = DebugWebEnginePage()
            self.web_view.setPage(self.debug_page)
            
            # Allow file:// URLs to access remote resources (for Leaflet CDN)
            setting_name = (
                "LocalContentCanAccessRemoteUrls"
                if hasattr(QWebEngineSettings, "LocalContentCanAccessRemoteUrls")
                else "LocalContentCanAccessRemoteUrl"
            )
            self.debug_page.settings().setAttribute(getattr(QWebEngineSettings, setting_name), True)
            
            idx = parent_layout.indexOf(placeholder)
            parent_layout.removeWidget(placeholder)
            placeholder.deleteLater()
            parent_layout.insertWidget(idx, self.web_view)

            # Optional Web channel bridge (for future interactive features)
            self.map_bridge = MapBridge()
            self.map_bridge.click_handler = self.handle_map_click  # Connect our handler
            channel = QWebChannel()
            channel.registerObject('bridge', self.map_bridge)
            self.web_view.page().setWebChannel(channel)

            # Create and load simple working HTML content
            self._setup_map_widget()
        else:
            self.web_view = None
            self.map_bridge = None
    

    def _setup_map_widget(self):
        """Setup the map widget and load the HTML map."""
        debug_print("[DEBUG] Setting up map widget...")

        # Create simple map HTML file
        map_path = self._create_simple_map_html()
        debug_print(f"[DEBUG] Created simple map HTML at: {map_path}")

        # Setup QWebEngineView
        self.debug_page = DebugWebEnginePage()
        self.web_view.setPage(self.debug_page)

        # Enable remote content access
        settings = self.web_view.page().settings()
        settings.setAttribute(QWebEngineSettings.WebAttribute.LocalContentCanAccessRemoteUrls, True)

        # Load the map
        map_url = QUrl.fromLocalFile(map_path)
        debug_print(f"[DEBUG] Loading map from: {map_path}")
        self.web_view.load(map_url)

        # Connect load finished signal
        self.web_view.loadFinished.connect(self._on_map_load_finished)

        debug_print("[DEBUG] Map widget setup complete")
    
    def _create_simple_map_html(self):
        """Create a simple HTML file with working Leaflet map."""
        html_content = '''<!DOCTYPE html>
<html>
<head>
    <title>ORBIT Flight Planning Map</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="qrc:///qtwebchannel/qwebchannel.js"></script>
    <style>
        html, body { height: 100%; margin: 0; padding: 0; }
        #map { height: 100%; width: 100%; }
        .search-container {
            position: absolute; top: 10px; left: 70px; z-index: 1000;
            background: white; padding: 10px; border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.3);
        }
    </style>
</head>
<body>
    <div class="search-container">
        <input type="text" id="searchInput" placeholder="Enter location" style="width: 200px;">
        <button onclick="searchLocationAndZoom()" style="margin-left: 5px;">Search</button>
    </div>
    <div id="map"></div>
    <script>
        console.log('Initializing ORBIT map...');
        
        // Create map centered on Belgium (good default for bridge inspection)
        var map = L.map('map').setView([50.8503, 4.3517], 10);
        console.log('Map created');
        
        // Add OpenStreetMap tiles
        var osmLayer = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap contributors'
        }).addTo(map);
        
        // Add satellite layer option
        var satelliteLayer = L.tileLayer('https://{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', {
            maxZoom: 20,
            subdomains: ['mt0', 'mt1', 'mt2', 'mt3'],
            attribution: 'Imagery © Google'
        });
        
        // Layer control
        L.control.layers({
            "OpenStreetMap": osmLayer,
            "Satellite": satelliteLayer
        }).addTo(map);
        
        console.log('Map layers configured');
        
        // Search functionality
        function searchLocationAndZoom() {
            var address = document.getElementById('searchInput').value;
            if (!address) return;
            
            // Using Nominatim (OpenStreetMap) geocoding service
            var url = 'https://nominatim.openstreetmap.org/search?format=json&q=' + encodeURIComponent(address);
            fetch(url)
                .then(response => response.json())
                .then(data => {
                    if (data && data.length > 0) {
                        var result = data[0];
                        var lat = parseFloat(result.lat);
                        var lon = parseFloat(result.lon);
                        map.setView([lat, lon], 15);
                        L.marker([lat, lon]).addTo(map)
                            .bindPopup(address)
                            .openPopup();
                        console.log('Searched location: ' + address + ' -> ' + lat + ', ' + lon);
                    } else {
                        alert('Location not found: ' + address);
                    }
                })
                .catch(error => {
                    console.error('Search error:', error);
                    alert('Search failed');
                });
        }
        
        // Allow search on Enter key
        document.getElementById('searchInput').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                searchLocationAndZoom();
            }
        });
        
        // WebChannel will be initialized from Qt side after page load
        window.initWebChannelFromQt = function() {
            if (typeof qt !== 'undefined' && qt.webChannelTransport) {
                console.log('Initializing WebChannel from Qt...');
                new QWebChannel(qt.webChannelTransport, function(channel) {
                    window.bridge = channel.objects.bridge;
                    console.log('SUCCESS: WebChannel bridge connected and ready!');
                });
            } else {
                console.log('ERROR: Qt WebChannel transport not available');
            }
        };
        
        console.log('ORBIT map initialization complete');
    </script>
</body>
</html>'''
    
        # Write to file
        map_file = Path(__file__).parent / "flight_map.html"
        map_file.write_text(html_content, encoding='utf-8')
        debug_print(f"[DEBUG] Created flight map HTML at: {map_file}")
        return str(map_file.absolute())

    def _on_map_load_finished(self, ok: bool):
        """Load bridge data visualization after map loads."""
        if not ok:
            debug_print("[DEBUG] Map failed to load")
            return

        debug_print("[DEBUG] Map loaded successfully")

        # Setup WebChannel for JavaScript communication AFTER map loads
        debug_print("[DEBUG] Setting up WebChannel bridge...")
        self.map_bridge = MapBridge()
        # Connect the signal to our handler
        self.map_bridge.map_clicked.connect(self.handle_map_click)

        channel = QWebChannel()
        channel.registerObject("bridge", self.map_bridge)
        self.web_view.page().setWebChannel(channel)
        debug_print("[DEBUG] WebChannel bridge registered")
        
        # Set up map layers for drawing
        js_setup_layers = '''
            console.log('Setting up map layers...');
            window.trajectoryLayer = L.layerGroup().addTo(map);
            window.pillarLayer = L.layerGroup().addTo(map);
            window.safetyZoneLayer = L.layerGroup().addTo(map);
            console.log('Map layers created');
        '''
        self.debug_page.runJavaScript(js_setup_layers)
        

    def _prepare_pillars_for_map(self, pillars):
        """
        Normalize pillars to list of {id, lat, lon} in WGS84.
        Accepts dicts with either {'lat','lon'} (WGS84) or {'x','y','z'} (local metric).
        """
        inv = getattr(self, "_last_inverse_transform", None)
        coord_sys = str(getattr(self, "_last_coordinate_system", "WGS84_Fallback"))
        use_inv = callable(inv) and coord_sys.startswith("LocalMetric_")
        out = []

        for i, p in enumerate(pillars or []):
            pid = p.get("id", f"P{i+1}")
            if "lat" in p and "lon" in p:
                lat, lon = p["lat"], p["lon"]
            elif "x" in p and "y" in p:
                if not use_inv:
                    # can't safely convert without inverse
                    continue
                x, y, z = p.get("x", np.nan), p.get("y", np.nan), p.get("z", 0.0)
                try:
                    lon, lat, _ = inv(float(x), float(y), float(z))
                except Exception:
                    continue
            else:
                continue

            try:
                lat = float(lat); lon = float(lon)
            except Exception:
                continue
            if not (np.isfinite(lat) and np.isfinite(lon)):
                continue

            lat = float(np.clip(lat, -90.0, 90.0))
            lon = float(((lon + 180.0) % 360.0) - 180.0)
            out.append({"id": pid, "lat": lat, "lon": lon})

        return out

    def _prepare_points_for_map(self, pts, *, pts_are_local_metric=False):
        """
        Return a clean list of [lat, lon] for the web map (WGS84).
        - pts may be list[[x,y,(z)]], list[(x,y)], or list of dicts with lat/lon or x/y.
        - If pts_are_local_metric=True, converts using self._last_inverse_transform (Local->WGS84).
        - Drops any invalid points (NaN/inf).
        """
        out = []
        inv = getattr(self, "_last_inverse_transform", None)
        coord_sys = str(getattr(self, "_last_coordinate_system", "WGS84_Fallback"))
        use_inv = pts_are_local_metric and callable(inv) and coord_sys.startswith("LocalMetric_")

        for p in (pts or []):
            # accept tuple/list or dict
            if isinstance(p, dict):
                # prefer explicit lat/lon; otherwise x/y
                if "lat" in p and "lon" in p:
                    a, b, z = p["lat"], p["lon"], p.get("z", 0.0)
                    is_local = False
                else:
                    a, b, z = p.get("x"), p.get("y"), p.get("z", 0.0)
                    is_local = True
            else:
                # sequence: [a, b, (z)]
                a = p[0] if len(p) > 0 else np.nan
                b = p[1] if len(p) > 1 else np.nan
                z = p[2] if len(p) > 2 else 0.0
                is_local = pts_are_local_metric

            try:
                a = float(a); b = float(b); z = float(z)
            except Exception:
                continue

            if not (np.isfinite(a) and np.isfinite(b)):
                continue

            if use_inv or is_local:
                # local metric -> WGS84 via inverse (expects x,y,z -> returns lon,lat,z)
                if callable(inv):
                    try:
                        lon, lat, _ = inv(a, b, z)
                    except Exception:
                        continue
                else:
                    # No inverse available; cannot convert safely
                    continue
            else:
                # already WGS84 lat=a, lon=b
                lat, lon = a, b

            if np.isfinite(lat) and np.isfinite(lon):
                lat = float(np.clip(lat, -90.0, 90.0))
                lon = float(((lon + 180.0) % 360.0) - 180.0)
                out.append([lat, lon])

        return out

    def _update_map_visualization(self):
        """Always push the live WGS84 lists to the web map (trajectory, pillars) and recenter."""
        debug_print("[DEBUG] _update_map_visualization called")

        # Ensure the web view is ready
        if not getattr(self, 'debug_page', None):
            debug_print("[MAP] No debug_page / web view yet; skipping map update")
            return

        # Idempotently ensure Leaflet layers exist
        try:
            js_bootstrap = """
                if (typeof map !== 'undefined') {
                    if (typeof window.trajectoryLayer === 'undefined') {
                        window.trajectoryLayer = L.layerGroup().addTo(map);
                    }
                    if (typeof window.pillarLayer === 'undefined') {
                        window.pillarLayer = L.layerGroup().addTo(map);
                    }
                    if (typeof window.safetyZoneLayer === 'undefined') {
                        window.safetyZoneLayer = L.layerGroup().addTo(map);
                    }
                }
            """
            self.debug_page.runJavaScript(js_bootstrap)
        except Exception as e:
            debug_print(f"[MAP] Layer bootstrap failed: {e}")

        # --- Trajectory (live WGS84) ---
        traj_wgs84 = []
        try:
            traj_wgs84 = self._prepare_points_for_map(
                getattr(self, "current_trajectory", []),
                pts_are_local_metric=False
            ) or []
        except Exception as e:
            debug_print(f"[MAP] Trajectory prep failed: {e}")

        try:
            self._send_trajectory_to_map(traj_wgs84)
        except Exception as e:
            debug_print(f"[MAP] Trajectory push failed: {e}")

        # --- Pillars (live WGS84 dicts: {'id','lat','lon'}) ---
        pillars_wgs84 = getattr(self, "current_pillars", []) or []
        try:
            self._send_pillars_to_map(pillars_wgs84)
        except Exception as e:
            debug_print(f"[MAP] Pillars push failed: {e}")

        # --- Safety zones (optional; WGS84) ---
        try:
            if hasattr(self, "_send_safety_zones_to_map"):
                zones = getattr(self, "current_safety_zones", []) or []
                self._send_safety_zones_to_map(zones)
        except Exception as e:
            debug_print(f"[MAP] Safety zones push failed: {e}")

        # --- Recenter based on available geometry (prefer trajectory, else pillars) ---
        try:
            if traj_wgs84:
                lat_vals = [p[0] for p in traj_wgs84]
                lon_vals = [p[1] for p in traj_wgs84]
            else:
                lat_vals = [p.get("lat") for p in pillars_wgs84 if "lat" in p and "lon" in p]
                lon_vals = [p.get("lon") for p in pillars_wgs84 if "lat" in p and "lon" in p]

            lat_vals = [float(v) for v in lat_vals if v is not None]
            lon_vals = [float(v) for v in lon_vals if v is not None]

            if lat_vals and lon_vals:
                min_lat, max_lat = min(lat_vals), max(lat_vals)
                min_lon, max_lon = min(lon_vals), max(lon_vals)

                if (max_lat - min_lat) < 1e-9 and (max_lon - min_lon) < 1e-9:
                    # Single point → center with a reasonable zoom
                    avg_lat = (min_lat + max_lat) / 2.0
                    avg_lon = (min_lon + max_lon) / 2.0
                    js_center = f"""
                        if (typeof map !== 'undefined') {{
                            map.setView([{avg_lat}, {avg_lon}], 17);
                            console.log('Map centered on single point');
                        }}
                    """
                    self.debug_page.runJavaScript(js_center)
                else:
                    # Fit bounds to extent
                    js_fit = f"""
                        if (typeof map !== 'undefined') {{
                            var bounds = L.latLngBounds([{min_lat}, {min_lon}], [{max_lat}, {max_lon}]);
                            map.fitBounds(bounds, {{ padding: [20, 20] }});
                            console.log('Map fit to geometry bounds');
                        }}
                    """
                    self.debug_page.runJavaScript(js_fit)
            else:
                debug_print("[MAP] No geometry available to center/fit map")
        except Exception as e:
            debug_print(f"[MAP] Recentering failed: {e}")

    def _convert_trajectory_to_wgs84(self):
        """Return list[[lat, lon, alt], ...] derived from project-CRS trajectory without mutating state."""
        try:
            if not getattr(self, 'current_bridge', None) or not getattr(self, 'current_context', None):
                return []
            traj = getattr(self.current_bridge, 'trajectory', None)
            pts = getattr(traj, 'points', None)
            if pts is None or getattr(pts, 'size', 0) == 0:
                return []

            proj2wgs = getattr(self.current_context, 'project_to_wgs84', None)
            if not callable(proj2wgs):
                return []

            out = []
            # pts is Nx3 (x,y,z) in PROJECT CRS
            for row in pts:
                x = float(row[0]); y = float(row[1])
                z = float(row[2]) if len(row) >= 3 else 0.0
                lon, lat, alt = proj2wgs(x, y, z)  # context returns lon,lat,alt
                out.append([lat, lon, alt])
            return out
        except Exception as e:
            error_debug_print(f"[MAP] traj→WGS84 failed: {e}")
            return []
    
    def _convert_pillars_to_wgs84(self):
        """Return list[{'id', 'lat', 'lon', 'z'}...] from project-CRS pillars; do not mutate."""
        try:
            if not getattr(self, 'current_bridge', None) or not getattr(self, 'current_context', None):
                return []
            proj2wgs = getattr(self.current_context, 'project_to_wgs84', None)
            if not callable(proj2wgs):
                return []

            out = []
            # If your pillars are model objects with x,y,z in project CRS:
            for p in getattr(self.current_bridge, 'pillars', []) or []:
                x = float(getattr(p, 'x', 0.0)); y = float(getattr(p, 'y', 0.0))
                z = float(getattr(p, 'z', 0.0))
                lon, lat, alt = proj2wgs(x, y, z)
                out.append({'id': getattr(p, 'id', ''), 'lat': lat, 'lon': lon, 'z': alt})
            return out
        except Exception as e:
            error_debug_print(f"[MAP] pillars→WGS84 failed: {e}")
            return []

    def _send_trajectory_to_map(self, trajectory_points):
        """Send trajectory data to the map for visualization (expects WGS84 lat/lon)."""
        # Python-side filtering (drop any non-finite)
        safe_pts = []
        for p in (trajectory_points or []):
            try:
                lat = float(p[0]); lon = float(p[1])
            except Exception:
                continue
            if np.isfinite(lat) and np.isfinite(lon):
                safe_pts.append([lat, lon])

        debug_print(f"[DEBUG] Sending {len(safe_pts)} trajectory points to map")

        try:
            payload = json.dumps(safe_pts, allow_nan=False)
        except ValueError:
            # Fallback if someone sneaked a NaN in
            payload = json.dumps([[float(lat), float(lon)] for lat, lon in safe_pts if np.isfinite(lat) and np.isfinite(lon)])

        js_code = f'''
            console.log('Updating complete trajectory on map...');
            if (window.trajectoryLayer) {{
                trajectoryLayer.clearLayers();

                var points = {payload};
                console.log('Received ' + points.length + ' complete trajectory points');

                // JS-side guard
                points = points.filter(function(p) {{
                    return Array.isArray(p) && p.length >= 2 &&
                        Number.isFinite(p[0]) && Number.isFinite(p[1]);
                }});

                if (points.length >= 2) {{
                    var polyline = L.polyline(points, {{
                        color: 'blue',
                        weight: 4,
                        opacity: 0.8,
                        dashArray: '5, 5',
                        className: 'complete-trajectory'
                    }}).addTo(trajectoryLayer);

                    console.log('Complete trajectory updated with ' + points.length + ' points');
                }} else if (points.length === 1) {{
                    L.marker(points[0], {{ className: 'complete-trajectory' }})
                        .addTo(trajectoryLayer)
                        .bindPopup('Trajectory point');
                    console.log('Single trajectory point displayed');
                }} else {{
                    console.log('Trajectory cleared (0 points)');
                }}
            }}
        '''
        self.debug_page.runJavaScript(js_code)
    
    def _send_pillars_to_map(self, pillars):
        """Send pillar data to the map for visualization."""
        debug_print(f"[DEBUG] Sending {len(pillars)} pillars to map")
        
        js_code = f'''
            console.log('Updating complete pillars on map...');
            if (window.pillarLayer) {{
                // Clear all pillar layers except abutments (both imported and user-drawn will be redrawn as unified)
                window.pillarLayer.eachLayer(function(layer) {{
                    if (!layer.options.className || !layer.options.className.includes('abutment')) {{
                        window.pillarLayer.removeLayer(layer);
                    }}
                }});
                
                var pillars = {pillars};
                console.log('Received ' + pillars.length + ' complete pillars');
                
                if (pillars.length === 0) {{
                    console.log('Pillars cleared (0 pillars)');
                    // Nothing to draw, just return from this JS block safely
                    console.log('Exiting pillar update early due to 0 pillars');
                }} else {{
                    // Draw lines connecting every completed pair (consecutive pillars)
                    for (var i = 0; i < pillars.length; i += 2) {{
                        var p1 = pillars[i];
                        var p2 = pillars[i + 1];
                        if (p2) {{
                            L.polyline([
                                [p1.lat, p1.lon],
                                [p2.lat, p2.lon]
                            ], {{
                                color: 'green',
                                weight: 5,
                                opacity: 0.9,
                                className: 'complete-pillar'
                            }}).addTo(pillarLayer);
                        }}
                    }}

                    // Draw markers for all pillars on top of lines
                    pillars.forEach(function(pillar) {{
                        var marker = L.circleMarker([pillar.lat, pillar.lon], {{
                            color: 'darkgreen',
                            fillColor: 'lightgreen',
                            fillOpacity: 0.9,
                            radius: 6,
                            className: 'complete-pillar'
                        }}).addTo(pillarLayer);
                        marker.bindPopup('Pillar: ' + pillar.id);
                    }});

                    console.log('Complete pillars visualization updated: ' + pillars.length + ' markers, ' + Math.floor(pillars.length/2) + ' lines');
                }}
            }}
        '''
        self.debug_page.runJavaScript(js_code)
    
    def _transform_coordinates(self, points_list, source_coord_system, target_coord_system="WGS84"):
        """
        Standalone coordinate transformation function.

        Args:
            points_list: List of [x, y, z] coordinates in source CRS.
                        For EPSG:4326 (WGS84), inputs are [lon, lat, (z)].
            source_coord_system: EPSG code (int/str like 31370, "4326", "EPSG:4326"),
                                known name ("Lambert72", "WGS84", "UTM31N", ...),
                                or "custom" (use self.last_custom_epsg / data_loader.last_custom_epsg).
            target_coord_system: Only "WGS84" is supported here (returns [lat, lon, z]).

        Returns:
            List of [lat, lon, z] in WGS84.
        """
        if not points_list:
            return []

        if target_coord_system and str(target_coord_system).upper() not in ("WGS84", "EPSG:4326"):
            debug_print(f"[TRANSFORM] Unsupported target CRS '{target_coord_system}' (only WGS84 supported).")
            return []

        # Averages only for concise logging (safe if values are numeric)
        try:
            avg_x = sum(float(p[0]) for p in points_list) / len(points_list)
            avg_y = sum(float(p[1]) for p in points_list) / len(points_list)
        except Exception:
            avg_x = avg_y = 0.0

        try:
            # Convenience aliases
            coord_system_map = {
                "Lambert72": 31370,
                "WGS84": 4326,
                "UTM31N": 32631,
                "UTM32N": 32632,
            }

            # ---- Resolve source EPSG robustly -----------------------------------
            src = source_coord_system
            source_epsg = None

            # 1) Explicit "custom" from loader dialog
            if isinstance(src, str) and src.lower() == "custom":
                source_epsg = getattr(self, "last_custom_epsg", None) \
                            or getattr(getattr(self, "data_loader", None), "last_custom_epsg", None)

            # 2) Forms like "EPSG:4326" or "4326" or 4326 / 4326.0
            if source_epsg is None:
                if isinstance(src, (int, float)):
                    try:
                        source_epsg = int(src)
                    except Exception:
                        source_epsg = None
                elif isinstance(src, str):
                    s = src.strip().upper()
                    if s.startswith("EPSG:"):
                        s = s.split(":", 1)[1].strip()
                    if s.isdigit():
                        source_epsg = int(s)

            # 3) Known names fallback
            if source_epsg is None:
                source_epsg = coord_system_map.get(str(src))

            if not source_epsg:
                debug_print(f"[TRANSFORM] Unsupported or unknown source CRS: {source_coord_system!r}")
                return []

            # ---- Fast identity path for EPSG:4326 (WGS84 degrees) ---------------
            if int(source_epsg) == 4326:
                transformed_points = []
                for p in points_list:
                    try:
                        lon = float(p[0])
                        lat = float(p[1])
                        z = float(p[2]) if len(p) > 2 and p[2] is not None else 0.0
                    except Exception:
                        continue
                    # Output must be [lat, lon, z]
                    transformed_points.append([lat, lon, z])

                if transformed_points:
                    try:
                        avg_lat = sum(pt[0] for pt in transformed_points) / len(transformed_points)
                        avg_lon = sum(pt[1] for pt in transformed_points) / len(transformed_points)
                        debug_print(
                            f"Transforming data from WGS84 to WGS84 (identity): "
                            f"{avg_x:.6f},{avg_y:.6f} -> {avg_lat:.6f},{avg_lon:.6f}"
                        )
                    except Exception:
                        pass
                return transformed_points

            # ---- General case: source EPSG -> WGS84 -----------------------------
            try:
                source_cs = CoordinateSystem.from_epsg(int(source_epsg))
            except Exception as e:
                error_debug_print(f"[TRANSFORM] Failed to build CRS from EPSG:{source_epsg} – {e}")
                return []

            transformed_points = []
            for p in points_list:
                try:
                    x = float(p[0])
                    y = float(p[1])
                    z_in = float(p[2]) if len(p) > 2 and p[2] is not None else None
                    lon, lat, z_out = source_cs.to_wgs84(x, y, z_in)
                    transformed_points.append([lat, lon, z_out])
                except Exception:
                    continue  # skip bad rows

            if transformed_points:
                try:
                    avg_lat = sum(pt[0] for pt in transformed_points) / len(transformed_points)
                    avg_lon = sum(pt[1] for pt in transformed_points) / len(transformed_points)
                    debug_print(
                        f"Transforming data from {source_coord_system} (EPSG:{source_epsg}) to {target_coord_system}: "
                        f"{avg_x:.2f},{avg_y:.2f} -> {avg_lat:.6f},{avg_lon:.6f}"
                    )
                except Exception:
                    pass

            return transformed_points

        except Exception as e:
            error_debug_print(f"Error during coordinate transformation: {e}")
            return []

    def _zoom_to_trajectory_data(self):
        """Zoom map to show trajectory data from self.trajectory_list after project confirmation."""
        try:
            if (not getattr(self, 'trajectory_list', None)) and getattr(self, 'current_trajectory', None):
                try:
                    lat_vals = [p[0] for p in self.current_trajectory]
                    lon_vals = [p[1] for p in self.current_trajectory]
                    avg_lat = sum(lat_vals)/len(lat_vals)
                    avg_lon = sum(lon_vals)/len(lon_vals)
                    min_lat, max_lat = min(lat_vals), max(lat_vals)
                    min_lon, max_lon = min(lon_vals), max(lon_vals)
                    ext = max(max_lat - min_lat, max_lon - min_lon)
                    zoom = 18 if ext <= 0.005 else 16 if ext <= 0.01 else 14 if ext <= 0.05 else 12 if ext <= 0.1 else 10
                    js_code = f"if (typeof map !== 'undefined') {{ map.setView([{avg_lat}, {avg_lon}], {zoom}); }}"
                    if hasattr(self, 'debug_page') and self.debug_page:
                        QTimer.singleShot(500, lambda: self.debug_page.runJavaScript(js_code))
                except Exception as e:
                    debug_print(f"[ZOOM] Live zoom failed: {e}")
                return

            if not hasattr(self, 'trajectory_list') or not self.trajectory_list:
                debug_print("No trajectory data available for zooming")
                return
                
            # Use standalone transformation function
            source_coord_system = self.selected_coord_system or "Lambert72"  # Default fallback
            
            # Transform coordinates using our standalone function
            transformed_points = self._transform_coordinates(
                self.trajectory_list, 
                source_coord_system, 
                "WGS84"
            )
            
            if not transformed_points:
                debug_print("No valid coordinates converted for zooming")
                return
            
            # Convert to the format expected by the rest of the function [lat, lon]
            wgs84_points = [[point[0], point[1]] for point in transformed_points]
            
            # Compute average x,y (lat,lon)
            avg_lat = sum(point[0] for point in wgs84_points) / len(wgs84_points)
            avg_lon = sum(point[1] for point in wgs84_points) / len(wgs84_points)
            
            # Compute bounds to decide zoom level
            min_lat = min(point[0] for point in wgs84_points)
            max_lat = max(point[0] for point in wgs84_points)
            min_lon = min(point[1] for point in wgs84_points)
            max_lon = max(point[1] for point in wgs84_points)
            
            # Calculate extent
            lat_extent = max_lat - min_lat
            lon_extent = max_lon - min_lon
            max_extent = max(lat_extent, lon_extent)
            
            # Decide zoom level based on extent (heuristic)
            if max_extent > 0.1:  # Very large area
                zoom_level = 10
            elif max_extent > 0.05:  # Large area
                zoom_level = 12
            elif max_extent > 0.01:  # Medium area
                zoom_level = 14
            elif max_extent > 0.005:  # Small area
                zoom_level = 16
            else:  # Very small area
                zoom_level = 18
                
            debug_print(f"Zooming map to: {avg_lat:.6f}, {avg_lon:.6f} (zoom level {zoom_level})")
            
            # Send zoom command to map via JavaScript
            js_code = f'''
                if (typeof map !== 'undefined') {{
                    map.setView([{avg_lat}, {avg_lon}], {zoom_level});
                    console.log('Map zoomed to trajectory location');
                }}
            '''
            
            # Execute JavaScript after a small delay to ensure map is ready
            if hasattr(self, 'debug_page') and self.debug_page:
                QTimer.singleShot(500, lambda: self.debug_page.runJavaScript(js_code))
            
        except Exception as e:
            debug_print(f"Error during zoom to trajectory: {e}")
    
    def _transform_imported_geometry_to_wgs84(self):
        """Transform all imported geometry (trajectory, pillars, abutments) to WGS84 for map visualization."""
        try:
            source_coord_system = self.selected_coord_system or "Lambert72"  # Default fallback
            
            # Transform trajectory
            if self.trajectory_list:
                # IMPORTANT: Store original Z values before transformation
                self.trajectory_original_z = [point[2] if len(point) > 2 else 0.0 for point in self.trajectory_list]
                debug_print(f"[Z_VALUES] Stored {len(self.trajectory_original_z)} original Z values from imported trajectory")
                if self.trajectory_original_z:
                    debug_print(f"[Z_VALUES] Z range: {min(self.trajectory_original_z):.1f}m to {max(self.trajectory_original_z):.1f}m")
                
                self.trajectory_wgs84 = self._transform_coordinates(
                    self.trajectory_list, 
                    source_coord_system, 
                    "WGS84"
                )
                # Convert to [lat, lon] format expected by map
                self.trajectory_wgs84 = [[point[0], point[1]] for point in self.trajectory_wgs84]
                debug_print(f"Transformed trajectory: {len(self.trajectory_wgs84)} points")
            
            # Transform pillars (nested format: [[[x,y,z], [x,y,z]], [[x,y,z], [x,y,z]]])
            if self.pillars_list:
                self.pillars_wgs84 = []
                for pillar_pair in self.pillars_list:
                    # Transform each point in the pair
                    transformed_pair = self._transform_coordinates(
                        pillar_pair, 
                        source_coord_system, 
                        "WGS84"
                    )
                    # Convert to [lat, lon] format
                    wgs84_pair = [[point[0], point[1]] for point in transformed_pair]
                    self.pillars_wgs84.append(wgs84_pair)
                debug_print(f"Transformed pillars: {len(self.pillars_wgs84)} pairs")
            
            # Transform abutments (nested format: [[[x,y,z], [x,y,z]], ...])
            if self.abutment_list:
                self.abutments_wgs84 = []
                for abutment_pair in self.abutment_list:
                    # Transform each point in the pair
                    transformed_pair = self._transform_coordinates(
                        abutment_pair, 
                        source_coord_system, 
                        "WGS84"
                    )
                    # Convert to [lat, lon] format
                    wgs84_pair = [[point[0], point[1]] for point in transformed_pair]
                    self.abutments_wgs84.append(wgs84_pair)
                debug_print(f"Transformed abutments: {len(self.abutments_wgs84)} pairs")
                
        except Exception as e:
            error_debug_print(f"Error transforming imported geometry: {e}")
    

    
    def _update_map_with_imported_geometry(self):
        """Update map visualization with imported and transformed geometry."""
        try:
            # Initialize trajectory drawing data and send to map
            if self.trajectory_wgs84 and not getattr(self, "current_trajectory", None):
                self.current_trajectory = self.trajectory_wgs84.copy()
                debug_print(f"Initialized drawing trajectory with {len(self.current_trajectory)} imported points")
                # Send unified trajectory to map
                self._send_trajectory_to_map(self.current_trajectory)
                
            # Initialize pillar drawing data and send to map
            if self.pillars_wgs84 and not getattr(self, "current_pillars", None):
                self.current_pillars = []
                for i, pair in enumerate(self.pillars_wgs84):
                    for j, point in enumerate(pair):
                        pillar_id = f"IP{i+1}{chr(65+j)}"  # IP1A, IP1B, IP2A, IP2B, etc.
                        self.current_pillars.append({
                            'id': pillar_id,
                            'lat': point[0],
                            'lon': point[1]
                        })
                debug_print(f"Initialized drawing pillars with {len(self.current_pillars)} imported points")
                debug_print(f"Pillar IDs: {[p['id'] for p in self.current_pillars]}")
                # Send unified pillars to map
                self._send_pillars_to_map(self.current_pillars)
                
            # Initialize undo/redo stacks - clear them since we're starting fresh with imported data
            self.trajectory_redo_stack.clear()
            self.pillar_redo_stack.clear()
            self.safety_zones_redo_stack.clear()
            self.zone_points_redo_stack.clear()
            debug_print("Cleared undo/redo stacks for fresh start with imported data")
                
            # Send abutments to map (abutments are not typically drawn interactively, so no integration needed)
            if self.abutments_wgs84:
                self._send_imported_abutments_to_map(self.abutments_wgs84)
                
        except Exception as e:
            debug_print(f"Error updating map with imported geometry: {e}")
    
    def _send_imported_trajectory_to_map(self, trajectory_points):
        """Send imported trajectory data to the map for visualization."""
        debug_print(f"Sending imported trajectory: {len(trajectory_points)} points")
        
        js_code = f'''
            console.log('Updating imported trajectory on map...');
            if (window.trajectoryLayer) {{
                trajectoryLayer.clearLayers();
                var points = {trajectory_points};
                console.log('Received ' + points.length + ' imported trajectory points');
                
                if (points.length >= 2) {{
                    var polyline = L.polyline(points, {{
                        color: 'blue',
                        weight: 3,
                        opacity: 0.8,
                        dashArray: '5, 5',
                        className: 'imported-trajectory'
                    }}).addTo(trajectoryLayer);
                    
                    console.log('Imported trajectory displayed with ' + points.length + ' points');
                }} else if (points.length === 1) {{
                    // Single point marker
                    L.marker(points[0]).addTo(trajectoryLayer)
                        .bindPopup('Single trajectory point');
                }}
            }}
        '''
        self.debug_page.runJavaScript(js_code)
    
    def _send_imported_pillars_to_map(self, pillar_pairs):
        """Send imported pillar data to the map for visualization."""
        debug_print(f"Sending imported pillars: {len(pillar_pairs)} pairs")
        
        js_code = f'''
            console.log('Updating imported pillars on map...');
            if (window.pillarLayer) {{
                pillarLayer.clearLayers();
                var pillarPairs = {pillar_pairs};
                console.log('Received ' + pillarPairs.length + ' imported pillar pairs');
                
                pillarPairs.forEach(function(pair, index) {{
                    if (pair.length >= 2) {{
                                                 // Draw line between pillar pair
                         var pillarLine = L.polyline([pair[0], pair[1]], {{
                             color: 'darkgreen',
                             weight: 4,
                             opacity: 0.9,
                             className: 'imported-pillar'
                         }}).addTo(pillarLayer);
                        
                        // Add markers for each pillar
                                                 var marker1 = L.circleMarker(pair[0], {{
                             color: 'darkgreen',
                             fillColor: 'lightgreen',
                             fillOpacity: 0.8,
                             radius: 5,
                             className: 'imported-pillar'
                         }}).addTo(pillarLayer);
                        marker1.bindPopup('Imported Pillar ' + (index + 1) + 'A');
                        
                                                 var marker2 = L.circleMarker(pair[1], {{
                             color: 'darkgreen',
                             fillColor: 'lightgreen',
                             fillOpacity: 0.8,
                             radius: 5,
                             className: 'imported-pillar'
                         }}).addTo(pillarLayer);
                        marker2.bindPopup('Imported Pillar ' + (index + 1) + 'B');
                        
                        console.log('Drew imported pillar pair ' + (index + 1));
                    }} else if (pair.length === 1) {{
                        // Single pillar
                                                 var marker = L.circleMarker(pair[0], {{
                             color: 'darkgreen',
                             fillColor: 'yellow',
                             fillOpacity: 0.8,
                             radius: 5,
                             className: 'imported-pillar'
                         }}).addTo(pillarLayer);
                        marker.bindPopup('Single Imported Pillar ' + (index + 1));
                    }}
                }});
                
                console.log('Imported pillars visualization complete');
            }}
        '''
        self.debug_page.runJavaScript(js_code)
    
    def _send_imported_abutments_to_map(self, abutment_pairs):
        """Send imported abutment data to the map for visualization."""
        debug_print(f"Sending imported abutments: {len(abutment_pairs)} pairs")
        
        js_code = f'''
            console.log('Updating imported abutments on map...');
            if (window.pillarLayer) {{
                // Use pillar layer but with different styling
                var abutmentPairs = {abutment_pairs};
                console.log('Received ' + abutmentPairs.length + ' imported abutment pairs');
                
                abutmentPairs.forEach(function(pair, index) {{
                    if (pair.length >= 2) {{
                                                 // Draw line between abutment pair
                         var abutmentLine = L.polyline([pair[0], pair[1]], {{
                             color: 'purple',
                             weight: 5,
                             opacity: 0.9,
                             className: 'imported-abutment'
                         }}).addTo(pillarLayer);
                        
                        // Add markers for each abutment
                                                 var marker1 = L.circleMarker(pair[0], {{
                             color: 'purple',
                             fillColor: 'violet',
                             fillOpacity: 0.8,
                             radius: 6,
                             className: 'imported-abutment'
                         }}).addTo(pillarLayer);
                        marker1.bindPopup('Imported Abutment ' + (index + 1) + 'A');
                        
                                                 var marker2 = L.circleMarker(pair[1], {{
                             color: 'purple',
                             fillColor: 'violet',
                             fillOpacity: 0.8,
                             radius: 6,
                             className: 'imported-abutment'
                         }}).addTo(pillarLayer);
                        marker2.bindPopup('Imported Abutment ' + (index + 1) + 'B');
                        
                        console.log('Drew imported abutment pair ' + (index + 1));
                    }} else if (pair.length === 1) {{
                        // Single abutment
                                                 var marker = L.circleMarker(pair[0], {{
                             color: 'purple',
                             fillColor: 'orange',
                             fillOpacity: 0.8,
                             radius: 6,
                             className: 'imported-abutment'
                         }}).addTo(pillarLayer);
                        marker.bindPopup('Single Imported Abutment ' + (index + 1));
                    }}
                }});
                
                console.log('Imported abutments visualization complete');
            }}
        '''
        self.debug_page.runJavaScript(js_code)
    
    def handle_map_click(self, click_data_json):
        """Handle map click events from JavaScript."""
        try:
            click_data = json.loads(click_data_json)
            mode = click_data['mode']
            lat = click_data['lat']
            lng = click_data['lng']

            debug_print(f"[CLICK] Map clicked in {mode} mode at: {lat:.6f}, {lng:.6f}")

            if mode == 'trajectory':
                self._add_trajectory_point(lat, lng)
            elif mode == 'pillars':
                self._add_pillar_point(lat, lng)
            elif mode == 'safety_zones':
                self._add_safety_zone_point(lat, lng)
                
        except Exception as e:
            debug_print(f"[ERROR] Failed to handle map click: {e}")

            traceback.print_exc()

    def _add_trajectory_point(self, lat, lng):
        """Add a trajectory point from map click."""
        debug_print(f"[TRAJECTORY] Adding point: {lat:.6f}, {lng:.6f}")

        # Convert WGS84 to project coordinate system
        try:
            self.current_trajectory.append([lat, lng])
            debug_print(f"[TRAJECTORY] Total points: {len(self.current_trajectory)}")
            debug_print(f"[TRAJECTORYXXXXXXXXXXXXXXXXXX] Current trajectory list: {self.current_trajectory}")
            self._update_trajectory_on_map()
            
        except Exception as e:
            error_debug_print(f"[ERROR] Failed to add trajectory point: {e}")

    def _add_pillar_point(self, lat, lng):
        """Add a pillar point from map click."""
        debug_print(f"[PILLAR] Adding pillar: {lat:.6f}, {lng:.6f}")

        # Clear redo stack when adding new pillar (standard undo/redo behavior)
        self.pillar_redo_stack.clear()

        # Add to pillars directly using WGS84 coordinates (same pattern as trajectory)
        try:
            # Generate new ID continuing from existing ones
            next_num = len(self.current_pillars) + 1
            pillar_id = f"UP{next_num}"  # UP = User Pillar to distinguish from imported IP

            # Store WGS84 coordinates directly (no conversion needed for map display)
            self.current_pillars.append({'id': pillar_id, 'lat': lat, 'lon': lng})

            debug_print(f"[PILLAR] Added pillar {pillar_id} at WGS84: {lat:.6f}, {lng:.6f}")
            debug_print(f"[PILLAR] Total pillars: {len(self.current_pillars)}")
            debug_print(f"[PILLAR] Current pillar list: {[p['id'] for p in self.current_pillars]}")
            debug_print(f"[PILARXXXXXXXXXXXXXXXXXX] Current Pillar list: {self.current_pillars}")
            # Update map visualization
            self._update_pillars_on_map()
            
        except Exception as e:
            error_debug_print(f"[ERROR] Failed to add pillar point: {e}")
            import traceback
            traceback.print_exc()

    def _add_safety_zone_point(self, lat, lng):
        """Add a safety zone point from map click."""
        debug_print(f"[SAFETY_ZONE] Adding point: {lat:.6f}, {lng:.6f}")

        # Convert WGS84 to project coordinate system
        try:
            if self.current_context:
                x, y, z = self.current_context.wgs84_to_project(lng, lat, 0)
                debug_print(f"[SAFETY_ZONE] Converted to project coords: {x:.2f}, {y:.2f}")
            else:
                x, y, z = lng, lat, 0  # Fallback
                debug_print(f"[SAFETY_ZONE] No context available, using raw coords: {x:.6f}, {y:.6f}")

            # Add to current zone points
            self.current_zone_points.append([lat, lng])
            # Clear point redo stack when adding new point
            self.zone_points_redo_stack.clear()

            debug_print(f"[SAFETY_ZONE] Current zone ID {self.current_zone_id}: {len(self.current_zone_points)} points")

            # Update map visualization
            self._update_safety_zones_on_map()

        except Exception as e:
            error_debug_print(f"[ERROR] Failed to add safety zone point: {e}")

    def _update_trajectory_on_map(self):
        """Update trajectory visualization on map."""
        # Default assumption: current_trajectory is in WGS84 (lat,lon)
        # If you want to send the densified *local* path instead, pass pts_are_local_metric=True and the local list.
        traj_for_map = self._prepare_points_for_map(self.current_trajectory, pts_are_local_metric=False)
        debug_print(f"[DEBUG] Updating trajectory on map: {len(traj_for_map)} points (clean WGS84)")
        self._send_trajectory_to_map(traj_for_map)

    def _update_pillars_on_map(self):
        """Update pillar visualization on map."""
        debug_print(f"[DEBUG] Updating pillars on map: {len(self.current_pillars)} pillars")
        self._send_pillars_to_map(self.current_pillars)

    def show(self):
        """Show the main window."""
        self.ui.show()
        
    def connect_signals(self):
        """Connect all GUI signals to their handlers."""
        try:
            # Connect tab change signal
            if self.tab_widget and hasattr(self.tab_widget, 'currentChanged'):
                self.tab_widget.currentChanged.connect(self.on_tab_changed)
            
            # Tab synchronization - connect both tab widgets
            if self.left_panel_stacked and self.tab_widget:
                self.left_panel_stacked.currentChanged.connect(self.sync_tabs_from_left_panel)
                self.tab_widget.currentChanged.connect(self.sync_tabs_from_main_tab)
            
            # TAB 0 - Project Setup
            self.connect_button("btn_tab0_ImportDirectory", self.import_directory)
            self.connect_button("btn_tab0_LoadBridgeData", self.load_bridge_data)
            self.connect_button("btn_tab0_ConfirmProjectData", self.confirm_project_data)
            self.connect_button("btn_tab0_updateData", self.update_crosssection_data)
            
            # Tab 1 - Photogrammetric Flight
            
            self.connect_button("btn_tab1_DrawTrajectory", self.toggle_draw_trajectory)
            self.connect_button("btn_tab1_mark_pillars", self.toggle_mark_pillars)
            self.connect_button("btn_tab1_SafetyZones", self.toggle_safety_zones)
            # Undo/Redo buttons with new names
            self.connect_button("btnUndo_trajectory", self.undo_trajectory)
            self.connect_button("btnRedo_trajectory", self.redo_trajectory)
            self.connect_button("btnUndo_Pillar", self.undo_pillar)
            self.connect_button("btnRedo_Pillar", self.redo_pillar)
            self.connect_button("btnUndo_Safety", self.undo_safety)
            self.connect_button("btnRedo_Safety", self.redo_safety)
            
            # Add Safety button
            self.connect_button("btnAdd_Safety", self.add_safety_zone)
            self.connect_button("btnLoad_SafetyZones", self.load_SafetyZones_fromJSON)
                        
            # Tab 1 - Actions
            self.connect_button("btn_tab1_build_model", self.build_flight_model)
            
            # Tab 2 - Inspection Flights (placeholder methods)
            self.connect_button("btn_tab2_LoadPC", self.load_point_cloud)
            self.connect_button("btn_tab2_TopView", self.change_to_top_view)
            self.connect_button("btnToggleFR", self.toggle_dock_widget_fr)
            self.connect_button("btn_tab2_UpdateSafetyZones", self.update_safety_zones_3d)
            # Under-deck inspection route button
            self.connect_button("btn_tab2_Dock_updateInspectionRoute", self.update_inspection_route)
            self.connect_button("btn_tab2_Dock_updateOverviewFlight", self.update_flight_routes)
            self.connect_button("btn_tab2_ExportOverview", self.export_overview_flight)
            self.connect_button("btn_tab2_ExportUnderdeck", self.export_underdeck_flight)
            
            
            # Flight Route Adjustment Controls
            self._setup_flight_route_adjustment_controls()
            

            
        except Exception as e:
            debug_print(f"Warning: Could not connect all signals: {e}")
    
    def connect_button(self, button_name: str, handler):
        """Helper to connect a button by name to a handler."""
        button = self.ui.findChild(QWidget, button_name)
        if button and hasattr(button, 'clicked'):
            button.clicked.connect(handler)
        else:
            debug_print(f"Warning: Button {button_name} not found or not clickable")
    
    def sync_tabs_from_left_panel(self, index):
        """Sync main tab widget when left panel changes."""
        if self.tab_widget and hasattr(self.tab_widget, 'setCurrentIndex'):
            self.tab_widget.setCurrentIndex(index)
    
    def sync_tabs_from_main_tab(self, index):
        """Sync left panel when main tab widget changes."""
        if self.left_panel_stacked and hasattr(self.left_panel_stacked, 'setCurrentIndex'):
            self.left_panel_stacked.setCurrentIndex(index)
    
    # =====================================================================
    # Tab 0 - Project Setup Functions
    # =====================================================================
    
    def import_directory(self):
        """Handle btn_tab0_ImportDirectory click - open directory dialog."""
        try:
            # Initialize data loader if needed
            if not self.data_loader:
                if not self.project_text_edit:
                    QMessageBox.warning(self.ui, "Error", "Project text edit not found")
                    return
                    
                self.data_loader = BridgeDataLoader(
                    self.ui, 
                    self.project_text_edit,
                    self.flight_routes_text_edit,
                    self.cross_section_view
                )
            
            # Call the import directory method
            success = self.data_loader.import_directory()
            
            if success:
                debug_print("Base directory imported successfully")
            
        except Exception as e:
            QMessageBox.critical(self.ui, "Error", 
                               f"Failed to import directory: {str(e)}")



    def load_bridge_data(self):
        """Load bridge data from selected file, update UI, and reflect imported values in the Project textbox."""
        try:
            # Reset 3D model state when loading new data
            if hasattr(self, '_3d_model_built'):
                self._3d_model_built = False
                debug_print("[load_bridge_data] Reset 3D model flag for new data")

            # Reset drawing mode and button states
            if getattr(self, 'drawing_mode', None):
                self.drawing_mode = None
                self._reset_all_drawing_buttons()
                self._disable_map_click_handler()
                self._remove_drawing_mode_indicator()
                debug_print("[load_bridge_data] Reset drawing mode and button states")

            # Ensure data loader exists
            if not getattr(self, 'data_loader', None):
                if not getattr(self, 'project_text_edit', None):
                    QMessageBox.warning(self.ui, "Error", "Project text edit not found")
                    return
                self.data_loader = BridgeDataLoader(
                    self.ui,
                    self.project_text_edit,
                    self.flight_routes_text_edit,
                    self.cross_section_view
                )

            # Load via data loader
            result = self.data_loader.load_bridge_data()
            bridge = result[0] if isinstance(result, tuple) else result

            if not bridge:
                QMessageBox.warning(self.ui, "Warning", "Failed to load bridge data")
                return

            self.current_bridge = bridge

            # Populate helper lists for non-Excel sources
            if not getattr(self, 'trajectory_list', None) and getattr(bridge, 'trajectory', None) and bridge.trajectory.points.size:
                self.trajectory_list = bridge.trajectory.points.tolist()
            if not getattr(self, 'pillars_list', None) and getattr(bridge, 'pillars', None):
                flat = [[p.x, p.y, p.z] for p in bridge.pillars]
                self.pillars_list = [flat[i:i + 2] for i in range(0, len(flat), 2)]

            # Capture coordinate system & vertical datum (before UI updates)
            if hasattr(self.data_loader, 'last_coord_system') and self.data_loader.last_coord_system:
                coord_system = self.data_loader.last_coord_system
                # For custom EPSG, use the actual EPSG code instead of "custom"
                if coord_system == "custom" and hasattr(self.data_loader, 'last_custom_epsg') and self.data_loader.last_custom_epsg:
                    self.selected_coord_system = str(self.data_loader.last_custom_epsg)
                    debug_print(f"[DEBUG] Custom EPSG captured: {self.selected_coord_system}")
                else:
                    self.selected_coord_system = coord_system
                    debug_print(f"[DEBUG] Coordinate system captured: {self.selected_coord_system}")


            # Compute “Imported data” metrics from the loaded bridge
            traj_count = None
            traj_len = None
            pillars_count = None
            avg_pillar_h = None

            if getattr(bridge, 'trajectory', None):
                if getattr(bridge.trajectory, 'points', None) is not None:
                    try:
                        traj_count = len(bridge.trajectory.points)
                    except Exception:
                        pass
                if hasattr(bridge.trajectory, 'length') and bridge.trajectory.length is not None:
                    try:
                        traj_len = round(float(bridge.trajectory.length), 2)
                    except Exception:
                        pass

            if getattr(bridge, 'pillars', None):
                try:
                    pillars_count = len(bridge.pillars)
                    if pillars_count > 0:
                        avg_pillar_h = round(sum(getattr(p, 'z', 0.0) for p in bridge.pillars) / pillars_count, 2)
                except Exception:
                    pass

            # Prepare updates for the Project Information textbox (Tab-0)
            project_updates = {
                "coordinate_system": getattr(self, 'selected_coord_system', None),

                "trajectory_points_count": traj_count,
                "trajectory_length": traj_len,
                "pillars_count": pillars_count,
                "average_pillar_height": avg_pillar_h,
                # If you want to update bridge_name, uncomment the line below; otherwise leave as-is to
                # preserve complex names with commas/# etc.
                # "bridge_name": getattr(bridge, 'name', None),
            }

            # Apply colored in-place updates (value-only, purple pt-11, comments preserved)
            if hasattr(self, 'update_textbox_variables'):
                self.update_textbox_variables("tab0_textEdit1_Photo", project_updates)
                debug_print(f"[PROJECT_UPDATE] Updated Project Information with: " +
                    ", ".join([k for k, v in project_updates.items() if v not in (None, "*")]))

            # Cross-section info capture
            if hasattr(self.data_loader, 'current_crosssection_path'):
                self.current_crosssection_path = self.data_loader.current_crosssection_path
                debug_print(f"[DEBUG] Cross-section path captured: {self.current_crosssection_path}")

            if hasattr(self.data_loader, 'crosssection_transformed_points') and self.data_loader.crosssection_transformed_points is not None:
                self.crosssection_transformed_points = self.data_loader.crosssection_transformed_points
                try:
                    debug_print(f"[DEBUG] Cross-section 2D shape captured with {len(self.crosssection_transformed_points)} points")
                except Exception:
                    debug_print("[DEBUG] Cross-section 2D shape captured")

            # Transfer parsed data including computed bridge_width from data_loader
            if hasattr(self.data_loader, 'parsed_data') and self.data_loader.parsed_data is not None:
                # Merge the data_loader's parsed_data into the main app's parsed_data
                if not hasattr(self, 'parsed_data') or self.parsed_data is None:
                    self.parsed_data = {"project": {}, "flight_routes": {}}

                # Update project data with any new values from data_loader
                if 'project' in self.data_loader.parsed_data:
                    self.parsed_data['project'].update(self.data_loader.parsed_data['project'])
                    debug_print(f"[DEBUG] Merged project data from data_loader: {list(self.data_loader.parsed_data['project'].keys())}")

                # Update flight_routes data if present
                if 'flight_routes' in self.data_loader.parsed_data:
                    self.parsed_data['flight_routes'].update(self.data_loader.parsed_data['flight_routes'])

            # Update the map visualization after loading
            if getattr(self, 'debug_page', None):
                debug_print("[DEBUG] Triggering map visualization update after bridge load...")
                self._update_map_visualization()

            # Log success
            bname = getattr(bridge, 'name', 'Unknown Bridge')
            debug_print(f"Bridge data loaded: {bname}")

        except Exception as e:
            QMessageBox.critical(self.ui, "Error", f"Failed to load bridge data: {str(e)}")
            


    
    def confirm_project_data(self):
        """Handle confirming project data and setup."""
        try:
            # Ensure data loader
            if not getattr(self, 'data_loader', None):
                if not getattr(self, 'project_text_edit', None):
                    QMessageBox.warning(self.ui, "Error", "Project text edit not found")
                    return
                self.data_loader = BridgeDataLoader(
                    self.ui,
                    self.project_text_edit,
                    self.flight_routes_text_edit,
                    self.cross_section_view
                )

            # Transfer cross-section data from data loader to main application if available
            if hasattr(self.data_loader, 'crosssection_transformed_points') and self.data_loader.crosssection_transformed_points is not None:
                self.crosssection_transformed_points = self.data_loader.crosssection_transformed_points
                debug_print(f"[DEBUG] Transferred cross-section data from data loader: {len(self.crosssection_transformed_points)} points")

            # Transfer parsed data including computed bridge_width from data_loader
            if hasattr(self.data_loader, 'parsed_data') and self.data_loader.parsed_data is not None:
                # Merge the data_loader's parsed_data into the main app's parsed_data
                if not hasattr(self, 'parsed_data') or self.parsed_data is None:
                    self.parsed_data = {"project": {}, "flight_routes": {}}

                # Update project data with any new values from data_loader
                if 'project' in self.data_loader.parsed_data:
                    self.parsed_data['project'].update(self.data_loader.parsed_data['project'])
                    debug_print(f"[DEBUG] Merged project data from data_loader: {list(self.data_loader.parsed_data['project'].keys())}")

                # Update flight_routes data if present
                if 'flight_routes' in self.data_loader.parsed_data:
                    self.parsed_data['flight_routes'].update(self.data_loader.parsed_data['flight_routes'])

            if hasattr(self.data_loader, 'current_crosssection_path'):
                self.current_crosssection_path = self.data_loader.current_crosssection_path
                debug_print(f"[DEBUG] Transferred cross-section path from data loader: {self.current_crosssection_path}")

            # Cross-section presence prompt (unchanged)
            if not self._check_cross_section_availability():
                reply = QMessageBox.question(
                    self.ui,
                    "No Cross-Section Data",
                    "No cross-section data found. Cross-section data is required for accurate flight planning.\n\n"
                    "Would you like to select a template now?",
                    QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
                )
                if reply == QMessageBox.Yes:
                    pass  # user will pick a template in the existing view
                elif reply == QMessageBox.Cancel:
                    return
                else:
                    continue_reply = QMessageBox.question(
                        self.ui,
                        "Continue Without Cross-Section?",
                        "Cross-section data is important for accurate flight planning.\n\n"
                        "Do you want to continue without cross-section data?",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.No
                    )
                    if continue_reply == QMessageBox.No:
                        return

            # Parse project data from text fields
            # Skip EPSG check since it was already validated during load_bridge_data
            project_data = self.data_loader._parse_project_data(skip_epsg_check=True)
            if not project_data:
                QMessageBox.warning(self.ui, "Error", "Could not parse project data. Please check the project settings.")
                return

            original_import_dir = project_data.get('import_dir')

            # Reuse context from the loader / app; if missing, create it once now.
            ctx = getattr(self.data_loader, "current_context", None) or getattr(self, "current_context", None)
            if ctx is None:
                ctx = self.data_loader._ensure_context_from_project_data(project_data)
            self.current_context = ctx

            # Only setup folders/copies; DO NOT rebuild context here
            _ = self.data_loader._setup_project_structure(
                project_data,
                write_back_to_text=False,
                pin_import_dir_to_project=False,
                existing_context=ctx,
                build_context=False
            )

            # --- Backfill project-CRS lists from CURRENT WGS84 lists if needed ---
            try:
                proj = getattr(self.current_context, "wgs84_to_project", None)
                if callable(proj):
                    # 1) Trajectory [[lat,lon]] -> [[x,y,z]]
                    if (not getattr(self, "trajectory_list", None)) and getattr(self, "current_trajectory", None):
                        tl = []
                        z_src = getattr(self, "trajectory_original_z", None) or []
                        for i, (lat, lon) in enumerate(self.current_trajectory):
                            z = float(z_src[i]) if i < len(z_src) else 0.0
                            x, y, z_out = proj(lon, lat, z)  # (lon, lat, z) !
                            tl.append([float(x), float(y), float(z_out)])
                        self.trajectory_list = tl
                        setattr(self, "_crs_of_trajectory_list", "project")
                        debug_print(f"[BACKFILL] Built trajectory_list from WGS84 current_trajectory: {len(tl)} pts")

                    # 2) Pillars [{'id','lat','lon'}] -> [[x,y,z],[x,y,z]] pairs
                    if (not getattr(self, "pillars_list", None)) and getattr(self, "current_pillars", None):
                        flat = []
                        for p in self.current_pillars:
                            lat = float(p.get("lat")); lon = float(p.get("lon"))
                            x, y, z_out = proj(lon, lat, 0.0)  # (lon, lat, z) !
                            flat.append([float(x), float(y), float(z_out)])
                        self.pillars_list = [flat[i:i+2] for i in range(0, len(flat), 2)]
                        setattr(self, "_crs_of_pillars_list", "project")
                        debug_print(f"[BACKFILL] Built pillars_list from WGS84 current_pillars: {len(flat)} pts / {len(self.pillars_list)} pairs")
            except Exception as _bf_exc:
                debug_print(f"[BACKFILL] Skipped (no context or invalid data): {_bf_exc}")

            # (Optional) write back the chosen CRS to Tab-0 so UI matches runtime
            if hasattr(self.data_loader, 'last_coord_system'):
                if hasattr(self, 'update_textbox_variables'):
                    # For custom EPSG, show the actual EPSG code instead of "custom"
                    coord_system_display = self.data_loader.last_coord_system
                    epsg_code_to_write = None

                    if (coord_system_display == "custom" and
                        hasattr(self.data_loader, 'last_custom_epsg') and
                        self.data_loader.last_custom_epsg):
                        coord_system_display = str(self.data_loader.last_custom_epsg)
                        epsg_code_to_write = self.data_loader.last_custom_epsg
                        debug_print(f"[DEBUG] Displaying custom EPSG in textbox: {coord_system_display}")
                    else:
                        # For predefined systems, get the EPSG code from the registry
                        try:
                            
                            info = CoordinateSystemRegistry.get_system_info(coord_system_display)
                            if info and 'epsg' in info:
                                epsg_code_to_write = info['epsg']
                                debug_print(f"[DEBUG] Found EPSG {epsg_code_to_write} for {coord_system_display}")
                        except Exception as e:
                            debug_print(f"[DEBUG] Could not determine EPSG for {coord_system_display}: {e}")

                    updates = {
                        "coordinate_system": coord_system_display
                    }

                    # Add EPSG code if we determined one
                    if epsg_code_to_write is not None:
                        updates["epsg_code"] = epsg_code_to_write

                    self.update_textbox_variables("tab0_textEdit1_Photo", updates)
            # Ensure the textbox still shows the user's import_dir (purple, pt-11; comments untouched)
            if original_import_dir and hasattr(self, 'update_textbox_variables'):
                self.update_textbox_variables("tab0_textEdit1_Photo", {
                    "import_dir": original_import_dir
                })

            # Update map after context
            if getattr(self, 'debug_page', None):
                self._update_map_visualization()

            # Prefer the single, comprehensive state saver (keeps everything in 01_Input)
            # If you still call multiple savers elsewhere, consider deprecating them.
            _ = self._save_complete_program_state()

            # Removed duplicate project config save - using only _save_complete_program_state

            # Removed legacy comprehensive project data saver - using only _save_complete_program_state

            # UI navigation
            try:
                left_panel_stacked = self.ui.findChild(QWidget, "leftPanelStackedWidget")
                if left_panel_stacked and hasattr(left_panel_stacked, 'setCurrentIndex'):
                    left_panel_stacked.setCurrentIndex(1)
                tab_widget = self.ui.findChild(QWidget, "tabWidget")
                if tab_widget and hasattr(tab_widget, 'setCurrentIndex'):
                    tab_widget.setCurrentIndex(1)
                debug_print("Navigated to Tab 1 - Flight Planning")
            except Exception as e:
                debug_print(f"Warning: Could not switch tabs: {e}")

            debug_print(f"[SUCCESS] Project structure created successfully!")
            debug_print(f"[SUCCESS] Directory: {project_data.get('project_dir_base', 'Unknown')}")
            debug_print(f"[SUCCESS] Bridge: {project_data.get('bridge_name', 'Unknown')}")
            debug_print(f"[SUCCESS] ✈️ Ready for flight planning!")

            # Map: show imported geometry
            self._transform_imported_geometry_to_wgs84()
            self._update_map_with_imported_geometry()
            self._zoom_to_trajectory_data()

            # Build 3-D model
            try:
                self.build_improved_3d_bridge_model()
            except Exception as _bm_exc:
                debug_print(f"[WARNING] build_improved_3d_bridge_model failed: {_bm_exc}")

        except Exception as e:
            debug_print(f"Error confirming project data: {e}")
            QMessageBox.critical(self.ui, "Error", f"Failed to confirm project data:\n{str(e)}")

    def _apply_text_box_updates(self, project_data: dict):
        """Apply any updates made to values in the text box"""
        try:
            # Get current text content to check for any manual updates
            current_text = self.project_text_edit.toPlainText()
            
            # Parse current values
            updated_data = {}
            for line in current_text.split('\n'):
                line = line.strip()
                if '=' in line and not line.startswith('#'):
                    try:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"\'')
                        
                        # Remove comments
                        if '#' in value:
                            value = value.split('#')[0].strip()
                        
                        # Convert to appropriate type
                        if key in ['input_scale_meters', 'bridge_width', 'epsilonInput']:
                            updated_data[key] = float(value)
                        elif key in ['epsg_code']:
                            updated_data[key] = int(value)
                        else:
                            updated_data[key] = value
                    except (ValueError, IndexError):
                        continue
            
            # Check for changes and apply them
            changed_values = []
            for key, new_value in updated_data.items():
                if key in project_data and project_data[key] != new_value:
                    project_data[key] = new_value
                    changed_values.append(f"{key}: {new_value}")
            
            if changed_values:
                debug_print(f"Applied text box updates: {', '.join(changed_values)}")
            
        except Exception as e:
            debug_print(f"Warning: Could not apply text box updates: {e}")
    
    def _save_project_configuration(self, project_dir: Path, project_data: dict):
        """Save the current project configuration to the project directory"""
        try:

            # Create project configuration
            config = {
                "project_name": project_data.get("bridge_name", "DefaultBridge"),
                "created_date": datetime.now().isoformat(),
                "project_directory": str(project_dir),
                "project_settings": project_data,
                "flight_route_settings": self.data_loader._parse_flight_route_data() if self.data_loader.flight_routes_text_edit else {},
                "coordinate_system": getattr(self.data_loader, 'last_coord_system', 'custom'),

                "geometry": {}
            }
            
            # ------------------------------------------------------------------
            # Embed trajectory / pillar / abutment information (if Excel selected)
            # ------------------------------------------------------------------
            try:
                sel_file = getattr(self.data_loader, 'last_selected_file', None)
                if sel_file and sel_file.suffix.lower() in {'.xlsx', '.xls'}:
             
                    
                    df_tmp = pd.read_excel(sel_file, sheet_name="00_Input")
                    abut_pairs, super_pairs, pillar_pairs = _separate_structural_components(df_tmp)

                    # trajectory list (mid-points of super pairs)
                    traj_pts = []
                    for seq in sorted(super_pairs.keys()):
                        pair = super_pairs[seq]
                        if 'right' in pair and 'left' in pair:
                            midpoint = ((pair['right'] + pair['left'])/2).tolist()
                        else:
                            midpoint = next(iter(pair.values())).tolist()
                        traj_pts.append(midpoint)

                    # pillars list – store centres
                    pillars_json = []
                    for seq, pair in pillar_pairs.items():
                        if 'right' in pair and 'left' in pair:
                            centre = ((pair['right'] + pair['left'])/2).tolist()
                        else:
                            centre = next(iter(pair.values())).tolist()
                        pillars_json.append({"seq": int(seq), "center": centre})

                    # abutments – store both sides
                    abut_json = []
                    for seq, pair in abut_pairs.items():
                        abut_json.append({
                            "seq": int(seq),
                            "right": pair.get('right', []).tolist() if 'right' in pair else None,
                            "left": pair.get('left', []).tolist() if 'left' in pair else None
                        })

                    config["geometry"] = {
                        "trajectory_points": traj_pts,
                        "pillars": pillars_json,
                        "abutments": abut_json
                    }
                    debug_print(f"[INFO] Saved component geometry – traj:{len(traj_pts)} pillars:{len(pillars_json)} abut:{len(abut_json)}")
            except Exception as g_exc:
                debug_print(f"[WARNING] Could not embed geometry info in config: {g_exc}")

            # Save to project directory
            config_file = project_dir / "project_config.json"
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            debug_print(f"Project configuration saved to: {config_file}")
            
            # If map available, send geometry immediately
            if self.map_bridge and config.get("geometry"):
                def _to_wgs(pt_list):
                    if not self.current_context:
                        return [pt_list[1], pt_list[0]]  # fallback swap
                    lon, lat, _ = self.current_context.crs.to_wgs84(pt_list[0], pt_list[1], None)
                    return [lat, lon]

                traj_js = json.dumps([_to_wgs(pt) for pt in config["geometry"]["trajectory_points"]])
                self.map_bridge.updateTrajectory.emit(traj_js)

                pillars_js = json.dumps([_to_wgs(p['center']) for p in config["geometry"]["pillars"]])
                self.map_bridge.updatePillars.emit(pillars_js)
            
        except Exception as e:
            debug_print(f"Warning: Could not save project configuration: {e}")
        
    def update_crosssection_data(self):
        """Update cross section data by reprocessing with current parameters."""
        try:
            # Ensure data loader exists
            if not self.data_loader:
                QMessageBox.warning(self.ui, "Error", 
                                  "Data loader not available. Please load bridge data first.")
                return
            
            # CRUCIAL STEP: Re-parse project data from textbox to get current values
            # This allows users to adjust parameters before confirming project data
            # Skip EPSG check since it should already be properly set
            project_data = self.data_loader._parse_project_data(skip_epsg_check=True)
            if not project_data:
                QMessageBox.warning(self.ui, "Error", 
                                  "Could not parse current project data from textbox. Please check the project settings.")
                return
            
            debug_print(f"[UPDATE] Re-parsed project data from textbox")
            
            # Check if we have a cross-section image path
            # First check main app's path, then fall back to data loader's path
            cross_section_path = None
            if self.current_crosssection_path and Path(self.current_crosssection_path).exists():
                cross_section_path = self.current_crosssection_path
                debug_print(f"[UPDATE] Using main app's cross-section image: {cross_section_path}")
            elif (hasattr(self.data_loader, 'current_crosssection_path') and 
                  self.data_loader.current_crosssection_path and 
                  Path(self.data_loader.current_crosssection_path).exists()):
                cross_section_path = self.data_loader.current_crosssection_path
                debug_print(f"[UPDATE] Using data loader's cross-section image: {cross_section_path}")
            else:
                QMessageBox.warning(self.ui, "Error", 
                                  "No cross-section image found. Please load bridge data or select a cross-section template first.")
                return
            
            debug_print(f"[UPDATE] Using cross-section image: {cross_section_path}")
            
            # Get current parameters from freshly parsed project data
            input_scale_meters = project_data.get('input_scale_meters')
            epsilon_input = project_data.get('epsilonInput', 0.003)
            
            # Validate that input_scale_meters is available from textbox
            if input_scale_meters is None:
                QMessageBox.warning(self.ui, "Error", 
                                  "input_scale_meters not found in project settings. Please add 'input_scale_meters = [your_value]' to the project textbox.")
                return
            
            input_scale_meters = float(input_scale_meters)
            debug_print(f"[UPDATE] Using input_scale_meters from textbox: {input_scale_meters}")
            debug_print(f"[UPDATE] Using epsilonInput from textbox: {epsilon_input}")
            
            # Validate inputs
            if input_scale_meters <= 0 or epsilon_input <= 0:
                QMessageBox.warning(self.ui, "Error", 
                                  "Invalid input parameters. Check input_scale_meters and epsilonInput.")
                return
            
            debug_print(f"[UPDATE] Reprocessing cross-section with scale={input_scale_meters}, epsilon={epsilon_input}")
            
            # Clear existing graphics view and data
            graphics_view = self.ui.findChild(QWidget, "graphicsView_crosssection_2")
            if graphics_view and hasattr(graphics_view, 'setScene'):
                graphics_view.setScene(None)  # Clear the scene
                debug_print("[UPDATE] Cleared graphics view")
            
            # Clear existing processed data and contour lists
            self.processed_crosssection_image = None
            self.crosssection_transformed_points = None
            debug_print("[UPDATE] Cleared existing contour and processed data")

            # --------------------------------------------------------------
            # NEW APPROACH: delegate the image processing to BridgeDataLoader
            # --------------------------------------------------------------
            # Ensure the latest project parameters are available to the loader
            self.data_loader.project_data = project_data  # keep loader in sync

            # Perform the cross-section analysis via the loader. This will also
            # update the graphics view with the annotated image.
            self.data_loader._perform_cross_section_analysis(Path(cross_section_path))

            # Retrieve the freshly processed results from the loader so that the
            # rest of the application (e.g. 3-D modelling) can use them.
            self.processed_crosssection_image = getattr(self.data_loader, "processed_crosssection_image", None)
            self.crosssection_transformed_points = getattr(self.data_loader, "crosssection_transformed_points", None)
            
            # Also update the main app's cross-section path to match the data loader's
            # This ensures consistency for future operations
            if hasattr(self.data_loader, 'current_crosssection_path'):
                self.current_crosssection_path = self.data_loader.current_crosssection_path
                debug_print(f"[UPDATE] Synchronized main app's cross-section path: {self.current_crosssection_path}")

            if self.crosssection_transformed_points is None:
                QMessageBox.warning(self.ui, "Error",
                                     "Cross-section analysis failed. Please check the image and parameters.")
                return

            # Provide user feedback
            debug_print(f"[UPDATE] Cross-section data updated successfully – {len(self.crosssection_transformed_points)} points")
            QMessageBox.information(
                self.ui,
                "Cross-Section Updated",
                f"Cross-section shape extraction updated successfully!\n\n"
                f"Parameters used:\n"
                f"• Scale: {input_scale_meters} m\n"
                f"• Epsilon: {epsilon_input}\n"
                f"• Contour points: {len(self.crosssection_transformed_points)}\n\n"
                f"You can continue adjusting parameters and clicking 'Update Crosssection' "
                f"until you're satisfied with the result, then click 'Confirm Project Data'.")
                                      
        except Exception as e:
            QMessageBox.critical(self.ui, "Error", 
                               f"Failed to update cross section data: {str(e)}")
            
            traceback.print_exc()
    
    def display_crosssection_image(self, image):
        """Display the processed cross section image in the graphics view."""
        try:
            # Find the graphics view widget
            graphics_view = self.ui.findChild(QWidget, "graphicsView_crosssection_2")
            if not graphics_view:
                debug_print("Warning: graphicsView_crosssection_2 not found")
                return
            
            # Convert BGR to RGB for Qt display
            image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
            height, width, channels = image_rgb.shape
            bytes_per_line = channels * width
            
            # Create QImage
            q_image = QImage(image_rgb.data, width, height, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(q_image)
            
            # Create scene and add pixmap
            scene = QGraphicsScene()
            scene.addPixmap(pixmap)
            
            # Set scene to graphics view
            graphics_view.setScene(scene)
            graphics_view.fitInView(scene.itemsBoundingRect(), 1)  # Qt.KeepAspectRatio = 1
            
        except Exception as e:
            debug_print(f"Error displaying cross section image: {e}")
    
    # =====================================================================
    # Tab 1 - Photogrammetric Flight Functions  
    # =====================================================================
    

    def toggle_draw_trajectory(self):
        """Toggle trajectory drawing mode."""
        debug_print("[DEBUG] toggle_draw_trajectory called")
        
        if self.drawing_mode == 'trajectory':
            debug_print("[MODE] Exited trajectory drawing mode")
            self.drawing_mode = None
            self._reset_all_drawing_buttons()
            self._disable_map_click_handler()
            # Remove drawing mode indicator
            self._remove_drawing_mode_indicator()
        else:
            debug_print("[MODE] Entered trajectory drawing mode - click map to add points")
            self.drawing_mode = 'trajectory'
            self._reset_all_drawing_buttons()
            self._set_button_state("btn_tab1_DrawTrajectory", True)
            self._enable_map_click_handler('trajectory')
            # Add drawing mode indicator
            self._add_drawing_mode_indicator('trajectory')
    
    def toggle_mark_pillars(self):
        """Toggle pillar marking mode."""
        debug_print("[DEBUG] toggle_mark_pillars called")
        
        if self.drawing_mode == 'pillars':
            debug_print("[MODE] Exited pillar marking mode")
            self.drawing_mode = None
            self._reset_all_drawing_buttons()
            self._disable_map_click_handler()
            # Remove drawing mode indicator
            self._remove_drawing_mode_indicator()
        else:
            debug_print("[MODE] Entered pillar marking mode - click map to add pillars")
            self.drawing_mode = 'pillars'
            self._reset_all_drawing_buttons()
            self._set_button_state("btn_tab1_mark_pillars", True)
            self._enable_map_click_handler('pillars')
            # Add drawing mode indicator
            self._add_drawing_mode_indicator('pillars')
    
    def toggle_safety_zones(self):
        """Toggle safety zone drawing mode."""
        debug_print("[DEBUG] toggle_safety_zones called")
        
        if self.drawing_mode == 'safety_zones':
            debug_print("[MODE] Exited safety zone drawing mode")
            self.drawing_mode = None
            self._reset_all_drawing_buttons()
            self._disable_map_click_handler()
            # Complete current zone if it has points
            if len(self.current_zone_points) >= 3:
                self._complete_current_safety_zone()
            # Remove drawing mode indicator
            self._remove_drawing_mode_indicator()
        else:
            debug_print("[MODE] Entered safety zone drawing mode")
            self.drawing_mode = 'safety_zones'
            self._reset_all_drawing_buttons()
            self._set_button_state("btn_tab1_SafetyZones", True)
            self._enable_map_click_handler('safety_zones')
            # Add drawing mode indicator
            self._add_drawing_mode_indicator('safety_zones')
    
    def _reset_all_drawing_buttons(self):
        """Reset all drawing mode buttons to their default state."""
        self._set_button_state("btn_tab1_DrawTrajectory", False)
        self._set_button_state("btn_tab1_mark_pillars", False)
        self._set_button_state("btn_tab1_SafetyZones", False)
    
    def _set_button_state(self, button_name: str, active: bool):
        """Set visual state of a button (highlighted when active)."""
        button = self.ui.findChild(QWidget, button_name)
        if button and hasattr(button, 'setStyleSheet'):
            if active:
                button.setStyleSheet("background-color: #4CAF50; color: white;")
            else:
                button.setStyleSheet("")  # Reset to default style
    
    def _add_drawing_mode_indicator(self, mode='safety_zones'):
        """Add a visual indicator to show that drawing mode is active."""
        mode_configs = {
            'trajectory': {
                'color': 'rgba(0, 0, 255, 0.8)',
                'icon': '🔵',
                'title': 'Trajectory Drawing Mode',
                'description': 'Click anywhere to add trajectory points'
            },
            'pillars': {
                'color': 'rgba(0, 128, 0, 0.8)',
                'icon': '🟢',
                'title': 'Pillar Marking Mode',
                'description': 'Click anywhere to add pillar pairs'
            },
            'safety_zones': {
                'color': 'rgba(255, 0, 0, 0.8)',
                'icon': '🔴',
                'title': 'Safety Zone Drawing Mode',
                'description': 'Click anywhere to add corner points'
            }
        }
        
        config = mode_configs.get(mode, mode_configs['safety_zones'])
        
        js_code = f'''
            console.log('Adding {mode} drawing mode indicator...');
            
            // Remove existing indicator if any
            if (window.drawingModeIndicator) {{
                map.removeControl(window.drawingModeIndicator);
            }}
            
            // Create indicator control
            window.drawingModeIndicator = L.control({{position: 'topright'}});
            window.drawingModeIndicator.onAdd = function(map) {{
                var div = L.DomUtil.create('div', 'drawing-mode-indicator');
                div.innerHTML = '<div style="background: {config['color']}; color: white; padding: 8px 12px; border-radius: 4px; font-weight: bold; font-size: 12px; box-shadow: 0 2px 4px rgba(0,0,0,0.3);">{config['icon']} {config['title']}<br><small>{config['description']}</small></div>';
                return div;
            }};
            
            window.drawingModeIndicator.addTo(map);
            console.log('{mode} drawing mode indicator added');
        '''
        self.debug_page.runJavaScript(js_code)
    
    def _remove_drawing_mode_indicator(self):
        """Remove the drawing mode indicator."""
        js_code = '''
            console.log('Removing drawing mode indicator...');
            if (window.drawingModeIndicator) {
                map.removeControl(window.drawingModeIndicator);
                window.drawingModeIndicator = null;
                console.log('Drawing mode indicator removed');
            }
        '''
        self.debug_page.runJavaScript(js_code)
    
    def build_flight_model(self):
        """Validate inputs and move to Tab 2 if everything is ready."""
        try:
            # ------------------------------------------------------------------
            # 1. Validate that required inputs are available
            # ------------------------------------------------------------------
            missing = []
            # Trajectory – need at least 2 points
            if len(self.current_trajectory) < 2:
                missing.append("trajectory (≥2 points)")

            # Pillars – need an even amount ≥2 (pairs)
            if len(self.current_pillars) < 2 or len(self.current_pillars) % 2 != 0:
                missing.append("pillar pairs (even number, ≥2 points)")

            # Cross-section shape – need processed points
            cs_pts = getattr(self, 'crosssection_transformed_points', None)
            if cs_pts is None or len(cs_pts) == 0:
                missing.append("cross-section 2D shape")

            # If something missing – inform user and stop
            if missing:
                msg = "Missing or incomplete input:\n  • " + "\n  • ".join(missing)
                debug_print("\n===================== BUILD MODEL ABORTED =====================")
                debug_print(msg)
                debug_print("================================================================\n")
                QMessageBox.warning(self.ui, "Build Model – Missing Data", msg)
                return

            # ------------------------------------------------------------------
            # 2. Print out the gathered data clearly in terminal
            # ------------------------------------------------------------------
            debug_print("\n===================== FINAL DATA FOR FLIGHT MODEL =====================")
            # Trajectory
            debug_print(f"Trajectory – {len(self.current_trajectory)} points:")
            for idx, pt in enumerate(self.current_trajectory, 1):
                debug_print(f"  {idx:02d}: lat={pt[0]:.6f}, lon={pt[1]:.6f}")

            # Pillar pairs
            debug_print(f"\nPillar Pairs – {len(self.current_pillars)//2} pairs:")
            for i in range(0, len(self.current_pillars), 2):
                p1 = self.current_pillars[i]
                p2 = self.current_pillars[i+1]
                pair_idx = i//2 + 1
                debug_print(f"  Pair {pair_idx:02d}: {p1['id']} ({p1['lat']:.6f},{p1['lon']:.6f})  ↔  {p2['id']} ({p2['lat']:.6f},{p2['lon']:.6f})")

            # Cross-section shape
            debug_print(f"\nCross-section 2D shape – {len(cs_pts)} points:")
            for idx, pt in enumerate(cs_pts, 1):
                try:
                    x, y = pt[0], pt[1]
                except Exception:
                    # Fallback if stored differently (e.g., tuple)
                    x, y = pt[:2]
                debug_print(f"  {idx:02d}: x={x:.3f}, y={y:.3f}")

            # Safety zones
            debug_print(f"\nSafety Zones – {len(self.current_safety_zones)} zones:")
            for idx, zone in enumerate(self.current_safety_zones, 1):
                zone_id = zone.get('id', f'Zone{idx}')
                points_count = len(zone.get('points', []))
                debug_print(f"  Zone {idx:02d}: {zone_id} ({points_count} points)")
                for pidx, pt in enumerate(zone.get('points', []), 1):
                    debug_print(f"    {pidx:02d}: lat={pt[0]:.6f}, lon={pt[1]:.6f}")

            debug_print("================================================================\n")


            # ------------------------------------------------------------------
            # 3. Switch UI to Tab 2
            # ------------------------------------------------------------------
            if self.tab_widget and hasattr(self.tab_widget, 'setCurrentIndex'):
                self.tab_widget.setCurrentIndex(2)
            if self.left_panel_stacked and hasattr(self.left_panel_stacked, 'setCurrentIndex'):
                self.left_panel_stacked.setCurrentIndex(2)
            debug_print("[INFO] All inputs present – switched to Tab 2 for next steps.")

            # --------------------------------------------------------------
            # NEW: build improved 3-D geometric model and visualise it
            # --------------------------------------------------------------
            try:
                self.build_improved_3d_bridge_model()
                # Set to top view for better initial perspective
                self.change_to_top_view()
            except Exception as _bm_exc:
                debug_print(f"[WARNING] build_improved_3d_bridge_model failed: {_bm_exc}")

        except Exception as e:
            debug_print(f"[ERROR] build_flight_model failed: {e}")

            QMessageBox.critical(self.ui, "Error", f"Failed to build model: {str(e)}")
    
    def _center_map_on_trajectory(self, traj_wgs84, pillars_wgs84=None, padding_px=60):
        """
        Fit the map to show the full bridge (trajectory + pillars) with a bit of padding.
        This never mutates stored geometry; it only drives the viewer.
        """
        # Collect points
        pts = []
        for p in (traj_wgs84 or []):
            # our converters return [lat, lon, alt]
            if isinstance(p, (list, tuple)) and len(p) >= 2:
                pts.append((float(p[0]), float(p[1])))
        for pi in (pillars_wgs84 or []):
            # pillar dicts: {'id','lat','lon','z'}
            if isinstance(pi, dict) and 'lat' in pi and 'lon' in pi:
                pts.append((float(pi['lat']), float(pi['lon'])))

        if not pts:
            return  # nothing to fit

        # Compute bounds (in lat/lon)
        lats = [p[0] for p in pts]
        lons = [p[1] for p in pts]
        south, north = min(lats), max(lats)
        west,  east  = min(lons), max(lons)

        # Pad a tiny amount to avoid tight clipping
        pad_deg = 0.0005
        south -= pad_deg; north += pad_deg; west -= pad_deg; east += pad_deg

        # Fallback: approximate zoom + center and call your set-view hook
        lat_c = (south + north) * 0.5
        lon_c = (west  + east)  * 0.5

        # Viewport size (try to read actual widget; fall back to sensible defaults)
        try:
            vw = int(getattr(self.ui, 'mapView', self.ui).width())
            vh = int(getattr(self.ui, 'mapView', self.ui).height())
        except Exception:
            vw, vh = 1200, 800

        # zoom = self._approx_zoom_for_bounds(south, west, north, east, vw, vh)
        # self._set_map_view(lat_c, lon_c, zoom)

    def undo_trajectory(self):
        """Undo last trajectory point."""
        if self.current_trajectory:
            # Move last point to redo stack
            removed_point = self.current_trajectory.pop()
            self.trajectory_redo_stack.append(removed_point)
            debug_print(f"[TRAJECTORY] Undid point: {removed_point}")
            
            # Update map
            self._update_trajectory_on_map()
        else:
            debug_print("[UNDO] No trajectory points to undo")
    
    def redo_trajectory(self):
        """Redo last undone trajectory point."""
        if self.trajectory_redo_stack:
            # Move point back from redo stack
            point = self.trajectory_redo_stack.pop()
            self.current_trajectory.append(point)
            debug_print(f"[TRAJECTORY] Redid point: {point}")
            
            # Update map
            self._update_trajectory_on_map()
        else:
            debug_print("[REDO] No trajectory points to redo")
    
    def undo_pillar(self):
        """Undo last pillar."""
        if self.current_pillars:
            # Move last pillar to redo stack
            removed_pillar = self.current_pillars.pop()
            self.pillar_redo_stack.append(removed_pillar)
            debug_print(f"[PILLARS] Undid pillar: {removed_pillar['id']}")
            
            # Update map
            self._update_pillars_on_map()
        else:
            debug_print("[UNDO] No pillars to undo")
    
    def redo_pillar(self):
        """Redo last undone pillar."""
        if self.pillar_redo_stack:
            # Move pillar back from redo stack
            pillar = self.pillar_redo_stack.pop()
            self.current_pillars.append(pillar)
            debug_print(f"[PILLARS] Redid pillar: {pillar['id']}")
            
            # Update map
            self._update_pillars_on_map()
        else:
            debug_print("[REDO] No pillars to redo")
    
    def undo_safety(self):
        """Undo last safety zone action."""
        if self.current_zone_points:
            # Remove last point from current zone and push to redo stack
            removed_point = self.current_zone_points.pop()
            self.zone_points_redo_stack.append(removed_point)
            debug_print(f"[SAFETY_ZONE] Undid point: {removed_point}")
            self._update_safety_zones_on_map()
        elif self.current_safety_zones:
            # If no current points, undo last completed zone
            removed_zone = self.current_safety_zones.pop()
            self.safety_zones_redo_stack.append(removed_zone)
            debug_print(f"[SAFETY_ZONE] Undid completed zone: {removed_zone['id']}")
            self._update_safety_zones_on_map()
        else:
            debug_print("[UNDO] Nothing to undo in safety zones")
    
    def redo_safety(self):
        """Redo last undone safety zone."""
        if self.safety_zones_redo_stack:
            # Restore zone from redo stack
            zone = self.safety_zones_redo_stack.pop()
            self.current_safety_zones.append(zone)
            debug_print(f"[SAFETY_ZONE] Redid zone: {zone['id']}")
            self._update_safety_zones_on_map()
        elif self.zone_points_redo_stack:
            # Redo last undone point within current zone
            point = self.zone_points_redo_stack.pop()
            self.current_zone_points.append(point)
            debug_print(f"[SAFETY_ZONE] Redid point: {point}")
            self._update_safety_zones_on_map()
        else:
            debug_print("[REDO] No safety zones to redo")
    
    def save_project(self):
        """Handle save project action."""
        try:
            if self.bridge_session:
                # Session already auto-saves, but we can provide user feedback
                QMessageBox.information(self.ui, "Success", "Project saved")
            else:
                QMessageBox.warning(self.ui, "Warning", "No active project to save")
                
        except Exception as e:
            QMessageBox.critical(self.ui, "Error", f"Save failed: {str(e)}")
    
    def add_safety_zone(self):
        """Start a new safety zone - complete current one and begin new."""
        debug_print("[DEBUG] add_safety_zone called - starting new zone")
        
        # Complete current zone if it has enough points
        if len(self.current_zone_points) >= 3:
            self._complete_current_safety_zone()
            debug_print(f"[SAFETY_ZONE] Completed zone with {len(self.current_zone_points)} points, starting new zone")
        elif len(self.current_zone_points) > 0:
            debug_print(f"[SAFETY_ZONE] Current zone has only {len(self.current_zone_points)} points (need 3+), discarding and starting new zone")
        
        # Clear current zone points and start new zone
        self.current_zone_points = []
        self.zone_points_redo_stack.clear()
        self.current_zone_id += 1
        
        # If not in safety zone drawing mode, enter it
        if self.drawing_mode != 'safety_zones':
            self.toggle_safety_zones()
        
        debug_print(f"[SAFETY_ZONE] Started new zone ID: {self.current_zone_id}")

    def _complete_current_safety_zone(self):
        """Complete the current safety zone and add it to the zones list."""
        if len(self.current_zone_points) >= 3:
            zone = {
                'id': f"SZ{self.current_zone_id}",
                'points': self.current_zone_points.copy()
            }
            self.current_safety_zones.append(zone)
            self.safety_zones_history.append(self.current_safety_zones.copy())
            
            debug_print(f"[SAFETY_ZONE] Completed zone {zone['id']} with {len(zone['points'])} points")
            debug_print(f"[SAFETY_ZONE] Total completed zones: {len(self.current_safety_zones)}")
            debug_print(f"[SAFETY_ZONE] Current safety zones list: {[sz['id'] for sz in self.current_safety_zones]}")
            debug_print(f"[SAFETY_ZONEXXXXXXXXXXXXXXXXXX] Current safety zones list: {self.current_safety_zones}")
            # Clear current zone points
            self.current_zone_points = []
            # Clear point redo stack as zone is completed
            self.zone_points_redo_stack.clear()
            
            # Update map visualization
            self._update_safety_zones_on_map()
        else:
            debug_print(f"[SAFETY_ZONE] Cannot complete zone with only {len(self.current_zone_points)} points (need 3+)")

    def _update_safety_zones_on_map(self):
        """Update safety zone visualization on map."""
        debug_print(f"[DEBUG] Updating safety zones on map: {len(self.current_safety_zones)} completed zones, {len(self.current_zone_points)} current points")
        
        # Always send completed zones (including empty list to clear)
        self._send_safety_zones_to_map(self.current_safety_zones)
        
        # Send current zone being drawn (or empty to clear)
        current_zone = {
            'id': f"SZ{self.current_zone_id}_temp",
            'points': self.current_zone_points
        }
        self._send_current_zone_to_map(current_zone)

    def _send_safety_zones_to_map(self, zones):
        """Send completed safety zones to the map for visualization."""
        debug_print(f"[DEBUG] Sending {len(zones)} completed safety zones to map")
        
        js_code = f'''
            console.log('Updating safety zones on map...');
            if (window.safetyZoneLayer) {{
                // Clear existing completed zones
                window.safetyZoneLayer.eachLayer(function(layer) {{
                    if (layer.options.className && layer.options.className.includes('completed')) {{
                        window.safetyZoneLayer.removeLayer(layer);
                    }}
                }});
                
                var zones = {zones};
                console.log('Received ' + zones.length + ' completed zones');
                
                // Check if we're in safety zone drawing mode
                var isDrawingMode = window.currentDrawingMode === 'safety_zones';
                
                zones.forEach(function(zone) {{
                    if (zone.points.length >= 3) {{
                        var polygon = L.polygon(zone.points, {{
                            color: 'red',
                            weight: 2,
                            opacity: 0.8,
                            fillColor: 'red',
                            fillOpacity: 0.3,
                            className: 'completed-safety-zone'
                        }}).addTo(window.safetyZoneLayer);

                        // Store zone ID on the polygon for later restoration
                        polygon.zoneId = zone.id;

                        // Only bind popup if not in drawing mode
                        if (!isDrawingMode) {{
                            polygon.bindPopup('Safety Zone: ' + zone.id);
                        }} else {{
                            // In drawing mode, make sure no popup is bound and layer is non-interactive
                            polygon.options.interactive = false;
                            // Also remove any existing popup binding
                            if (polygon.getPopup()) {{
                                polygon.unbindPopup();
                            }}
                        }}

                        console.log('Drew completed safety zone: ' + zone.id + ' with ' + zone.points.length + ' points');
                    }}
                }});
                
                console.log('Completed safety zones visualization updated');
            }}
        '''
        self.debug_page.runJavaScript(js_code)

    def _send_current_zone_to_map(self, current_zone):
        """Send current zone being drawn to the map for visualization."""
        debug_print(f"[DEBUG] Sending current zone {current_zone['id']} with {len(current_zone['points'])} points to map")
        
        js_code = f'''
            console.log('Updating current safety zone on map...');
            if (window.safetyZoneLayer) {{
                // Clear existing current zone
                window.safetyZoneLayer.eachLayer(function(layer) {{
                    if (layer.options.className && layer.options.className.includes('current')) {{
                        window.safetyZoneLayer.removeLayer(layer);
                    }}
                }});
                
                var zone = {current_zone};
                console.log('Received current zone with ' + zone.points.length + ' points');
                
                if (zone.points.length >= 1) {{
                    // Draw points as markers
                    zone.points.forEach(function(point, index) {{
                        var marker = L.circleMarker(point, {{
                            color: 'darkred',
                            fillColor: 'red',
                            fillOpacity: 0.8,
                            radius: 4,
                            className: 'current-safety-zone'
                        }}).addTo(window.safetyZoneLayer);
                        // Don't bind popup to current zone points to avoid interference
                    }});
                    
                    // Draw polygon if 3+ points
                    if (zone.points.length >= 3) {{
                        var polygon = L.polygon(zone.points, {{
                            color: 'red',
                            weight: 2,
                            opacity: 0.6,
                            fillColor: 'red',
                            fillOpacity: 0.2,
                            dashArray: '5, 10',
                            className: 'current-safety-zone'
                        }}).addTo(window.safetyZoneLayer);
                        
                        // Don't bind popup to current zone polygon to avoid interference
                        console.log('Drew current safety zone polygon with ' + zone.points.length + ' points');
                    }} else if (zone.points.length == 2) {{
                        // Draw line for 2 points
                        var line = L.polyline(zone.points, {{
                            color: 'red',
                            weight: 2,
                            opacity: 0.6,
                            dashArray: '5, 10',
                            className: 'current-safety-zone'
                        }}).addTo(window.safetyZoneLayer);
                        
                        console.log('Drew current safety zone line with 2 points');
                    }}
                }}
                
                console.log('Current safety zone visualization updated');
            }}
        '''
        self.debug_page.runJavaScript(js_code)

    def on_tab_changed(self, index):
        """Handle tab change events."""
        debug_print(f"[DEBUG] Tab changed to index: {index}")
        if index == 1:  # Tab 1 - Flight Planning
            debug_print("Navigated to Tab 1 - Flight Planning")
            # Update map visualization when entering Tab 1
            if hasattr(self, 'debug_page') and self.debug_page:
                debug_print("[DEBUG] Triggering map visualization update...")
                self._update_map_visualization()
        elif index == 0:  # Tab 0 - Project Setup
            debug_print("Navigated to Tab 0 - Project Setup")

    def _enable_map_click_handler(self, mode):
        """Enable click handling on the map for the specified mode."""
        debug_print(f"[DEBUG] Enabling map click handler for mode: {mode}")

        js_code = f'''
            console.log('Enabling click handler for mode: {mode}');
            window.currentDrawingMode = '{mode}';

            // Remove existing click handlers
            map.off('click');

            // For safety zone mode, completely disable popup bindings and interactivity from existing zones
            if ('{mode}' === 'safety_zones' && window.safetyZoneLayer) {{
                console.log('Disabling popups and interactivity for existing safety zones in drawing mode');
                window.safetyZoneLayer.eachLayer(function(layer) {{
                    if (layer.options.className && layer.options.className.includes('completed')) {{
                        // Remove popup binding completely
                        if (layer.getPopup()) {{
                            layer.unbindPopup();
                        }}
                        // Disable all interactivity and click events
                        layer.options.interactive = false;
                        // Also remove any click event listeners that might exist
                        layer.off('click');
                        layer.off('popupopen');
                        layer.off('popupclose');
                    }}
                }});
            }}

            // Prevent any popups from opening in drawing mode
            if ('{mode}' === 'safety_zones') {{
                // Override popup opening behavior
                map.on('popupopen', function(e) {{
                    if (window.currentDrawingMode === 'safety_zones') {{
                        console.log('Blocking popup in safety zone drawing mode');
                        map.closePopup();
                        e.popup.remove();
                    }}
                }});
            }}

            // Add new click handler
            map.on('click', function(e) {{
                console.log('Map clicked at: ' + e.latlng.lat + ', ' + e.latlng.lng + ' (mode: {mode})');

                // Store click data globally for Python to retrieve
                window.lastClickData = {{
                    mode: '{mode}',
                    lat: e.latlng.lat,
                    lng: e.latlng.lng
                }};

                console.log('Click data stored, notifying Python...');

                // Signal to Python that click occurred (will be picked up by timer)
                window.clickOccurred = true;
            }});

            console.log('Click handler enabled for mode: {mode}');
        '''
        self.debug_page.runJavaScript(js_code)
        
        # Start polling for clicks if not already running
        if not hasattr(self, 'click_timer') or not self.click_timer.isActive():
            self._start_click_polling()

    def _start_click_polling(self):
        """Start polling for map clicks."""
        debug_print("[DEBUG] Starting click polling...")
        
        def check_for_clicks():
            js_check = '''
                if (window.clickOccurred && window.lastClickData) {
                    var data = JSON.stringify(window.lastClickData);
                    window.clickOccurred = false;  // Reset flag
                    window.lastClickData = null;   // Clear data
                    data;  // Return the data
                } else {
                    null;  // No click occurred
                }
            '''
            
            def handle_result(result):
                if result:
                    debug_print(f"[POLL] Got click data: {result}")
                    self.handle_map_click(result)
            
            self.debug_page.runJavaScript(js_check, handle_result)
        

        self.click_timer = QTimer()
        self.click_timer.timeout.connect(check_for_clicks)
        self.click_timer.start(100)  # Check every 100ms

    def _disable_map_click_handler(self):
        """Disable click handling on the map."""
        debug_print("[DEBUG] Disabling map click handler")

        # Stop polling timer
        if hasattr(self, 'click_timer'):
            self.click_timer.stop()

        js_code = '''
            console.log('Disabling map click handler');
            window.currentDrawingMode = null;
            window.clickOccurred = false;
            window.lastClickData = null;
            map.off('click');

            // Remove the popup blocking handler we added for drawing mode
            map.off('popupopen');

            // Restore popup bindings and interactivity to safety zones
            if (window.safetyZoneLayer) {
                console.log('Restoring popup bindings to safety zones');
                window.safetyZoneLayer.eachLayer(function(layer) {
                    if (layer.options.className && layer.options.className.includes('completed')) {
                        // Restore interactivity
                        layer.options.interactive = true;
                        // Re-bind popup with zone information
                        if (layer.zoneId) {
                            layer.bindPopup('Safety Zone: ' + layer.zoneId);
                        }
                    }
                });
            }

            console.log('Click handler disabled');
        '''
        self.debug_page.runJavaScript(js_code)
        
        # Re-enable popups for safety zones when drawing mode is disabled
        self._update_safety_zones_on_map()

    # =====================================================================
    # Tab 2 - Point Cloud Loading and Coordinate System Transformation
    # =====================================================================
    
    def load_point_cloud(self):
        """Load and display a point cloud file with coordinate system transformation."""
        try:
            debug_print("[POINT_CLOUD] Loading point cloud with coordinate system dialog...")
            
            # Check if we have the 3D visualizer and coordinate transformation
            if not hasattr(self, 'visualizer') or self.visualizer is None:
                QMessageBox.information(self.ui, "Info", "No 3D viewer available. Please build the bridge model first using the 'Build Model' button.")
                return
            
            if not hasattr(self, '_last_transform_func') or not self._last_transform_func:
                QMessageBox.warning(self.ui, "Warning", 
                                  "No coordinate transformation available. Please build the bridge model first using 'Build Model' button.")
                return
            
            # Step 1: Select point cloud file
            file_path, _ = QFileDialog.getOpenFileName(
                self.ui,
                "Select Point Cloud File",
                "",
                "Point Cloud Files (*.ply *.pcd *.xyz *.las *.laz *.pts);;PLY Files (*.ply);;PCD Files (*.pcd);;XYZ Files (*.xyz);;LAS Files (*.las *.laz);;PTS Files (*.pts);;All Files (*)"
            )
            
            if not file_path:
                return
            
            # Step 2: Show coordinate system selection dialog
            point_cloud_crs_info = self._show_coordinate_system_dialog(file_path)
            if not point_cloud_crs_info:
                return
            
            # Step 3: Load and transform point cloud
            success = self._load_and_transform_point_cloud(file_path, point_cloud_crs_info)
            
            if success:
                # Switch to top view for alignment validation
                self.change_to_top_view()
                debug_print("[POINT_CLOUD] ✅ Point cloud loaded and transformed successfully!")
            
        except Exception as e:
            debug_print(f"[POINT_CLOUD] ❌ Error: {e}")
            
            traceback.print_exc()
            QMessageBox.critical(self.ui, "Error", f"Point cloud loading failed: {str(e)}")

    def _show_coordinate_system_dialog(self, file_path):
        """Show dialog to select coordinate system, vertical datum, and optional data reduction."""
        


        try:
            # Create dialog
            dialog = QDialog(self.ui)
            dialog.setWindowTitle("Point Cloud Coordinate System")
            dialog.setModal(True)
            dialog.resize(500, 520)

            layout = QVBoxLayout(dialog)

            # Header
            header = QLabel(f"Specify coordinate system for:\n{Path(file_path).name}")
            header.setStyleSheet("font-weight: bold; font-size: 14px; margin-bottom: 15px;")
            layout.addWidget(header)

            # Point cloud info
            info_group = QGroupBox("Point Cloud Information")
            info_layout = QVBoxLayout(info_group)
            info_text = QTextEdit()
            info_text.setMaximumHeight(100)
            info_text.setReadOnly(True)
            info_text.setPlainText(self._get_point_cloud_info(file_path))
            info_layout.addWidget(info_text)
            layout.addWidget(info_group)

            # Coordinate system selection
            coord_group = QGroupBox("Coordinate System Selection")
            coord_layout = QVBoxLayout(coord_group)

            # Coordinate system dropdown
            coord_label = QLabel("Coordinate System:")
            coord_layout.addWidget(coord_label)

            coord_combo = QComboBox()
            coord_systems = CoordinateSystemRegistry.get_coordinate_systems()

            # Set default coordinate system
            default_coord = "custom"  # Custom EPSG as default
            if hasattr(self, 'selected_coord_system') and self.selected_coord_system:
                default_coord = self.selected_coord_system
                debug_print(f"[COORD_DIALOG] Using last coordinate system: {default_coord}")
            else:
                debug_print(f"[COORD_DIALOG] Using default coordinate system: {default_coord}")

            default_index = 0
            for i, (key, display_name) in enumerate(coord_systems):
                coord_combo.addItem(display_name, key)
                if (key == default_coord or
                    (default_coord and default_coord.lower() in display_name.lower())):
                    default_index = i

            coord_combo.setCurrentIndex(default_index)
            coord_layout.addWidget(coord_combo)

            # Custom EPSG input (hidden by default)
            custom_layout = QHBoxLayout()
            custom_label = QLabel("Custom EPSG Code:")
            custom_input = QLineEdit()
            custom_input.setPlaceholderText("e.g. 31370 for Lambert72")
            custom_layout.addWidget(custom_label)
            custom_layout.addWidget(custom_input)
            custom_widget = QWidget()
            custom_widget.setLayout(custom_layout)
            custom_widget.setVisible(False)
            coord_layout.addWidget(custom_widget)



            layout.addWidget(coord_group)

            # Show/hide custom EPSG based on selection
            def on_coord_changed():
                is_custom = coord_combo.currentData() == "custom"
                custom_widget.setVisible(is_custom)

            coord_combo.currentTextChanged.connect(on_coord_changed)

            # ---------------- Data reduction (optional) -----------------
            reduce_group = QGroupBox("Data Reduction (optional)")
            reduce_layout = QVBoxLayout(reduce_group)

            reduce_enable = QCheckBox("Reduce points before saving (faster write, smaller file)")
            reduce_layout.addWidget(reduce_enable)

            reduce_row = QHBoxLayout()
            reduce_method = QComboBox()
            reduce_method.addItem("Random %", "random")
            reduce_method.addItem("Every Nth point", "nth")
            reduce_method.addItem("Voxel size (m)", "voxel")
            reduce_value = QLineEdit()
            reduce_value.setPlaceholderText("e.g. 25  (means 25% / every 25th / 0.25 m)")
            reduce_value.setEnabled(False)
            reduce_method.setEnabled(False)

            def on_reduce_toggled(checked):
                reduce_method.setEnabled(checked)
                reduce_value.setEnabled(checked)

            reduce_enable.toggled.connect(on_reduce_toggled)

            reduce_row.addWidget(reduce_method)
            reduce_row.addWidget(reduce_value)
            reduce_layout.addLayout(reduce_row)

            layout.addWidget(reduce_group)
            # ------------------------------------------------------------

            # Buttons
            button_layout = QHBoxLayout()
            ok_button = QPushButton("Load Point Cloud")
            cancel_button = QPushButton("Cancel")

            ok_button.clicked.connect(dialog.accept)
            cancel_button.clicked.connect(dialog.reject)

            button_layout.addWidget(cancel_button)
            button_layout.addWidget(ok_button)
            layout.addLayout(button_layout)

            # Execute dialog
            if dialog.exec() == QDialog.Accepted:
                # Get selected coordinate system
                coord_key = coord_combo.currentData()

                if coord_key == "custom":
                    try:
                        custom_epsg = int(custom_input.text().strip())
                        coord_info = {"type": "custom", "epsg": custom_epsg, "key": "custom", "name": f"EPSG:{custom_epsg}"}
                    except ValueError:
                        QMessageBox.warning(dialog, "Invalid Input", "Please enter a valid EPSG code (numeric).")
                        return None
                else:
                    system_info = CoordinateSystemRegistry.get_system_info(coord_key)
                    if not system_info:
                        QMessageBox.warning(dialog, "Error", f"Invalid coordinate system: {coord_key}")
                        return None
                    coord_info = {
                        "type": "predefined",
                        "epsg": system_info["epsg"],
                        "key": coord_key,
                        "name": system_info["name"]
                    }



                # Reduction payload
                reduction = None
                if reduce_enable.isChecked():
                    method = reduce_method.currentData()
                    txt = reduce_value.text().strip()
                    if not txt:
                        QMessageBox.warning(dialog, "Missing value",
                                            "Please provide a value for data reduction (e.g. 25).")
                        return None
                    try:
                        if method == "random":
                            val = float(txt)  # percentage (0–100]
                            if not (0 < val <= 100):
                                raise ValueError("Percentage must be in (0, 100].")
                        elif method == "nth":
                            val = int(txt)    # every Nth (>=2)
                            if val < 2:
                                raise ValueError("N must be >= 2.")
                        elif method == "voxel":
                            val = float(txt)  # meters (>0)
                            if val <= 0:
                                raise ValueError("Voxel size must be > 0.")
                        reduction = {"enabled": True, "method": method, "value": val}
                    except Exception as ex:
                        QMessageBox.warning(dialog, "Invalid value", f"{ex}")
                        return None

                result = {
                    "coordinate_system": coord_info,
                    "reduction": reduction or {"enabled": False}
                }

                debug_print(f"[COORD_DIALOG] Selected: {coord_info['name']}")
                debug_print(f"[COORD_DIALOG] Coordinate system key: {coord_info['key']}, name: {coord_info['name']}")
                if result["reduction"]["enabled"]:
                    debug_print(f"[COORD_DIALOG] Reduction: method={result['reduction']['method']} value={result['reduction']['value']}")
                return result

            return None

        except Exception as e:
            debug_print(f"[COORD_DIALOG] Error in coordinate system dialog: {e}")
            
            traceback.print_exc()
            return None

    def _reduce_point_cloud_arrays(self, points, rgb_data, reduction):
        """
        Return (points_red, rgb_red, info_dict) given reduction settings.
        Applies reduction ONLY if enabled. Keeps color alignment if provided.
        """
        

        if not reduction or not reduction.get("enabled"):
            return points, rgb_data, {"reduced": False}

        method = reduction.get("method")
        val = reduction.get("value")
        n = len(points)
        idx = None

        if n == 0:
            return points, rgb_data, {"reduced": False}

        if method == "random":
            # val: percentage (0–100]
            frac = max(0.0, min(1.0, float(val) / 100.0))
            if frac >= 0.999:
                return points, rgb_data, {"reduced": False}
            rng = np.random.default_rng(42)  # deterministic for reproducibility
            k = max(1, int(n * frac))
            idx = rng.choice(n, size=k, replace=False)

        elif method == "nth":
            # val: every Nth point (N >= 2)
            N = int(val)
            if N <= 1:
                return points, rgb_data, {"reduced": False}
            idx = np.arange(0, n, N, dtype=np.int64)

        elif method == "voxel":
            # val: voxel size (meters), simple quantization; keep first per voxel
            vs = float(val)
            if vs <= 0:
                return points, rgb_data, {"reduced": False}
            q = np.floor(points[:, :3] / vs).astype(np.int64)
            view = q.view([('', q.dtype)] * q.shape[1])  # structured view for unique rows
            _, first_idx = np.unique(view, return_index=True)
            idx = np.sort(first_idx)

        else:
            return points, rgb_data, {"reduced": False}

        pts_red = points[idx]
        rgb_red = (rgb_data[idx] if rgb_data is not None else None)
        info = {
            "reduced": True,
            "method": method,
            "value": val,
            "kept": len(pts_red),
            "original": n
        }
        return pts_red, rgb_red, info

    def _create_progress_dialog(self, title: str, label: str, maximum: int):
        """Create a simple modal progress dialog with Cancel."""
        
        
        dlg = QProgressDialog(label, "Cancel", 0, max(1, int(maximum)), self.ui)
        dlg.setWindowTitle(title)
        dlg.setWindowModality(Qt.ApplicationModal)
        dlg.setMinimumDuration(0)     # show immediately
        dlg.setAutoClose(False)       # we will close manually
        dlg.setAutoReset(False)
        dlg.setValue(0)
        return dlg

    def _tick_progress(self, dlg, value: int):
        """Advance progress and keep UI responsive."""
        
        if dlg is None:
            return False
        dlg.setValue(int(value))
        QApplication.processEvents()
        return dlg.wasCanceled()

    def _get_point_cloud_info(self, file_path):
        """Get basic information about the point cloud file including color information."""
        try:
            
            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
            
            info_lines = [
                f"File: {Path(file_path).name}",
                f"Size: {file_size_mb:.1f} MB",
                f"Format: {Path(file_path).suffix.upper()}",
            ]
            
            # Try to get quick file info without full loading
            if file_size_mb < 50:  # Only analyze smaller files quickly
                try:
                    
                    pc = pv.read(file_path)
                    info_lines.extend([
                        f"Points: {pc.n_points:,}",
                        f"X range: {pc.bounds[0]:.0f} to {pc.bounds[1]:.0f}",
                        f"Y range: {pc.bounds[2]:.0f} to {pc.bounds[3]:.0f}",
                        f"Z range: {pc.bounds[4]:.0f} to {pc.bounds[5]:.0f}",
                    ])
                    
                    # Color information
                    color_info = self._analyze_point_cloud_colors(pc)
                    if color_info["has_colors"]:
                        info_lines.append(f"✓ Colors: {color_info['color_format']}")
                        if color_info.get("color_range"):
                            info_lines.append(f"   Range: {color_info['color_range']}")
                    else:
                        info_lines.append("⚠️ No color information")
                    
                    # Coordinate system hints
                    if pc.bounds[0] > 100000:
                        info_lines.append("⚠️ Large coordinates suggest projected system")
                    elif abs(pc.bounds[0]) < 180:
                        info_lines.append("⚠️ Small coordinates suggest geographic system")
                        
                except Exception as e:
                    info_lines.append("(Analysis will be performed during loading)")
            else:
                info_lines.append("Large file - analysis will be performed during loading")
            
            return '\n'.join(info_lines)
        
        except Exception as e:
            return f"Could not analyze file: {e}"

    def _analyze_point_cloud_colors(self, point_cloud):
        """Analyze what color information is available in the point cloud."""
        color_info = {"has_colors": False, "color_format": "none", "color_range": None}
        
        try:
            # ------------------------------------------------------------
            # NEW: Handle PLY files that store colour as separate red/green/blue
            #      uchar arrays (very common for LiDAR / photogrammetry exports)
            # ------------------------------------------------------------
            if {"red", "green", "blue"}.issubset(point_cloud.point_data.keys()):
                # Stack the three channels into a single RGB Nx3 uint8 array so that
                # downstream logic can treat colours uniformly.
                r = point_cloud.point_data['red'].astype(np.uint8)
                g = point_cloud.point_data['green'].astype(np.uint8)
                b = point_cloud.point_data['blue'].astype(np.uint8)
                rgb = np.column_stack([r, g, b])
                # Store a canonical attribute
                point_cloud.point_data['RGB'] = rgb
                # Populate colour-info dict
                color_info["has_colors"] = True
                color_info["color_format"] = "rgb_array"
                color_info["color_attribute"] = "RGB"
                color_info["color_range"] = (f"R:{r.min()}-{r.max()} G:{g.min()}-"
                                              f"{g.max()} B:{b.min()}-{b.max()}")
                return color_info  # ✅ We are done – colours handled.
            # ------------------------------------------------------------
            # Fallback to the old heuristics
            # ------------------------------------------------------------
            # Check for common color attribute names
            color_attributes = []
            
            for key in point_cloud.point_data.keys():
                key_lower = key.lower()
                if any(color_name in key_lower for color_name in ['rgb', 'color', 'red', 'green', 'blue']):
                    color_attributes.append(key)
            
            if color_attributes:
                primary_color_attr = color_attributes[0]
                color_data = point_cloud.point_data[primary_color_attr]
                
                color_info["has_colors"] = True
                color_info["color_attribute"] = primary_color_attr
                
                # Determine color format
                if color_data.ndim == 2 and color_data.shape[1] == 3:
                    # RGB array
                    color_info["color_format"] = "rgb_array"
                    color_info["color_range"] = f"R:{color_data[:,0].min()}-{color_data[:,0].max()}, G:{color_data[:,1].min()}-{color_data[:,1].max()}, B:{color_data[:,2].min()}-{color_data[:,2].max()}"
                elif color_data.ndim == 1:
                    # Single channel (intensity)
                    color_info["color_format"] = "intensity"
                    color_info["color_range"] = f"{color_data.min():.1f} to {color_data.max():.1f}"
            
            # Check for intensity data
            if 'Intensity' in point_cloud.point_data:
                intensity_data = point_cloud.point_data['Intensity']
                if not color_info["has_colors"]:
                    color_info["has_colors"] = True
                    color_info["color_format"] = "intensity"
                    color_info["color_attribute"] = "Intensity"
                    color_info["color_range"] = f"{intensity_data.min():.1f} to {intensity_data.max():.1f}"
        
        except Exception as e:
            debug_print(f"[COLOR_ANALYSIS] Error analyzing colors: {e}")
        
        return color_info

    def _load_and_transform_point_cloud(self, file_path, crs_info):
        """Load point cloud file and transform to local metric coordinate system with color preservation (with progress + cancel)."""
        try:


            file_name = Path(file_path).stem
            coord_info = crs_info["coordinate_system"]
            reduction = crs_info.get("reduction", {"enabled": False})

            # Store dialog choices
            if hasattr(self, 'data_loader') and self.data_loader:
                self.data_loader.last_coord_system = coord_info['name']
                if hasattr(self, '_remember_last_reduction'):
                    self._remember_last_reduction(reduction)
                debug_print(f"[LOAD_TRANSFORM] Stored coordinate system: {coord_info['name']}")
                if reduction.get("enabled"):
                    debug_print(f"[LOAD_TRANSFORM] Stored reduction: method={reduction.get('method')} value={reduction.get('value')}")

            debug_print(f"[LOAD_TRANSFORM] Loading {file_name} with RGB color preservation...")
            debug_print(f"[LOAD_TRANSFORM] Source: {coord_info['name']}")
            debug_print(f"[LOAD_TRANSFORM] Target: Local metric coordinate system")

            # 1) Load
            point_cloud = self._load_point_cloud_file(file_path)
            if point_cloud is None:
                return False

            # Analyze colors
            color_info = self._analyze_point_cloud_colors(point_cloud)

            # 2) Transform with progress
            points = point_cloud.points
            n_pts = len(points)
            debug_print(f"[LOAD_TRANSFORM] Transforming {n_pts} points...")
            debug_print(f"[LOAD_TRANSFORM] Source coordinate ranges:")
            debug_print(f"  X: {points[:, 0].min():.1f} to {points[:, 0].max():.1f}")
            debug_print(f"  Y: {points[:, 1].min():.1f} to {points[:, 1].max():.1f}")
            debug_print(f"  Z: {points[:, 2].min():.1f} to {points[:, 2].max():.1f}")

            source_epsg = coord_info["epsg"]
            tx_to_wgs = Transformer.from_crs(source_epsg, 4326, always_xy=True)

            # Determine centre lat/lon
            if getattr(self, 'current_trajectory', None):
                center_lat = float(np.mean([pt[0] for pt in self.current_trajectory]))
                center_lon = float(np.mean([pt[1] for pt in self.current_trajectory]))
            else:
                m = min(10_000, n_pts)
                lon_tmp, lat_tmp, _ = tx_to_wgs.transform(points[:m, 0], points[:m, 1], points[:m, 2])
                center_lat = float(np.mean(lat_tmp))
                center_lon = float(np.mean(lon_tmp))

            R = 6_378_137.0  # Earth radius
            center_lat_rad = np.radians(center_lat)

            batch_size = 500_000
            transformed_chunks = []

            # Progress dialog (Transform)
            dlg = self._create_progress_dialog(
                "Transforming Points",
                f"Transforming {n_pts:,} points to local metric...",
                n_pts
            )

            progressed = 0
            canceled = False
            try:
                for start in range(0, n_pts, batch_size):
                    end = min(start + batch_size, n_pts)
                    batch = points[start:end]

                    lon_arr, lat_arr, alt_arr = tx_to_wgs.transform(batch[:, 0], batch[:, 1], batch[:, 2])
                    lon_diff_rad = np.radians(lon_arr - center_lon)
                    lon_diff_rad = (lon_diff_rad + np.pi) % (2*np.pi) - np.pi  # wrap
                    x_local = R * lon_diff_rad * np.cos(center_lat_rad)
                    y_local = R * (np.radians(lat_arr - center_lat))
                    transformed_chunks.append(np.column_stack([x_local, y_local, alt_arr]))

                    progressed = end
                    if self._tick_progress(dlg, progressed):
                        canceled = True
                        break
            finally:
                dlg.close()

            if canceled:
                debug_print("[LOAD_TRANSFORM] ❌ Transform canceled by user.")
                QMessageBox.information(self.ui, "Canceled", "Point cloud transform was canceled.")
                return False

            transformed_array = np.vstack(transformed_chunks)
            transformed_pc = pv.PolyData(transformed_array)

            # Copy attributes
            for key in point_cloud.point_data.keys():
                transformed_pc.point_data[key] = point_cloud.point_data[key]
                debug_print(f"[LOAD_TRANSFORM] Preserved attribute: {key}")

            debug_print(f"[LOAD_TRANSFORM] Local metric coordinate ranges:")
            debug_print(f"  X: {transformed_array[:, 0].min():.1f} to {transformed_array[:, 0].max():.1f} m")
            debug_print(f"  Y: {transformed_array[:, 1].min():.1f} to {transformed_array[:, 1].max():.1f} m")
            debug_print(f"  Z: {transformed_array[:, 2].min():.1f} to {transformed_array[:, 2].max():.1f} m")

            # 3) Save & display (with optional reduction + write progress)
            success = self._save_and_display_point_cloud_efficiently(
                transformed_pc, file_name, coord_info, color_info, reduction=reduction
            )
            return success

        except Exception as e:
            debug_print(f"[LOAD_TRANSFORM] ❌ Error: {e}")
            
            traceback.print_exc()
            
            QMessageBox.critical(self.ui, "Error", f"Failed to transform point cloud:\n{str(e)}")
            return False

    def _save_and_display_point_cloud_efficiently(self, transformed_pc, file_name, coord_info, color_info, reduction=None):
        """EFFICIENT combined save to visualization folder and display in 3D viewer (with optional reduction + progress/cancel)."""
        try:
  


            # Determine the visualization directory (not temp folder)
            viz_dir = Path(".")  # fallback
            if hasattr(self, 'data_loader') and self.data_loader and hasattr(self.data_loader, 'project_data'):
                project_data = self.data_loader.project_data
                if project_data:
                    bridge_name = project_data.get('bridge_name', 'DefaultBridge')
                    project_dir_base = project_data.get('project_dir_base', '.')
                    viz_dir = Path(project_dir_base) / bridge_name / "02_Visualization"
                    viz_dir.mkdir(parents=True, exist_ok=True)
                    debug_print(f"[SAVE_EFFICIENT] Using project visualization directory: {viz_dir}")

            # Create output path
            ply_path = viz_dir / f"point_cloud_{file_name}.ply"

            # Remove existing file if it exists
            if ply_path.exists():
                ply_path.unlink()
                debug_print(f"[SAVE_EFFICIENT] Replaced existing {ply_path.name}")

            # Base arrays
            points = transformed_pc.points

            # Prepare color data if available
            has_colors = color_info["has_colors"]
            rgb_data = None
            if has_colors and color_info.get("color_attribute"):
                color_attr = color_info["color_attribute"]
                color_data = transformed_pc.point_data[color_attr]
                if color_info["color_format"] == "rgb_array":
                    rgb_data = color_data.astype(np.uint8)
                elif color_info["color_format"] == "intensity":
                    normalized_intensity = ((color_data - color_data.min()) /
                                            (color_data.max() - color_data.min()) * 255).astype(np.uint8)
                    rgb_data = np.column_stack([normalized_intensity, normalized_intensity, normalized_intensity])

            # Optional reduction right before writing
            points_to_write, rgb_to_write, red_info = self._reduce_point_cloud_arrays(points, rgb_data, reduction)
            n_points = len(points_to_write)
            has_colors_for_output = rgb_to_write is not None

            debug_print(f"[SAVE_EFFICIENT] Saving {n_points:,} points with "
                f"{'RGB colors' if has_colors_for_output else 'no colors'}"
                + (f" (reduced from {len(points):,}, method={red_info.get('method')}, value={red_info.get('value')})"
                    if red_info.get('reduced') else ""))

            # --- Write with progress + cancel ---
            chunk_size = 100_000
            canceled = False
            written = 0

            dlg = self._create_progress_dialog(
                "Writing Point Cloud",
                f"Writing {n_points:,} points to PLY...",
                n_points
            )

            try:
                with open(ply_path, 'w', encoding='utf-8') as f:
                    # Header
                    f.write('ply\nformat ascii 1.0\n')
                    f.write(f'element vertex {n_points}\n')
                    f.write('property float x\nproperty float y\nproperty float z\n')
                    if has_colors_for_output:
                        f.write('property uchar red\nproperty uchar green\nproperty uchar blue\n')
                    f.write('end_header\n')

                    # Chunks
                    for start in range(0, n_points, chunk_size):
                        end = min(start + chunk_size, n_points)
                        chunk_points = points_to_write[start:end]
                        if has_colors_for_output:
                            chunk_colors = rgb_to_write[start:end]
                            lines = [f"{x:.6f} {y:.6f} {z:.6f} {r} {g} {b}\n"
                                    for (x, y, z), (r, g, b) in zip(chunk_points, chunk_colors)]
                        else:
                            lines = [f"{x:.6f} {y:.6f} {z:.6f}\n" for x, y, z in chunk_points]
                        f.writelines(lines)

                        written = end
                        if self._tick_progress(dlg, written):
                            canceled = True
                            break
            finally:
                dlg.close()

            if canceled:
                # Remove partial file
                try:
                    if ply_path.exists():
                        ply_path.unlink()
                except Exception:
                    pass
                debug_print("[SAVE_EFFICIENT] ❌ Write canceled by user; partial file removed.")
                QMessageBox.information(self.ui, "Canceled", "Point cloud write was canceled.")
                return False

            debug_print(f"[SAVE_EFFICIENT] ✅ Saved colored point cloud to: {ply_path}")

            # Add to 3D viewer - reflect whether file has colors
            display_name = f"Point Cloud: {file_name}"

            if has_colors_for_output:
                debug_print(f"[SAVE_EFFICIENT] Adding point cloud with {color_info['color_format']} colors")
                self.visualizer.add_mesh_with_button(
                    str(ply_path),
                    display_name,
                    color=None,
                    opacity=0.8
                )
                color_msg = f"✓ Using original {color_info['color_format']} colors"
            else:
                debug_print(f"[SAVE_EFFICIENT] No colors found (or written), using default cyan")
                self.visualizer.add_mesh_with_button(
                    str(ply_path),
                    display_name,
                    color=(0.2, 0.8, 0.9),  # Cyan as fallback
                    opacity=0.7
                )
                color_msg = "⚠️ No color information found, using default cyan"

            # Reset camera
            self.visualizer.plotter.reset_camera()

            # Success message
            base_total = len(points)
            msg_points_line = f"Points: {n_points:,}" + (f" (reduced from {base_total:,})" if red_info.get('reduced') else "")
            success_msg = (
                f"Point cloud transformed and loaded successfully!\n\n"
                f"File: {file_name}\n"
                f"{msg_points_line}\n"
                f"Source: {coord_info['name']}\n"
                f"Saved to: {viz_dir.name}/\n\n"
                f"{color_msg}\n"
                f"✓ Aligned with bridge model in local metric coordinates\n"
                f"✓ Same orientation as 3D bridge representation"
            )
            if has_colors_for_output and color_info.get("color_range"):
                success_msg += f"\n\nColor range: {color_info['color_range']}"

            QMessageBox.information(self.ui, "Point Cloud Loaded ✅", success_msg)
            debug_print(f"[SAVE_EFFICIENT] ✅ SUCCESS: Point cloud with colors saved to visualization folder and displayed")
            return True

        except Exception as e:
            debug_print(f"[SAVE_EFFICIENT] ❌ Failed to save and display point cloud: {e}")
            
            traceback.print_exc()
            
            QMessageBox.critical(self.ui, "Error", f"Failed to save and display point cloud:\n{str(e)}")
            return False

    def _load_point_cloud_file(self, file_path):
        """Load point cloud file using PyVista with RGB color preservation."""
        try:

            
            file_ext = Path(file_path).suffix.lower()
            debug_print(f"[LOAD_PC_FILE] Loading {file_ext} file with color preservation...")
            
            if file_ext == '.ply':
                point_cloud = pv.read(file_path)
                
            elif file_ext in ['.xyz', '.pts']:
                data = np.loadtxt(file_path)
                if data.shape[1] >= 3:
                    points = data[:, :3]
                    point_cloud = pv.PolyData(points)
                    
                    # Check for RGB columns (common formats: XYZ RGB or XYZ Intensity RGB)
                    if data.shape[1] >= 6:  # XYZ + RGB
                        rgb_data = data[:, 3:6].astype(np.uint8)
                        point_cloud.point_data['RGB'] = rgb_data
                        debug_print(f"[LOAD_PC_FILE] Found RGB data in columns 4-6")
                        
                    elif data.shape[1] >= 7:  # XYZ + Intensity + RGB
                        point_cloud.point_data['Intensity'] = data[:, 3]
                        rgb_data = data[:, 4:7].astype(np.uint8)
                        point_cloud.point_data['RGB'] = rgb_data
                        debug_print(f"[LOAD_PC_FILE] Found Intensity and RGB data")
                        
                    elif data.shape[1] == 4:  # XYZ + Intensity
                        point_cloud.point_data['Intensity'] = data[:, 3]
                        debug_print(f"[LOAD_PC_FILE] Found Intensity data (no RGB)")
                    
                    # Add any remaining columns as attributes
                    for i in range(max(6, 4), data.shape[1]):
                        point_cloud.point_data[f'attribute_{i-2}'] = data[:, i]
                else:
                    raise ValueError("File must have at least 3 columns (X, Y, Z)")
                
            else:
                # Try generic PyVista reader
                point_cloud = pv.read(file_path)
            
            if point_cloud.n_points == 0:
                QMessageBox.warning(self.ui, "Warning", "The selected file contains no points.")
                return None
            
            # Check what color data we have
            color_info = self._analyze_point_cloud_colors(point_cloud)
            debug_print(f"[LOAD_PC_FILE] Color analysis: {color_info}")
            
            return point_cloud
            
        except Exception as e:
            debug_print(f"[LOAD_PC_FILE] Failed to load point cloud file: {e}")
            QMessageBox.critical(self.ui, "Error", f"Failed to load point cloud file:\n{str(e)}")
            return None

    def _transform_point_cloud_to_local_metric(self, point_cloud, point_cloud_crs):
        """Transform point cloud from its CRS to the local metric coordinate system."""
        try:
            
            debug_print(f"[TRANSFORM_PC] Starting coordinate transformation...")
            debug_print(f"[TRANSFORM_PC] Source CRS: {point_cloud_crs['name']}")
            debug_print(f"[TRANSFORM_PC] Target: Local metric system")
            
            # Get the transformation function to local metric (from bridge model)
            local_metric_transform = self._last_transform_func  # WGS84 -> Local metric
            
            # Create source coordinate system
            source_epsg = point_cloud_crs["epsg"]
            source_cs = CoordinateSystem.from_epsg(source_epsg)
            
            # Get point coordinates
            points = point_cloud.points  # Nx3 numpy array
            n_points = len(points)
            
            debug_print(f"[TRANSFORM_PC] Transforming {n_points} points...")
            debug_print(f"[TRANSFORM_PC] Source coordinate ranges:")
            debug_print(f"  X: {points[:, 0].min():.1f} to {points[:, 0].max():.1f}")
            debug_print(f"  Y: {points[:, 1].min():.1f} to {points[:, 1].max():.1f}")
            debug_print(f"  Z: {points[:, 2].min():.1f} to {points[:, 2].max():.1f}")
            
            # For large point clouds, transform in batches
            batch_size = 10000
            transformed_points = []
            
            for i in range(0, n_points, batch_size):
                end_idx = min(i + batch_size, n_points)
                batch_points = points[i:end_idx]
                
                debug_print(f"[TRANSFORM_PC] Processing batch {i//batch_size + 1}/{(n_points + batch_size - 1)//batch_size}")
                
                batch_transformed = []
                for point in batch_points:
                    x, y, z = point
                    
                    try:
                        # Step 1: Source CRS -> WGS84
                        if source_epsg == 4326:  # Already WGS84
                            lon, lat, alt = x, y, z  # x=lon, y=lat from WGS84 input
                        else:
                            lon, lat, alt = source_cs.to_wgs84(x, y, z)

                        # Step 2: WGS84 -> Local metric
                        local_x, local_y, local_z = local_metric_transform(lat, lon, alt)
                        
                        batch_transformed.append([local_x, local_y, local_z])
                        
                    except Exception as e:
                        debug_print(f"[TRANSFORM_PC] Failed to transform point ({x}, {y}, {z}): {e}")
                        # Use original coordinates as fallback
                        batch_transformed.append([x, y, z])
                
                transformed_points.extend(batch_transformed)
            
            # Create new point cloud with transformed coordinates
            transformed_array = np.array(transformed_points)
            transformed_pc = pv.PolyData(transformed_array)
            
            # Copy over any point data from original
            for key in point_cloud.point_data.keys():
                transformed_pc.point_data[key] = point_cloud.point_data[key]
            
            debug_print(f"[TRANSFORM_PC] Transformation complete!")
            debug_print(f"[TRANSFORM_PC] Local metric coordinate ranges:")
            debug_print(f"  X: {transformed_array[:, 0].min():.1f} to {transformed_array[:, 0].max():.1f} m")
            debug_print(f"  Y: {transformed_array[:, 1].min():.1f} to {transformed_array[:, 1].max():.1f} m")
            debug_print(f"  Z: {transformed_array[:, 2].min():.1f} to {transformed_array[:, 2].max():.1f} m")
            
            return transformed_pc
            
        except Exception as e:
            debug_print(f"[TRANSFORM_PC] Failed to transform point cloud: {e}")
            
            traceback.print_exc()
            QMessageBox.critical(self.ui, "Error", f"Failed to transform point cloud coordinates:\n{str(e)}")
            return None

    def _save_and_display_transformed_point_cloud(self, transformed_pc, file_name, source_crs):
        """Save the transformed point cloud and add it to the 3D viewer."""
        try:

            
            # Save to temp directory
            temp_dir = Path(tempfile.gettempdir())
            temp_ply_path = temp_dir / f"transformed_pc_{file_name}.ply"
            
            # Remove existing file if it exists
            if temp_ply_path.exists():
                temp_ply_path.unlink()
            
            # Save transformed point cloud
            transformed_pc.save(str(temp_ply_path))
            debug_print(f"[SAVE_PC] Saved transformed point cloud to: {temp_ply_path}")
            
            # Add to 3D viewer with distinctive color
            display_name = f"Point Cloud: {file_name}"
            self.visualizer.add_mesh_with_button(
                str(temp_ply_path), 
                display_name, 
                color=(0.2, 0.8, 0.9),  # Cyan color
                opacity=0.7
            )
            
            # Reset camera to show everything
            self.visualizer.plotter.reset_camera()
            
            # Success message
            QMessageBox.information(
                        self.ui,
                "Point Cloud Loaded ✅", 
                f"Point cloud transformed and loaded successfully!\n\n"
                f"File: {file_name}\n"
                f"Points: {transformed_pc.n_points:,}\n"
                f"Source: {source_crs['name']}\n"
                
                f"✓ Aligned with bridge model in local metric coordinates\n"
                f"✓ Same orientation as 3D bridge representation"
            )
            
            debug_print(f"[LOAD_TRANSFORM] ✅ SUCCESS: Point cloud aligned with bridge model")
            return True
        
        except Exception as e:
            debug_print(f"[LOAD_TRANSFORM] ❌ Error: {e}")
            
            traceback.print_exc()
            QMessageBox.critical(self.ui, "Error", f"Failed to transform point cloud:\n{str(e)}")
            return False

    def _offer_alignment_validation_tools(self, file_name):
        """Offer tools to validate alignment between point cloud and bridge model."""
        try:
            
            
            msg_box = QMessageBox(self.ui)
            msg_box.setWindowTitle("Alignment Validation")
            msg_box.setText(f"Point cloud '{file_name}' has been loaded and transformed.\n\nWould you like to use alignment validation tools?")
            msg_box.setInformativeText("These tools help verify that the point cloud aligns correctly with your bridge model.")
            
            # Custom buttons
            top_view_btn = msg_box.addButton("Switch to Top View", QMessageBox.ActionRole)
            measure_btn = msg_box.addButton("Measure Distances", QMessageBox.ActionRole) 
            later_btn = msg_box.addButton("Maybe Later", QMessageBox.RejectRole)
            
            msg_box.exec()
            
            clicked_button = msg_box.clickedButton()
            
            if clicked_button == top_view_btn:
                # Switch to top view for better alignment checking
                self.change_to_top_view()
                debug_print("[VALIDATION] Switched to top view for alignment checking")
                
            elif clicked_button == measure_btn:
                # Show measurement instructions
                measure_msg = (
                    "Measurement Tools for Alignment Validation:\n\n"
                    "1. Use the 3D viewer to visually inspect alignment\n"
                    "2. Check that bridge pillars align with point cloud structures\n"  
                    "3. Verify that the bridge deck height matches point cloud data\n"
                    "4. Look for any systematic offsets or rotations\n\n"
                    "If alignment looks incorrect:\n"
                    "• Double-check the coordinate system selection\n"
                    "• Verify the point cloud's original coordinate system\n"
                    "• Consider using a different coordinate system"
                )
                QMessageBox.information(self.ui, "Measurement Guide", measure_msg)
            
        except Exception as e:
            debug_print(f"[VALIDATION] Error in alignment validation tools: {e}")
    
    def change_to_top_view(self):
        """Change the 3D viewer to a top-down view for better bridge overview."""
        try:
            debug_print("[TAB2] Changing to top view...")
            
            # Check if we have the 3D visualizer
            if not hasattr(self, 'visualizer') or self.visualizer is None:
                debug_print("[TAB2] No 3D viewer available. Please build the bridge model first.")
                QMessageBox.information(self.ui, "Info", "No 3D viewer available. Please build the bridge model first using the 'Build Model' button.")
                return
            
            # Check if the visualizer has a plotter
            if not hasattr(self.visualizer, 'plotter') or self.visualizer.plotter is None:
                debug_print("[TAB2] 3D plotter not available")
                QMessageBox.information(self.ui, "Info", "3D plotter not available. Please build the bridge model first.")
                return
            
            # Set camera to top view
            # Top view means looking down from above (negative Z direction)
            self.visualizer.plotter.view_xy()  # Sets view to look down from Z+ to Z-
            
            # Alternative method if view_xy doesn't work well
            # self.visualizer.plotter.camera_position = 'xy'
            
            # Fit the view to show all objects
            self.visualizer.plotter.reset_camera()
            
            debug_print("[TAB2] ✓ Successfully changed to top view")
            debug_print("[TAB2] View is now looking down from above the bridge")
            
        except Exception as e:
            debug_print(f"[TAB2] ❌ Failed to change to top view: {e}")
            
            traceback.print_exc()
            QMessageBox.warning(self.ui, "Error", f"Failed to change to top view: {str(e)}")
    

    # =====================================================================
    # Project Configuration Helper
    # =====================================================================
    
    def _save_project_config(self):
        """Save the current project configuration."""
        try:
            if not self.data_loader:
                return False
            
            # Get project data
            # Skip EPSG check since it should already be properly set
            project_data = self.data_loader._parse_project_data(skip_epsg_check=True)
            if not project_data:
                return False

            # Note: Removed project_config.json creation - complete_program_state.json is preferred
            debug_print("[INFO] Project configuration confirmed (using complete_program_state.json)")

            return True
            
        except Exception as e:
            debug_print(f"[ERROR] Failed to save project config: {e}")
            return False
    
    def _parse_trajectory_heights_from_textbox(self):
        """Parse trajectory_heights from the project text box."""
        try:
            self._update_parsed_data()
            heights = self.parsed_data["project"].get("trajectory_heights", [])
            if heights:
                debug_print(f"[PARSE_HEIGHTS] Found trajectory_heights: {heights}")
                self.trajectory_heights = heights
            return heights
        except Exception as e:
            debug_print(f"[PARSE_HEIGHTS] Error: {e}")
            return []
    
    def _interpolate_heights(self, heights, target_length):
        """Interpolate or truncate heights to match target length."""
        
        
        if not heights:
            return [0.0] * target_length
            
        if len(heights) == target_length:
            return heights
        elif len(heights) == 1:
            # Single height - use for all points
            return [heights[0]] * target_length
        elif len(heights) < target_length:
            # Interpolate to match target length
            x_original = np.linspace(0, 1, len(heights))
            x_target = np.linspace(0, 1, target_length)
            interpolated = np.interp(x_target, x_original, heights)
            debug_print(f"[INTERPOLATE] Interpolated {len(heights)} heights to {target_length} points")
            return interpolated.tolist()
        else:
            # More heights than needed - truncate
            debug_print(f"[INTERPOLATE] Truncated {len(heights)} heights to {target_length} points")
            return heights[:target_length]

    def _save_comprehensive_project_data(self, project_data):
        """Save comprehensive project data to input directory."""
        try:
            
            
            # Get the project directory structure that was already created by _setup_project_structure
            bridge_name = project_data.get('bridge_name', 'DefaultBridge')
            project_dir_base = Path(project_data.get('project_dir_base', '.'))
            project_dir = project_dir_base / bridge_name
            input_dir = project_dir / "01_Input"  # Use the same structure as _setup_project_structure
            
            # The input directory should already exist from _setup_project_structure, but ensure it exists
            if not input_dir.exists():
                debug_print(f"[WARNING] Input directory does not exist, creating: {input_dir}")
                input_dir.mkdir(parents=True, exist_ok=True)
            
            # Create comprehensive project data structure
            comprehensive_data = {
                "project_info": {
                    "project_name": bridge_name,
                    "created_date": datetime.now().isoformat(),
                    "project_dir_base": str(project_dir_base),
                    "project_dir": str(project_dir),
                    "input_directory": str(input_dir),
                    "coordinate_system": getattr(self.data_loader, 'last_coord_system', 'custom'),

                },
                "project_variables": project_data,
                "flight_route_settings": {},
                "extracted_geometry": {
                    "trajectory_points": [],
                    "pillar_points": [],
                    "abutment_points": []
                },
                "cross_section_data": {
                    "processed": False,
                    "parameters": {}
                }
            }
            
            # Add flight route settings if available
            if self.data_loader and hasattr(self.data_loader, 'flight_routes_text_edit'):
                comprehensive_data["flight_route_settings"] = self.data_loader._parse_flight_route_data()
            
            # Extract trajectory and pillar data from bridge data (if Excel file was loaded)
            try:
                sel_file = getattr(self.data_loader, 'last_selected_file', None)
                if sel_file and sel_file.suffix.lower() in {'.xlsx', '.xls'}:
                    debug_print(f"[SAVE] Extracting geometry from Excel file: {sel_file}")

                    
                    df_tmp = pd.read_excel(sel_file, sheet_name="00_Input")
                    abut_pairs, super_pairs, pillar_pairs = _separate_structural_components(df_tmp)
                    
                    # Extract trajectory points (mid-points of super pairs) - simple list format [[x,y,z], [x,y,z], ...]
                    trajectory_list = []
                    trajectory_detailed = []
                    for seq in sorted(super_pairs.keys()):
                        pair = super_pairs[seq]
                        if 'right' in pair and 'left' in pair:
                            midpoint = ((pair['right'] + pair['left'])/2).tolist()
                            # Store detailed info for reference
                            trajectory_detailed.append({
                                "sequence": int(seq),
                                "coordinates": midpoint,
                                "right_point": pair['right'].tolist(),
                                "left_point": pair['left'].tolist(),
                                "type": "trajectory_midpoint"
                            })
                        else:
                            midpoint = next(iter(pair.values())).tolist()
                            trajectory_detailed.append({
                                "sequence": int(seq),
                                "coordinates": midpoint,
                                "type": "trajectory_midpoint"
                            })
                        trajectory_list.append(midpoint)
                    
                    # Extract pillar points - nested list format [[[x,y,z], [x,y,z]], [[x,y,z], [x,y,z]]]
                    pillars_list = []
                    pillars_detailed = []
                    for seq, pair in pillar_pairs.items():
                        if 'right' in pair and 'left' in pair:
                            right_coord = pair['right'].tolist()
                            left_coord = pair['left'].tolist()
                            centre = ((pair['right'] + pair['left'])/2).tolist()
                            
                            # Add to simple nested list format
                            pillars_list.append([right_coord, left_coord])
                            
                            # Store detailed info for reference
                            pillars_detailed.append({
                                "sequence": int(seq),
                                "center": centre,
                                "right": right_coord,
                                "left": left_coord,
                                "type": "pillar"
                            })
                        else:
                            single_coord = next(iter(pair.values())).tolist()
                            # Single pillar - duplicate for consistency
                            pillars_list.append([single_coord, single_coord])
                            pillars_detailed.append({
                                "sequence": int(seq),
                                "center": single_coord,
                                "right": single_coord,
                                "left": single_coord,
                                "type": "pillar"
                            })
                    
                    # Extract abutment points - keep detailed format
                    abutment_list = []
                    abutment_detailed = []
                    for seq, pair in abut_pairs.items():
                        abutment_pair = []
                        abutment_data = {
                            "sequence": int(seq),
                            "type": "abutment"
                        }
                        if 'right' in pair:
                            right_coord = pair['right'].tolist()
                            abutment_pair.append(right_coord)
                            abutment_data["right"] = right_coord
                        if 'left' in pair:
                            left_coord = pair['left'].tolist()
                            abutment_pair.append(left_coord)
                            abutment_data["left"] = left_coord
                        
                        if abutment_pair:
                            abutment_list.append(abutment_pair)
                        abutment_detailed.append(abutment_data)
                    
                    # Store extracted data as globally accessible class attributes
                    self.trajectory_list = trajectory_list
                    self.pillars_list = pillars_list
                    self.abutment_list = abutment_list
                    
                    debug_print(f"[GLOBAL] Stored trajectory_list ({len(self.trajectory_list)} points), pillars_list ({len(self.pillars_list)} pairs), abutment_list ({len(self.abutment_list)} pairs) as globally accessible class attributes")
                    
                    # Update comprehensive data with ALL data in requested format
                    comprehensive_data["extracted_geometry"] = {
                        # Simple list formats as requested
                        "trajectory_list": trajectory_list,  # [[x,y,z], [x,y,z], ...]
                        "pillars_list": pillars_list,        # [[[x,y,z], [x,y,z]], [[x,y,z], [x,y,z]]]
                        "abutment_list": abutment_list,      # [[[x,y,z], [x,y,z]], ...]
                        
                        # Detailed formats for reference and analysis
                        "trajectory_detailed": trajectory_detailed,
                        "pillars_detailed": pillars_detailed,
                        "abutment_detailed": abutment_detailed,
                        
                        # Metadata
                        "extraction_source": str(sel_file),
                        "extraction_date": datetime.now().isoformat(),
                        "counts": {
                            "trajectory_points": len(trajectory_list),
                            "pillar_pairs": len(pillars_list),
                            "abutment_pairs": len(abutment_list)
                        }
                    }
                    
                    debug_print(f"[SAVE] Extracted {len(trajectory_list)} trajectory points, {len(pillars_list)} pillar pairs, {len(abutment_list)} abutment pairs")
                    
            except Exception as e:
                debug_print(f"[WARNING] Could not extract geometry from Excel: {e}")
            
            # Add cross-section data if processed - include ALL cross-section data
            if hasattr(self, 'processed_crosssection_image') and self.processed_crosssection_image is not None:
                cross_section_data = {
                    "processed": True,
                    "parameters": {
                        "input_scale_meters": project_data.get('input_scale_meters'),
                        "epsilon_input": project_data.get('epsilonInput', 0.003)
                    },
                    "processing_date": datetime.now().isoformat()
                }
                
                # Include transformed points if available
                if hasattr(self, 'crosssection_transformed_points') and self.crosssection_transformed_points is not None:
                    cross_section_data["has_transformed_points"] = True
                    cross_section_data["transformed_points_count"] = len(self.crosssection_transformed_points)
                    # Include the actual transformed points data
                    try:
                        if hasattr(self.crosssection_transformed_points, 'tolist'):
                            cross_section_data["transformed_points"] = self.crosssection_transformed_points.tolist()
                        else:
                            cross_section_data["transformed_points"] = list(self.crosssection_transformed_points)
                    except Exception as e:
                        debug_print(f"[WARNING] Could not serialize transformed points: {e}")
                        cross_section_data["transformed_points"] = None
                else:
                    cross_section_data["has_transformed_points"] = False
                    cross_section_data["transformed_points"] = None
                
                comprehensive_data["cross_section_data"] = cross_section_data
            


            
        except Exception as e:
            debug_print(f"[ERROR] Could not save comprehensive project data: {e}")
            QMessageBox.warning(self.ui, "Warning", f"Could not save comprehensive project data: {str(e)}")

    # =====================================================================
    # 3-D BRIDGE REPRESENTATION GENERATION
    # =====================================================================


    def _save_bridge_modelling_data(self):
        """Save bridge modeling data as a simple JSON file."""
        try:
            # Determine the save directory (project input directory if available)
            save_dir = Path(".")  # fallback to current directory
            
            if hasattr(self, 'data_loader') and self.data_loader and hasattr(self.data_loader, 'project_data'):
                project_data = self.data_loader.project_data
                if project_data:
                    bridge_name = project_data.get('bridge_name', 'DefaultBridge')
                    project_dir_base = project_data.get('project_dir_base', '.')
                    input_dir = Path(project_dir_base) / bridge_name / "01_Input"
                    if input_dir.exists():
                        save_dir = input_dir
                        debug_print(f"[BRIDGE_MODEL] Using project input directory: {save_dir}")
                    else:
                        debug_print(f"[BRIDGE_MODEL] Project input directory not found, using current directory")
            
            # Convert data to simple lists (handle numpy arrays)
            def convert_to_list(data):
                """Convert numpy arrays or other data structures to simple lists."""
                if data is None:
                    return []
                if hasattr(data, 'tolist'):  # numpy array
                    return data.tolist()
                if isinstance(data, (list, tuple)):
                    return [convert_to_list(item) if hasattr(item, 'tolist') else item for item in data]
                return data
            
            # Create bridge modeling data dictionary
            bridge_data = {
                "created_date": datetime.now().isoformat(),
                "current_trajectory": convert_to_list(getattr(self, 'current_trajectory', [])),
                "current_pillars": convert_to_list(getattr(self, 'current_pillars', [])),
                "current_safety_zones": convert_to_list(getattr(self, 'current_safety_zones', [])),
                "current_zone_points": convert_to_list(getattr(self, 'current_zone_points', [])),
                "crosssection_transformed_points": convert_to_list(getattr(self, 'crosssection_transformed_points', [])),
                "counts": {
                    "trajectory_points": len(getattr(self, 'current_trajectory', [])),
                    "pillars": len(getattr(self, 'current_pillars', [])),
                    "safety_zones": len(getattr(self, 'current_safety_zones', [])),
                    "zone_points": len(getattr(self, 'current_zone_points', [])),
                    "crosssection_points": len(getattr(self, 'crosssection_transformed_points', []))
                }
            }
            
            # Save to file
            output_file = save_dir / "bridge_modelling_data.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(bridge_data, f, indent=2, ensure_ascii=False)
            
            debug_print(f"[SUCCESS] Bridge modeling data saved to: {output_file}")
            
        except Exception as e:
            debug_print(f"[ERROR] Failed to save bridge modeling data: {e}")
            
            traceback.print_exc()

    def toggle_dock_widget_fr(self):
        """Toggle the dock widget for flight routes with proper layout adjustment."""
        try:
            debug_print("[DEBUG] toggle_dock_widget_fr called")
            
            # Find the dock widget
            dock_widget = self.ui.findChild(QWidget, "dockWidget_FR")
            if not dock_widget:
                debug_print("[WARNING] dockWidget_FR not found")
                return
            
            # Check if it's actually a QDockWidget or if we need to find the parent
            
            if not isinstance(dock_widget, QDockWidget):
                debug_print(f"[DEBUG] dockWidget_FR is a {type(dock_widget)}, looking for parent QDockWidget")
                # Try to find the parent QDockWidget
                parent = dock_widget.parent()
                while parent and not isinstance(parent, QDockWidget):
                    parent = parent.parent()
                if isinstance(parent, QDockWidget):
                    dock_widget = parent
                    debug_print(f"[DEBUG] Found parent QDockWidget: {dock_widget.objectName()}")
                else:
                    debug_print("[ERROR] Could not find QDockWidget in parent hierarchy")
                    return
            
            # Toggle visibility using QDockWidget-specific methods
            current_visible = dock_widget.isVisible()
            
            if current_visible:
                # Hide the dock widget
                dock_widget.hide()
                debug_print("[INFO] Flight Routes dock widget hidden")
            else:
                # Show the dock widget
                dock_widget.show()
                debug_print("[INFO] Flight Routes dock widget shown")
            
            # Force the main window to update its layout
            # This is crucial for QDockWidget to properly resize other elements
            self.ui.update()
            self.ui.updateGeometry()
            
            # Also process any pending events to ensure layout updates take effect
            
            QApplication.processEvents()
                
        except Exception as e:
            debug_print(f"[ERROR] Failed to toggle dock widget: {e}")
            
            traceback.print_exc()

    def build_improved_3d_bridge_model(self):
        """Build an improved 3D bridge model with correct coordinate system transformation."""


        # Clear any existing 3D models first
        if hasattr(self, "_improved_3d_model_built") and self._improved_3d_model_built:
            debug_print("[IMPROVED_BRIDGE] Rebuilding 3D model with improved coordinate system...")
            # Clear the visualizer
            if hasattr(self, 'visualizer') and self.visualizer is not None:
                self.visualizer.meshes.clear()
                self.visualizer.buttons.clear()
                # Clear the side panel
                layout = self.visualizer.side_panel_frame.layout()
                while layout.count():
                    child = layout.takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
                # Reset the plotter
                self.visualizer.plotter.clear()
                debug_print("[IMPROVED_BRIDGE] Cleared existing 3D models")
        else:
            debug_print("[IMPROVED_BRIDGE] Starting improved 3D bridge modeling...")

        try:
            # Imports


            # ------------------------------------------------------------------
            # 1. Create LOCAL METRIC coordinate system centered on bridge location
            # ------------------------------------------------------------------
            def create_local_metric_system(trajectory_points):
                """Create a production-ready local metric coordinate system centered on the bridge."""
                if not trajectory_points:
                    return None, None, None, "NoTrajectory"

                center_lat = sum(pt[0] for pt in trajectory_points) / len(trajectory_points)
                center_lon = sum(pt[1] for pt in trajectory_points) / len(trajectory_points)

                if abs(center_lat) > 80:
                    debug_print(f"\n[LOCAL_METRIC] ⚠️  WARNING: Near pole location {center_lat:.1f}°")
                    debug_print(f"[LOCAL_METRIC] ⚠️  Consider using UTM or polar projection instead")
                    debug_print(f"[LOCAL_METRIC] ⚠️  Accuracy may be reduced but still usable")

                lats = [pt[0] for pt in trajectory_points]
                lons = [pt[1] for pt in trajectory_points]
                lat_span = max(lats) - min(lats)
                lon_span = max(lons) - min(lons)

                R = 6378137.0
                approx_max_distance = R * np.sqrt((np.radians(lat_span))**2 +
                                                (np.radians(lon_span) * np.cos(np.radians(center_lat)))**2)

                debug_print(f"\n[LOCAL_METRIC] Creating production-ready local metric system")
                debug_print(f"[LOCAL_METRIC] Bridge center: {center_lat:.6f}°N, {center_lon:.6f}°E")
                debug_print(f"[LOCAL_METRIC] Estimated span: {approx_max_distance:.0f}m")

                if approx_max_distance < 1000:
                    accuracy, suitability = "<1mm", "EXCELLENT"
                elif approx_max_distance < 5000:
                    accuracy, suitability = "<1cm", "VERY GOOD"
                elif approx_max_distance < 10000:
                    accuracy, suitability = "<10cm", "GOOD"
                else:
                    accuracy, suitability = "degraded", "CONSIDER UTM"

                debug_print(f"[LOCAL_METRIC] Expected accuracy: {accuracy} - {suitability}")

                def wgs84_to_local_metric(lat, lon, alt=0):
                    try:
                        if not (-90 <= lat <= 90):
                            raise ValueError(f"Invalid latitude: {lat}")
                        if not (-180 <= lon <= 180):
                            raise ValueError(f"Invalid longitude: {lon}")

                        R = 6378137.0
                        lat_rad = np.radians(lat)
                        lon_rad = np.radians(lon)
                        center_lat_rad = np.radians(center_lat)
                        center_lon_rad = np.radians(center_lon)

                        lon_diff = lon_rad - center_lon_rad
                        if lon_diff > np.pi:
                            lon_diff -= 2 * np.pi
                        elif lon_diff < -np.pi:
                            lon_diff += 2 * np.pi

                        x = R * lon_diff * np.cos(center_lat_rad)
                        y = R * (lat_rad - center_lat_rad)
                        return x, y, alt
                    except Exception as e:
                        debug_print(f"[LOCAL_METRIC] Transform error: {e}")
                        return 0.0, 0.0, alt

                def local_metric_to_wgs84(x, y, z=0):
                    try:
                        R = 6378137.0
                        center_lat_rad = np.radians(center_lat)
                        center_lon_rad = np.radians(center_lon)
                        lat_rad = center_lat_rad + (y / R)
                        lon_rad = center_lon_rad + (x / (R * np.cos(center_lat_rad)))
                        while lon_rad > np.pi:
                            lon_rad -= 2 * np.pi
                        while lon_rad < -np.pi:
                            lon_rad += 2 * np.pi
                        lat = np.degrees(lat_rad)
                        lon = np.degrees(lon_rad)
                        lat = np.clip(lat, -90, 90)
                        return lon, lat, z
                    except Exception as e:
                        debug_print(f"[LOCAL_METRIC] Inverse transform error: {e}")
                        return center_lon, center_lat, z

                def export_to_coordinate_system(points, target_epsg):
                    try:
                        
                        wgs84_points = []
                        for x, y, z in points:
                            lon, lat, alt = local_metric_to_wgs84(x, y, z)
                            wgs84_points.append([lat, lon, alt])

                        target_context = ProjectContext.from_epsg(target_epsg, VerticalRef.ELLIPSOID)
                        target_points = []
                        for lat, lon, alt in wgs84_points:
                            tx, ty, tz = target_context.wgs84_to_project(lon, lat, alt)
                            target_points.append([tx, ty, tz])
                        return target_points
                    except Exception as e:
                        debug_print(f"[EXPORT] Failed to export to EPSG:{target_epsg}: {e}")
                        return points

                system_info = {
                    "center_lat": center_lat,
                    "center_lon": center_lon,
                    "span_m": approx_max_distance,
                    "accuracy": accuracy,
                    "suitability": suitability
                }
                return wgs84_to_local_metric, local_metric_to_wgs84, export_to_coordinate_system, f"LocalMetric_{center_lat:.3f}N_{center_lon:.3f}E"

            # Create local metric system
            if self.current_trajectory:
                to_local_metric, from_local_metric, export_function, local_system_name = create_local_metric_system(self.current_trajectory)

                if to_local_metric:
                    debug_print(f"[LOCAL_METRIC] System name: {local_system_name}")
                    debug_print(f"[LOCAL_METRIC] ✓ Metric units (meters)")
                    debug_print(f"[LOCAL_METRIC] ✓ Minimal distortion (bridge-scale)")


                    transform_func = to_local_metric
                    project_coordinate_system = local_system_name

                    # Store for later use by update_safety_zones_3d
                    self._last_transform_func = transform_func
                    self._last_coordinate_system = project_coordinate_system
                    self._last_inverse_transform = from_local_metric

                else:
                    debug_print("[ERROR] Failed to create local metric system")
                    transform_func = lambda lat, lon, alt=0: (float(lat), float(lon), float(alt))
                    project_coordinate_system = "WGS84_Fallback"
                    self._last_transform_func = transform_func
                    self._last_coordinate_system = project_coordinate_system
                    self._last_inverse_transform = lambda x, y, z=0.0: (float(x), float(y), float(z))  # identity for WGS84
            else:
                debug_print("[ERROR] No trajectory points available")
                transform_func = lambda lat, lon, alt=0: (float(lat), float(lon), float(alt))
                project_coordinate_system = "WGS84_Fallback"
                # Store for later use by update_safety_zones_3d
                self._last_transform_func = transform_func
                self._last_coordinate_system = project_coordinate_system
                self._last_inverse_transform = lambda x, y, z=0.0: (float(x), float(y), float(z))  # identity for WGS84

            # ------------------------------------------------------------------
            # 2. Transform trajectory and pillars to LOCAL METRIC coordinate system
            # ------------------------------------------------------------------
            debug_print(f"\n[TRAJECTORY] Converting {len(self.current_trajectory)} trajectory points to local metric coordinates:")
            # --- sanitize inputs from map/UI to floats (NEW) ---
            def _to_float(v):
                try:
                    return float(v)
                except Exception:
                    return np.nan

            # Trajectory: list of (lat, lon)
            self.current_trajectory = [
                (_to_float(lat), _to_float(lon))
                for (lat, lon) in (self.current_trajectory or [])
            ]
            self.current_trajectory = [
                (lat, lon) for (lat, lon) in self.current_trajectory
                if np.isfinite(lat) and np.isfinite(lon)
            ]

            # Pillars: list of dicts with "lat","lon"
            self.current_pillars = [
                {**p, "lat": _to_float(p.get("lat")), "lon": _to_float(p.get("lon"))}
                for p in (self.current_pillars or [])
                if np.isfinite(_to_float(p.get("lat"))) and np.isfinite(_to_float(p.get("lon")))
            ]

            # ------------------------------------------------------------------
            # XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
            # DEBUG: INPUT DATA FROM MAP VISUALIZATION
            # ------------------------------------------------------------------
            debug_print("XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")
            debug_print("DEBUG INPUT DATA FROM MAP VISUALIZATION:")
            debug_print("XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")

            debug_print(f"[INPUT_DATA] Trajectory points from map: {len(self.current_trajectory)} points")
            if self.current_trajectory:
                for i, (lat, lon) in enumerate(self.current_trajectory[:5]):  # Show first 5
                    debug_print(f"  Point {i+1}: WGS84({lat:.6f}, {lon:.6f})")
                if len(self.current_trajectory) > 5:
                    debug_print(f"  ... and {len(self.current_trajectory) - 5} more points")

            debug_print(f"[INPUT_DATA] Safety zones from map: {len(self.current_safety_zones)} zones")
            if self.current_safety_zones:
                for zone in self.current_safety_zones[:3]:  # Show first 3 zones
                    debug_print(f"  Zone {zone['id']}: {len(zone['points'])} points")
                    if zone['points']:
                        lat, lon = zone['points'][0]  # Show first point of each zone
                        debug_print(f"    First point: WGS84({lat:.6f}, {lon:.6f})")
                if len(self.current_safety_zones) > 3:
                    debug_print(f"  ... and {len(self.current_safety_zones) - 3} more zones")

            debug_print(f"[INPUT_DATA] Pillar points from map: {len(self.current_pillars)} pillars")
            if self.current_pillars:
                for pillar in self.current_pillars[:5]:  # Show first 5 pillars
                    debug_print(f"  Pillar {pillar['id']}: WGS84({pillar['lat']:.6f}, {pillar['lon']:.6f})")
                if len(self.current_pillars) > 5:
                    debug_print(f"  ... and {len(self.current_pillars) - 5} more pillars")

            debug_print("XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")
            height_values = []

            def _has_meaningful_z_values(z_values):
                if not z_values:
                    return False
                try:
                    return any(abs(float(z)) > 0.1 for z in z_values)
                except Exception:
                    return False

            def _coerce_heights_to_list(h):
                """Return a list[float] from list/tuple/ndarray/str (supports comments)."""
                import ast, re
                if h is None:
                    return []
                # Already a sequence
                if isinstance(h, (list, tuple)):
                    out = []
                    for v in h:
                        try:
                            out.append(float(v))
                        except Exception:
                            continue
                    return out
                try:
                    import numpy as _np  # in case np array is passed
                    if isinstance(h, _np.ndarray):
                        return [float(v) for v in h.tolist()]
                except Exception:
                    pass
                # String: strip comments and parse
                if isinstance(h, str):
                    s = h.split('#', 1)[0].strip()
                    if not s:
                        return []
                    # Try JSON/py-list first
                    if s.startswith('[') and s.endswith(']'):
                        try:
                            arr = ast.literal_eval(s)
                            return [float(v) for v in arr]
                        except Exception:
                            pass
                    # Fallback: regex extract numbers
                    nums = re.findall(r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?', s)
                    return [float(n) for n in nums]
                # Unknown → empty
                return []

            # Prefer imported Z if meaningful
            if getattr(self, 'trajectory_original_z', None) and _has_meaningful_z_values(self.trajectory_original_z):
                height_values = [float(z) for z in self.trajectory_original_z]
                debug_print(f"[HEIGHT_SOURCE] Using {len(height_values)} meaningful original Z values from imported data")
                debug_print(f"[HEIGHT_SOURCE] Z range: {min(height_values):.1f}m to {max(height_values):.1f}m")
            else:
                debug_print("[HEIGHT_SOURCE] Using heights from textbox or default 0.0m")
                # Ensure we actually coerce the textbox string/list to floats
                self._parse_trajectory_heights_from_textbox()
                height_values = _coerce_heights_to_list(getattr(self, 'trajectory_heights', None))
                if not height_values:
                    height_values = [0.0]
                debug_print(f"[HEIGHT_SOURCE] Parsed {len(height_values)} height value(s): {height_values[:10]}{'...' if len(height_values)>10 else ''}")

            interpolated_heights = self._interpolate_heights(height_values, len(self.current_trajectory))
            debug_print(f"[HEIGHT_INTERPOLATION] Interpolated {len(height_values)} → {len(interpolated_heights)} points")



            trajectory_project_coords = []
            base_height = 0.0

            def _safe_float(v, default=0.0):
                try:
                    return float(v)
                except Exception:
                    return float(default)

            for i, (lat, lon) in enumerate(self.current_trajectory):
                lat_f = _safe_float(lat, np.nan)
                lon_f = _safe_float(lon, np.nan)
                if not (np.isfinite(lat_f) and np.isfinite(lon_f)):
                    debug_print(f"  [ERROR] Point {i+1}: invalid lat/lon -> skipping")
                    continue

                h_raw = interpolated_heights[i] if i < len(interpolated_heights) else base_height
                h = _safe_float(h_raw, base_height)

                try:
                    x, y, z = transform_func(lat_f, lon_f, h)
                except Exception as e:
                    debug_print(f"  [WARN] Transform failed at point {i+1} with h={h!r}: {e} -> retry with h={base_height}")
                    try:
                        x, y, z = transform_func(lat_f, lon_f, base_height)
                    except Exception as e2:
                        debug_print(f"  [ERROR] Transform retry failed at point {i+1}: {e2} -> skipping")
                        continue

                x, y, z = float(x), float(y), float(z)
                trajectory_project_coords.append([x, y, z])
                if i < 5:
                    debug_print(f"  T{i+1}: WGS84({lat_f:.6f}, {lon_f:.6f}, h={h:.1f}m) -> Local({x:.1f}m, {y:.1f}m, {z:.1f}m)")

            debug_print(f"[PILLARS] Converting {len(self.current_pillars)} pillar points to local metric coordinates:")
            pillars_project_coords = []
            for i, pillar in enumerate(self.current_pillars):
                try:
                    lat = float(pillar["lat"]); lon = float(pillar["lon"])
                    x, y, z = transform_func(lat, lon, 0.0)
                    pillar_data = {"id": pillar.get("id", f"P{i+1}"), "x": float(x), "y": float(y), "z": float(z), "original": pillar}
                    pillars_project_coords.append(pillar_data)
                    if i < 5:
                        debug_print(f"  P{i+1}: {pillar_data['id']} WGS84({lat:.6f}, {lon:.6f}) -> Local({x:.1f}m, {y:.1f}m, {z:.1f}m)")
                except Exception as e:
                    debug_print(f"  [ERROR] Pillar {pillar.get('id', i+1)}: {e}")
                    pillars_project_coords.append({
                        "id": pillar.get("id", f"P{i+1}"),
                        "x": 0.0, "y": 0.0, "z": 0.0,
                        "original": pillar
                    })

            # ------------------------------------------------------------------
            # XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX
            # DEBUG: OUTPUT DATA IN 3D SPACE (AFTER COORDINATE TRANSFORMATION)
            # ------------------------------------------------------------------
            debug_print("XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")
            debug_print("DEBUG OUTPUT DATA IN 3D SPACE:")
            debug_print("XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")

            debug_print(f"[OUTPUT_DATA] Trajectory in 3D {project_coordinate_system}: {len(trajectory_project_coords)} points")
            if trajectory_project_coords:
                for i, (x, y, z) in enumerate(trajectory_project_coords[:5]):  # Show first 5
                    debug_print(f"  Point {i+1}: Local({x:.1f}m, {y:.1f}m, {z:.1f}m)")
                if len(trajectory_project_coords) > 5:
                    debug_print(f"  ... and {len(trajectory_project_coords) - 5} more points")

                # Show coordinate ranges for trajectory
                coords_array = np.asarray(trajectory_project_coords, dtype=float)
                if coords_array.shape[0] > 0:
                    x_range = f"{coords_array[:, 0].min():.0f}m to {coords_array[:, 0].max():.0f}m"
                    y_range = f"{coords_array[:, 1].min():.0f}m to {coords_array[:, 1].max():.0f}m"
                    z_range = f"{coords_array[:, 2].min():.0f}m to {coords_array[:, 2].max():.0f}m"
                    debug_print(f"[OUTPUT_DATA] Trajectory coordinate ranges:")
                    debug_print(f"  X: {x_range}")
                    debug_print(f"  Y: {y_range}")
                    debug_print(f"  Z: {z_range}")

            debug_print(f"[OUTPUT_DATA] Pillars in 3D {project_coordinate_system}: {len(pillars_project_coords)} pillars")
            if pillars_project_coords:
                for i, pillar in enumerate(pillars_project_coords[:5]):  # Show first 5
                    debug_print(f"  Pillar {pillar['id']}: Local({pillar['x']:.1f}m, {pillar['y']:.1f}m, {pillar['z']:.1f}m)")
                if len(pillars_project_coords) > 5:
                    debug_print(f"  ... and {len(pillars_project_coords) - 5} more pillars")

                # Show coordinate ranges for pillars
                if pillars_project_coords:
                    x_coords = [p['x'] for p in pillars_project_coords]
                    y_coords = [p['y'] for p in pillars_project_coords]
                    z_coords = [p['z'] for p in pillars_project_coords]
                    debug_print(f"[OUTPUT_DATA] Pillar coordinate ranges:")
                    debug_print(f"  X: {min(x_coords):.0f}m to {max(x_coords):.0f}m")
                    debug_print(f"  Y: {min(y_coords):.0f}m to {max(y_coords):.0f}m")
                    debug_print(f"  Z: {min(z_coords):.0f}m to {max(z_coords):.0f}m")

            debug_print(f"[OUTPUT_DATA] Safety zones in 3D {project_coordinate_system}: will be processed by update_safety_zones_3d()")
            debug_print(f"[OUTPUT_DATA] Coordinate system used: {project_coordinate_system}")

            debug_print("XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")

            # ------------------------------------------------------------------
            # 3. Determine save directory
            # ------------------------------------------------------------------
            save_dir = Path(".")
            bridge_name = "DefaultBridge"

            if hasattr(self, "data_loader") and self.data_loader and hasattr(self.data_loader, "project_data"):
                project_data = self.data_loader.project_data
                if project_data:
                    bridge_name = project_data.get("bridge_name", "DefaultBridge")
                    project_dir_base = project_data.get("project_dir_base", ".")
                    viz_dir = Path(project_dir_base) / bridge_name / "02_Visualization"
                    temp_dir = viz_dir / "temp"
                    temp_dir.mkdir(parents=True, exist_ok=True)
                    save_dir = temp_dir
                    debug_print(f"[PLY_SAVE] Using visualization directory: {save_dir}")

            # Store for later use by update_safety_zones_3d
            self._last_save_dir = save_dir
            self._last_bridge_name = bridge_name

            # ------------------------------------------------------------------
            # 4. Initialize 3D viewer if not already done
            # ------------------------------------------------------------------
            if self.visualizer is None:
                debug_print("[IMPROVED_BRIDGE] Initializing 3D viewer...")
                holder = self.ui.findChild(QWidget, 'Placeholder2')
                if holder is None:
                    debug_print('[IMPROVED_BRIDGE] Placeholder2 not found – cannot show viewer')
                    return

                parent = holder.parent()
                if parent is None:
                    debug_print('[IMPROVED_BRIDGE] Placeholder2 has no parent')
                    return

                if isinstance(parent, QSplitter):
                    debug_print('[IMPROVED_BRIDGE] Found QSplitter parent - using splitter replacement')
                    debug_print(f'[IMPROVED_BRIDGE] QSplitter children count: {parent.count()}')
                    debug_print(f'[IMPROVED_BRIDGE] Placeholder2 index in splitter: {parent.indexOf(holder)}')

                    debug_print('[IMPROVED_BRIDGE] Creating VisualizationWidget...')
                    self.visualizer = VisualizationWidget(self.ui)
                    debug_print(f'[IMPROVED_BRIDGE] Created visualizer: {self.visualizer}')

                    idx = parent.indexOf(holder)
                    parent.replaceWidget(idx, self.visualizer)
                    holder.deleteLater()

                    debug_print("[IMPROVED_BRIDGE] 3D viewer initialized successfully in QSplitter")
                    debug_print(f'[IMPROVED_BRIDGE] Visualizer has plotter: {hasattr(self.visualizer, "plotter")}')
                    debug_print(f'[IMPROVED_BRIDGE] Visualizer plotter: {getattr(self.visualizer, "plotter", None)}')
                else:
                    debug_print('[IMPROVED_BRIDGE] Using fallback layout approach')
                    parent_layout = parent.layout()
                    if parent_layout is None:
                        debug_print('[IMPROVED_BRIDGE] Placeholder2 has no parent layout')
                        return

                    idx = parent_layout.indexOf(holder)
                    parent_layout.removeWidget(holder)
                    holder.deleteLater()

                    self.visualizer = VisualizationWidget(self.ui)
                    parent_layout.insertWidget(idx, self.visualizer)
                    debug_print("[IMPROVED_BRIDGE] 3D viewer initialized successfully in layout")

            # ------------------------------------------------------------------
            # 5. Create 3D trajectory line (BLUE) and bridge deck extrusion
            # ------------------------------------------------------------------
            mesh_files = {}

            # 5a. Trajectory line
            if trajectory_project_coords and len(trajectory_project_coords) >= 2:
                debug_print(f"\n[3D_TRAJECTORY] Creating 3D trajectory line with {len(trajectory_project_coords)} points in {project_coordinate_system} coordinates...")
                try:

                    def create_trajectory_line(trajectory_points, height_offset=0.0):
                        """Create a 3D trajectory line from coordinate points.
                        
                        Args:
                            trajectory_points (list): List of [lat, lon] or [x, y, z] coordinate points
                            height_offset (float): Height to add to all points (if 2D coordinates)
                        
                        Returns:
                            pyvista.PolyData: Trajectory line mesh
                        """
                        # Convert to numpy array and ensure 3D coordinates
                        points = np.array(trajectory_points)
                        
                        # If 2D coordinates (lat/lon), convert to 3D by adding height
                        if points.shape[1] == 2:
                            # Add height offset as Z coordinate
                            height_column = np.full((points.shape[0], 1), height_offset)
                            points = np.hstack([points, height_column])
                        elif points.shape[1] > 3:
                            # Take only first 3 columns if more than 3D
                            points = points[:, :3]
                        
                        # Create line connectivity (connect consecutive points)
                        n_points = len(points)
                        if n_points < 2:
                            raise ValueError("Need at least 2 points to create a trajectory line")
                        
                        # Create cells array for line segments
                        cells = []
                        for i in range(n_points - 1):
                            cells.extend([2, i, i + 1])  # 2 points per line segment
                        
                        # Create PyVista line object
                        line_mesh = pv.PolyData(points, lines=cells)
                        
                        return line_mesh




                    trajectory_mesh = create_trajectory_line(trajectory_project_coords, height_offset=0.0)
                    trajectory_ply = save_dir / "trajectory.ply"
                    if trajectory_ply.exists():
                        try:
                            trajectory_ply.unlink()
                            debug_print(f"[PLY_SAVE] Replaced existing trajectory.ply")
                        except Exception as e:
                            debug_print(f"[PLY_SAVE] Warning: Could not remove existing trajectory.ply: {e}")
                    trajectory_mesh.save(str(trajectory_ply))
                    mesh_files["3D Trajectory"] = str(trajectory_ply)

                    debug_print(f"[3D_VIEWER] Adding 3D Trajectory (blue line) in {project_coordinate_system}")

                    coords_array = np.asarray(trajectory_project_coords, dtype=float)
                    mask = np.isfinite(coords_array).all(axis=1)
                    coords_array = coords_array[mask]
                    if coords_array.shape[0] < 2:
                        debug_print("[ERROR] Insufficient valid trajectory points after cleaning for ranges")
                    else:
                        x_range = f"{coords_array[:, 0].min():.0f}m to {coords_array[:, 0].max():.0f}m"
                        y_range = f"{coords_array[:, 1].min():.0f}m to {coords_array[:, 1].max():.0f}m"
                        z_range = f"{coords_array[:, 2].min():.0f}m to {coords_array[:, 2].max():.0f}m"
                        debug_print(f"[3D_TRAJECTORY] Coordinate ranges in {project_coordinate_system}:")
                        debug_print(f"  X: {x_range} (Easting)")
                        debug_print(f"  Y: {y_range} (Northing)")
                        debug_print(f"  Z: {z_range} (Height)")
                except Exception as e:
                    debug_print(f"[ERROR] Failed to create 3D trajectory: {e}")
                    import traceback; traceback.print_exc()
            else:
                debug_print(f"[ERROR] Insufficient trajectory points: {len(trajectory_project_coords) if trajectory_project_coords else 0}")

            # 5b. Bridge deck
            crosssection_2d = getattr(self, "crosssection_transformed_points", [])
            if trajectory_project_coords and crosssection_2d is not None and len(crosssection_2d) > 0:
                debug_print(f"\n[BRIDGE_DECK] Creating bridge deck by extruding cross-section over trajectory...")
                try:
                    

                    cs_points = crosssection_2d.tolist() if hasattr(crosssection_2d, "tolist") else list(crosssection_2d)

                    debug_print(f"[BRIDGE_DECK] Improving cross-section positioning...")
                    y_coords = [pt[0] for pt in cs_points if len(pt) >= 2]
                    x_coords = [pt[1] for pt in cs_points if len(pt) >= 2]

                    if y_coords:
                        y_array = np.asarray(y_coords, dtype=float)
                        x_array = np.asarray(x_coords, dtype=float)
                        closest_idx = np.argmin(np.abs(y_array))
                        centerline_x = 0.0
                        positive_y = y_array > 0
                        negative_y = y_array < 0
                        if np.any(positive_y) and np.any(negative_y):
                            pos_indices = np.where(positive_y)[0]
                            neg_indices = np.where(negative_y)[0]
                            min_pos_idx = pos_indices[np.argmin(y_array[pos_indices])]
                            max_neg_idx = neg_indices[np.argmax(y_array[neg_indices])]
                            y1, x1 = y_array[max_neg_idx], x_array[max_neg_idx]
                            y2, x2 = y_array[min_pos_idx], x_array[min_pos_idx]
                            if y2 != y1:
                                centerline_x = x1 + (0 - y1) * (x2 - x1) / (y2 - y1)
                                debug_print(f"[BRIDGE_DECK] Interpolated bridge centerline at x={centerline_x:.3f}m")
                            else:
                                centerline_x = (x1 + x2) / 2
                                debug_print(f"[BRIDGE_DECK] Average bridge centerline at x={centerline_x:.3f}m")
                        else:
                            centerline_x = x_array[closest_idx]
                            debug_print(f"[BRIDGE_DECK] Closest bridge centerline at x={centerline_x:.3f}m")

                        cs_3d = []
                        for pt in cs_points:
                            if len(pt) >= 2:
                                across = float(pt[0])
                                height = float(pt[1])
                                cs_3d.append([0.0, across, height])

                        debug_print(f"[BRIDGE_DECK] Using {len(cs_3d)} cross-section points (along=0, across=pt[0], height=pt[1])")

                    trajectory_array = np.asarray(trajectory_project_coords, dtype=float)
                    if trajectory_array.shape[0] >= 2:
                        diffs = np.diff(trajectory_array[:, :3], axis=0)
                        seg_lengths = np.linalg.norm(diffs, axis=1)
                        total_length = float(np.nansum(seg_lengths))
                    else:
                        total_length = 0.0

                    debug_print(f"[BRIDGE_DECK] Trajectory analysis:")
                    debug_print(f"  - Original points: {len(trajectory_project_coords)}")
                    debug_print(f"  - Calculated total length: {total_length:.1f}m")

                    num_samples = max(50, len(trajectory_project_coords) * 3)
                    debug_print(f"[BRIDGE_DECK] Using {num_samples} samples for extrusion")

                    debug_print(f"[BRIDGE_DECK] Extruding cross-section perpendicular to trajectory in {project_coordinate_system}")
                    bridge_modeler = BridgeModeler(trajectory_project_coords, cs_3d)
                    vertices, trajectory_samples, normals, binormals = bridge_modeler.create_bridge_representation(num_samples)
                    self.trajectory_samples = trajectory_samples
                    faces = bridge_modeler.calculate_faces(num_samples)

                    bridge_ply = save_dir / "bridge_deck.ply"
                    if bridge_ply.exists():
                        try:
                            bridge_ply.unlink()
                            debug_print(f"[PLY_SAVE] Replaced existing bridge_deck.ply")
                        except Exception as e:
                            debug_print(f"[PLY_SAVE] Warning: Could not remove existing bridge_deck.ply: {e}")
                    bridge_modeler.write_ply_with_vertices_and_faces(bridge_ply, vertices, faces)
                    mesh_files["Bridge Deck"] = str(bridge_ply)

                    debug_print(f"[3D_VIEWER] Adding Bridge Deck (brown) extruded in {project_coordinate_system}")
                    self.visualizer.add_mesh_with_button(str(bridge_ply), "Bridge Deck", color=(0.8, 0.6, 0.4), opacity=0.9)

                    vertices_array = np.array(vertices)
                    x_span = vertices_array[:, 0].max() - vertices_array[:, 0].min()
                    y_span = vertices_array[:, 1].max() - vertices_array[:, 1].min()
                    z_span = vertices_array[:, 2].max() - vertices_array[:, 2].min()
                    debug_print(f"[BRIDGE_DECK] Successfully created bridge deck:")
                    debug_print(f"  ✓ {len(vertices)} vertices generated from extrusion")
                    debug_print(f"  ✓ {len(faces)} faces for 3D mesh")
                    debug_print(f"  ✓ Cross-section extruded perpendicular to {len(trajectory_project_coords)}-point trajectory")
                    debug_print(f"  ✓ Using metric {project_coordinate_system} coordinates")
                    debug_print(f"[BRIDGE_DECK] Generated mesh dimensions:")
                    debug_print(f"  - Length along trajectory: {max(x_span, y_span):.1f}m")
                    debug_print(f"  - Width across bridge: {min(x_span, y_span):.1f}m")
                    debug_print(f"  - Height span: {z_span:.1f}m")
                except Exception as e:
                    debug_print(f"[ERROR] Failed to create bridge deck: {e}")
                    import traceback; traceback.print_exc()
            else:
                debug_print(f"[BRIDGE_DECK] Skipping bridge deck creation:")
                if not trajectory_project_coords:
                    debug_print(f"  - No trajectory points available")
                elif not crosssection_2d or len(crosssection_2d) == 0:
                    debug_print(f"  - No cross-section data available (found {len(crosssection_2d) if crosssection_2d else 0} points)")
                    debug_print(f"  - Load cross-section image and process it first")

            # 5c. Pillars
            if pillars_project_coords:
                debug_print(f"\n[PILLARS] Creating improved pillar models for {len(pillars_project_coords)} pillars...")
                try:
                    def create_improved_pillar_mesh(p1, p2, trajectory_points, bridge_vertices=None):
                        
                        p1 = np.asarray(p1[:3], dtype=float); p2 = np.asarray(p2[:3], dtype=float)
                        direction = p2 - p1
                        norm = np.linalg.norm(direction)
                        direction_unit = direction / norm if norm > 1e-9 else np.array([1.0, 0.0, 0.0], dtype=float)
                        perp_vector = np.array([-direction_unit[1], direction_unit[0], 0.0], dtype=float) * 0.5
                        base_corners = np.array([p1 + perp_vector, p1 - perp_vector, p2 - perp_vector, p2 + perp_vector])

                        center = (p1 + p2) / 2
                        pillar_height = 15.0
                        if bridge_vertices is not None and len(bridge_vertices) > 0:
                            bridge_array = np.array(bridge_vertices)
                            distances = np.linalg.norm(bridge_array[:, :2] - center[:2], axis=1)
                            closest_idx = np.argmin(distances)
                            closest_bridge_point = bridge_array[closest_idx]
                            pillar_height = closest_bridge_point[2] - center[2]
                            debug_print(f"[PILLAR] Height from bridge deck: {pillar_height:.1f}m (deck {closest_bridge_point[2]:.1f}m, base {center[2]:.1f}m)")
                        elif trajectory_points is not None and len(trajectory_points) > 0:
                            traj_array = np.asarray(trajectory_points, dtype=float)
                            mask = np.isfinite(traj_array).all(axis=1)
                            traj_array = traj_array[mask]
                            distances = np.linalg.norm(traj_array[:, :2] - center[:2], axis=1)
                            closest_idx = np.argmin(distances)
                            if closest_idx > 0 and closest_idx < len(traj_array) - 1:
                                p_before = traj_array[closest_idx - 1]
                                p_closest = traj_array[closest_idx]
                                p_after = traj_array[closest_idx + 1]
                                avg_height = np.mean([p_before[2], p_closest[2], p_after[2]])
                                pillar_height = avg_height - center[2]
                                debug_print(f"[PILLAR] Height from trajectory: {pillar_height:.1f}m (traj {avg_height:.1f}m)")
                            else:
                                pillar_height = traj_array[closest_idx][2] - center[2]
                                debug_print(f"[PILLAR] Height from trajectory: {pillar_height:.1f}m (traj {traj_array[closest_idx][2]:.1f}m)")

                        pillar_height = max(pillar_height, 5.0)
                        base_z = min(p1[2], p2[2])
                        top_z = base_z + pillar_height
                        base_verts = np.column_stack([base_corners[:, :2], np.full(4, base_z)])
                        top_verts  = np.column_stack([base_corners[:, :2], np.full(4, top_z)])
                        vertices = np.vstack([base_verts, top_verts])

                        faces = []
                        faces.append([0, 3, 2, 1])  # bottom
                        faces.append([4, 5, 6, 7])  # top
                        for i in range(4):
                            next_i = (i + 1) % 4
                            faces.append([i, next_i, next_i + 4, i + 4])
                        debug_print(f"[PILLAR] Created pillar: {pillar_height:.1f}m height")
                        return vertices, faces

                    all_vertices, all_faces = [], []
                    bridge_vertices = None
                    if "Bridge Deck" in mesh_files:
                        try:
                            bridge_vertices = vertices  # from deck creation above
                        except:
                            bridge_vertices = None

                    for i in range(0, len(pillars_project_coords), 2):
                        if i + 1 < len(pillars_project_coords):
                            p1d = pillars_project_coords[i]; p2d = pillars_project_coords[i + 1]
                            p1 = [p1d["x"], p1d["y"], p1d["z"]]
                            p2 = [p2d["x"], p2d["y"], p2d["z"]]
                            debug_print(f"\n[PILLAR_PAIR] Processing pillar pair {i//2 + 1}: {p1d['id']} ↔ {p2d['id']}")
                            pillar_verts, pillar_faces = create_improved_pillar_mesh(p1, p2, trajectory_project_coords, bridge_vertices)
                            base_index = len(all_vertices)
                            all_vertices.extend(pillar_verts)
                            for face in pillar_faces:
                                adjusted_face = [idx + base_index for idx in face]
                                all_faces.append(adjusted_face)

                    vertices, faces = all_vertices, all_faces
                    if vertices and faces:
                        pillars_ply = save_dir / "pillars.ply"
                        if pillars_ply.exists():
                            try:
                                pillars_ply.unlink()
                                debug_print(f"[PLY_SAVE] Replaced existing pillars.ply")
                            except Exception as e:
                                debug_print(f"[PLY_SAVE] Warning: Could not remove existing pillars.ply: {e}")

                        with open(pillars_ply, 'w', encoding='utf-8') as f:
                            f.write('ply\nformat ascii 1.0\n')
                            f.write(f'element vertex {len(vertices)}\n')
                            f.write('property float x\nproperty float y\nproperty float z\n')
                            f.write(f'element face {len(faces)}\n')
                            f.write('property list uchar int vertex_indices\nend_header\n')
                            for v in vertices:
                                f.write(f"{v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
                            for face in faces:
                                f.write(f"4 {' '.join(map(str, face))}\n")

                        mesh_files["Bridge Pillars"] = str(pillars_ply)
                        debug_print(f"[3D_VIEWER] Adding Improved Bridge Pillars (gray) in {project_coordinate_system}")
                        self.visualizer.add_mesh_with_button(str(pillars_ply), "Bridge Pillars", color=(0.7, 0.7, 0.7), opacity=0.9)

                        debug_print(f"[PILLARS] Created improved pillar models:")
                        debug_print(f"  ✓ {len(vertices)} vertices from {len(pillars_project_coords)//2} pillar pairs")
                        debug_print(f"  ✓ {len(faces)} faces (6 faces per pillar: 4 sides + top + bottom)")
                        debug_print(f"  ✓ Rectangular construction: 0.5m offset method")
                        debug_print(f"  ✓ Automatic height detection from bridge deck/trajectory")
                        debug_print(f"  ✓ Proper connection between pillar point pairs")
                except Exception as e:
                    debug_print(f"[ERROR] Failed to create pillars: {e}")
                    import traceback; traceback.print_exc()


            self.pillars_project_coords = pillars_project_coords
            self.pillars_project_xy = [(p["x"], p["y"]) for p in pillars_project_coords]
            # ------------------------------------------------------------------
            # 5d. SAFETY ZONES (delegated to the single, canonical updater)
            # ------------------------------------------------------------------
            # Use memory here to avoid race/availability issues with the web view.
            self.update_safety_zones_3d(fetch_from_map=False)
            
            # ------------------------------------------------------------------
            # Store mesh files for cleanup
            # ------------------------------------------------------------------
            self._improved_mesh_files = mesh_files
            self._improved_3d_model_built = True

            debug_print(f"\n[SUCCESS] 3D bridge modeling completed!")
            debug_print(f"✓ Using global metric coordinate system: {project_coordinate_system}")
            debug_print(f"✓ 3D Trajectory line (blue) - shows flight path")
            if "Bridge Deck" in mesh_files:
                debug_print(f"✓ Bridge deck (brown) - cross-section extruded along trajectory")
            if "Bridge Pillars" in mesh_files:
                debug_print(f"✓ Bridge pillars (gray) - structural support elements")
            debug_print(f"✓ Safety zones handled by unified updater")
            debug_print(f"✓ Total {len(mesh_files)} component(s) created using proper metric coordinates")

        except Exception as e:
            debug_print(f"[ERROR] build_improved_3d_bridge_model failed: {e}")
            import traceback; traceback.print_exc()


    def _parse_all_flight_route_parameters(self):
        """Return parsed flight_routes dict from unified parser with enhanced validation."""
        try:
            self._update_parsed_data()
            flight_routes = self.parsed_data.get("flight_routes", {})
            
            # Validate required flight-route parameters
            required = (
                "safety_zones_clearance",
                "safety_zones_clearance_adjust",
                "transition_mode",
                "transition_vertical_offset",
                "transition_horizontal_offset",
                "order",
                "standard_flight_routes",
                "flight_speed_map",
            )
            # Detailed dump of all flight-route parameters
            debug_print("[FLIGHT_ROUTE_PARAMS] ----------------------------------------")
            if flight_routes:
                for k, v in sorted(flight_routes.items()):
                    debug_print(f"[FLIGHT_ROUTE_PARAMS] {k:<25}: {v!r} ({type(v).__name__})")
            else:
                debug_print("[FLIGHT_ROUTE_PARAMS] <NO DATA>")
            missing = [k for k in required if k not in flight_routes]
            if missing:
                debug_print(f"[ERROR] Missing flight-route parameters: {', '.join(missing)}")
            debug_print("[FLIGHT_ROUTE_PARAMS] ----------------------------------------")
            return flight_routes
            
        except Exception as e:
            debug_print(f"❌ Error parsing flight route parameters: {e}")
            return {}

    def _parse_safety_zone_parameters(self):
        """Return flight route dict; call-site can pick needed keys."""
        return self._parse_all_flight_route_parameters()
    
    def update_safety_zones_3d(self, fetch_from_map: bool = True):
        """Update ONLY safety zones in the viewer; mirrors map; silent when none; keeps files tidy."""
        debug_print("\n[UPDATE_SAFETY_ZONES] ===== UPDATING 3D SAFETY ZONES =====")
        try:
            # Viewer required; don’t alter anything if it’s not ready
            if not getattr(self, 'visualizer', None):
                debug_print("[UPDATE_SAFETY_ZONES] ❌ No visualizer; nothing to update.")
                return
                    # Read zones from the map (or reuse memory)
            zones = self._get_zones_from_map_sync() if fetch_from_map else list(self.current_safety_zones or [])
            zones = zones if isinstance(zones, list) else []
            self.current_safety_zones = zones
            debug_print(f"[UPDATE_SAFETY_ZONES] Map reports {len(zones)} zone(s)")

            save_dir = getattr(self, '_last_save_dir', Path("."))
            bridge_name = getattr(self, '_last_bridge_name', "DefaultBridge")

            # If none → clear viewer + disk silently and exit
            if not zones:
                debug_print("[UPDATE_SAFETY_ZONES] No zones → clearing viewer & temp files (silent).")
                if hasattr(self.visualizer, 'remove_all_safety_zones'):
                    self.visualizer.remove_all_safety_zones()
                self._cleanup_stale_safety_zone_files(save_dir, keep_paths=[])
                return

            # Transform precondition (don’t fake transforms)
            transform_func = getattr(self, '_last_transform_func', None)
            if not transform_func:
                debug_print("[UPDATE_SAFETY_ZONES] ❌ Missing transform. Build the model first. (No changes applied.)")
                return

            # Remove ONLY safety zones (keep everything else)
            debug_print("[UPDATE_SAFETY_ZONES] Removing existing safety zone visualizations…")
            if hasattr(self.visualizer, 'remove_all_safety_zones'):
                self.visualizer.remove_all_safety_zones()
                    # Parse parameters
            safety_params = self._parse_safety_zone_parameters()
            clearance_per_zone = safety_params.get('safety_zones_clearance', [])
            default_z_min = safety_params.get('default_z_min', 0.0)
            default_z_max = safety_params.get('default_z_max', 50.0)

            # Transform rings
            safety_zones_project_coords = []
            debug_print(f"[UPDATE_SAFETY_ZONES] Processing {len(zones)} zones with {len(clearance_per_zone)} clearance specs")
            for idx, zone in enumerate(zones):
                pts_proj = []
                for lat, lon in zone.get('points', []):
                    x, y, z = transform_func(lat, lon, 0.0)
                    pts_proj.append([x, y, z])

                if len(pts_proj) < 3:
                    debug_print(f"[UPDATE_SAFETY_ZONES] Skipping '{zone.get('id','?')}' (<3 pts)")
                    continue

                if idx < len(clearance_per_zone):
                    z_min, z_max = clearance_per_zone[idx]
                else:
                    z_min, z_max = default_z_min, default_z_max

                safety_zones_project_coords.append({
                    'id': zone['id'],
                    'points': pts_proj,
                    'z_min': float(z_min),
                    'z_max': float(z_max),
                })

            # If nothing valid → clear viewer + disk silently & exit
            if not safety_zones_project_coords:
                debug_print("[UPDATE_SAFETY_ZONES] No valid zones after transform → clearing viewer & temp files (silent).")
                if hasattr(self.visualizer, 'remove_all_safety_zones'):
                    self.visualizer.remove_all_safety_zones()
                self._cleanup_stale_safety_zone_files(save_dir, keep_paths=[])
                return

            # Build meshes
            verts, faces = self._create_3d_safety_zones(safety_zones_project_coords, safety_params)
            if not verts or not faces:
                debug_print("[UPDATE_SAFETY_ZONES] ❌ Mesh creation failed → clearing zones & temp files (silent).")
                if hasattr(self.visualizer, 'remove_all_safety_zones'):
                    self.visualizer.remove_all_safety_zones()
                self._cleanup_stale_safety_zone_files(save_dir, keep_paths=[])
                return

            # Save with your existing helper (returns {zone_id: path})
            saved = self._save_safety_zones_separately(
                safety_zones_project_coords, safety_params, save_dir, bridge_name
            )

            # Rename to contiguous files per current update and clean stale files
            ordered_zone_ids = [z['id'] for z in safety_zones_project_coords]
            new_paths_by_zone_id = {}
            keep_paths = []

            for idx, zid in enumerate(ordered_zone_ids, start=1):
                orig = Path(saved[zid])
                target = Path(save_dir) / f"safety_zone_{idx:02d}.ply"
                try:
                    if orig.resolve() != target.resolve():
                        try:
                            # fast path: same filesystem
                            orig.replace(target)
                        except Exception:
                            # fallback: copy bytes then remove original
                            target.write_bytes(orig.read_bytes())
                            try:
                                orig.unlink()
                            except FileNotFoundError:
                                pass
                except Exception as e:
                    debug_print(f"[FILES] rename failed {orig.name} -> {target.name}: {e}")
                    target = orig  # fall back

                new_paths_by_zone_id[zid] = target
                keep_paths.append(target)

            # Remove stale PLYs from previous runs
            self._cleanup_stale_safety_zone_files(save_dir, keep_paths)

            # Ensure registries exist (in case older Visualizer instances are in memory)
            if not hasattr(self.visualizer, "_safety_zone_registry"):
                self.visualizer._safety_zone_registry = set()
            if not hasattr(self.visualizer, "_display_to_ident"):
                self.visualizer._display_to_ident = {}

            # Add back to viewer with clean, sequential labels
            debug_print(f"[UPDATE_SAFETY_ZONES] Adding {len(ordered_zone_ids)} safety zones to 3D viewer")
            added = 0
            for idx, zid in enumerate(ordered_zone_ids, start=1):
                ply_path = new_paths_by_zone_id[zid]
                display_name = f"Safety Zone {idx}"
                try:
                    self.visualizer.add_mesh_with_button(
                        str(ply_path),
                        display_name,
                        color=(1.0, 0.2, 0.2),
                        opacity=0.4,
                        is_safety_zone=True
                    )
                    added += 1
                except Exception as e:
                    debug_print(f"[UPDATE_SAFETY_ZONES] add failed {display_name}: {e}")

            if hasattr(self.visualizer, 'plotter'):
                self.visualizer.plotter.render()

            debug_print(f"[UPDATE_SAFETY_ZONES] ✅ Updated {added}/{len(ordered_zone_ids)} safety zones.")
        except Exception as e:
            debug_print(f"[UPDATE_SAFETY_ZONES] ❌ Error: {e}")
            import traceback; traceback.print_exc()
    
    def _get_zones_from_map_sync(self, timeout_ms: int = 5000):
        """Return zones from Leaflet, or [] if none/timeout/error. Falls back to memory if map yields none."""
        # If there’s no web page, fall back to whatever we have in memory.
        if not getattr(self, "debug_page", None):
            return list(self.current_safety_zones or [])

        JS_GET_ZONES = r"""
            (function() {
                function collectFromLayer(layer, zones) {
                    try {
                        // Accept polygons that look like safety zones; be tolerant.
                        var cls = ((layer && layer.options && layer.options.className) || "").toLowerCase();
                        var looksSafety = cls.includes('safety') || cls.includes('zone') || cls.includes('completed');

                        var hasPoly = layer && typeof layer.getLatLngs === 'function';
                        if (!hasPoly) return;

                        var rings = layer.getLatLngs();
                        if (!rings || rings.length === 0) return;

                        var ring = Array.isArray(rings[0]) ? rings[0] : rings; // handle single-ring polygons
                        if (!ring || ring.length < 3) return;

                        // Popup hint also marks it as safety zone
                        var popupStr = "";
                        if (layer.getPopup && layer.getPopup()) {
                            var c = layer.getPopup().getContent && layer.getPopup().getContent();
                            popupStr = (typeof c === 'string') ? c : "";
                            if (/safety\s*zone/i.test(popupStr)) looksSafety = true;
                        }

                        // If we can't prove it's a safety zone, still accept if caller specifically asked for all polygons
                        if (!looksSafety && typeof window.__ACCEPT_ALL_POLYGONS__ === 'undefined') return;

                        var pts = [];
                        for (var i=0; i<ring.length; i++) pts.push([ring[i].lat, ring[i].lng]);

                        // Prefer id from popup; else generate
                        var zid = null;
                        var m = popupStr.match(/Safety Zone:\s*([^\n<]+)/i);
                        if (m && m[1]) zid = m[1].trim();
                        if (!zid) zid = "zone_" + zones.length;

                        zones.push({id: zid, points: pts});
                    } catch (e) { /* be silent */ }
                }

                var zones = [];

                // Primary: dedicated layer
                if (window.safetyZoneLayer && typeof window.safetyZoneLayer.eachLayer === 'function') {
                    window.safetyZoneLayer.eachLayer(function(layer){ collectFromLayer(layer, zones); });
                }

                // Fallback: scan all map layers
                if ((!zones.length) && window.map && typeof window.map.eachLayer === 'function') {
                    window.map.eachLayer(function(layer){ collectFromLayer(layer, zones); });
                }

                return zones;
            })();
        """

        loop = QEventLoop()
        box = {"done": False, "res": []}

        def _cb(res):
            box["res"] = res if isinstance(res, list) else []
            box["done"] = True
            loop.quit()

        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(loop.quit)

        try:
            self.debug_page.runJavaScript(JS_GET_ZONES, _cb)
            timer.start(timeout_ms)
            loop.exec()
        finally:
            timer.stop()

        # If JS couldn’t find any but we have in-memory zones, prefer memory
        if not box["done"]:
            return []
        if not box["res"] and getattr(self, "current_safety_zones", None):
            return list(self.current_safety_zones)
        return box["res"]
    def _cleanup_stale_safety_zone_files(self, save_dir: Path, keep_paths: list[Path]):
        """Delete safety-zone PLYs we no longer use (pattern-based, safe)."""
        try:
            save_dir = Path(save_dir)
            keep_set = {Path(p).resolve() for p in (keep_paths or [])}
            for p in save_dir.glob("safety_zone_*.ply"):
                rp = p.resolve()
                if rp not in keep_set:
                    try:
                        p.unlink()
                        debug_print(f"[CLEAN] removed stale file: {p.name}")
                    except Exception as e:
                        debug_print(f"[CLEAN] warn: could not remove {p.name}: {e}")
        except Exception as e:
            debug_print(f"[CLEAN] error during stale cleanup: {e}")
    def _save_safety_zones_separately(self, safety_zones_coords, safety_params, save_dir, bridge_name):
        """Save each safety zone as a separate PLY file with simplified names."""
        separate_zone_files = {}
        
        debug_print(f"[SAFETY_ZONES] Saving {len(safety_zones_coords)} safety zones separately...")
        
        for zone in safety_zones_coords:
            zone_id = zone['id']
            points_2d = zone['points']
            z_min = zone['z_min']
            z_max = zone['z_max']
            
            if len(points_2d) < 3:
                debug_print(f"[SAFETY_ZONES] Skipping zone {zone_id}: insufficient points ({len(points_2d)})")
                continue
            
            # Create 3D mesh for this individual zone
            zone_vertices, zone_faces = self._create_single_safety_zone_mesh(points_2d, z_min, z_max)
            
            if zone_vertices and zone_faces:
                # Create simplified filename
                zone_ply_path = save_dir / f"safety_zone_{zone_id}.ply"
                
                # Remove existing file if it exists to avoid conflicts
                if zone_ply_path.exists():
                    try:
                        zone_ply_path.unlink()
                        debug_print(f"[PLY_SAVE] Replaced existing safety_zone_{zone_id}.ply")
                    except Exception as e:
                        debug_print(f"[PLY_SAVE] Warning: Could not remove existing safety_zone_{zone_id}.ply: {e}")
                
                # Write PLY file for this zone
                with open(zone_ply_path, 'w', encoding='utf-8') as f:
                    f.write('ply\nformat ascii 1.0\n')
                    f.write(f'element vertex {len(zone_vertices)}\n')
                    f.write('property float x\nproperty float y\nproperty float z\n')
                    f.write(f'element face {len(zone_faces)}\n')
                    f.write('property list uchar int vertex_indices\nend_header\n')
                    
                    # Write vertices
                    for v in zone_vertices:
                        f.write(f"{v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
                    
                    # Write faces
                    for face in zone_faces:
                        f.write(f"3 {' '.join(map(str, face))}\n")  # Triangular faces
                
                separate_zone_files[zone_id] = zone_ply_path
                debug_print(f"[SAFETY_ZONES] Zone {zone_id}: saved {len(zone_vertices)} vertices, {len(zone_faces)} faces to {zone_ply_path.name}")
        
        debug_print(f"[SAFETY_ZONES] Successfully saved {len(separate_zone_files)} safety zones separately")
        return separate_zone_files
    def _create_single_safety_zone_mesh(self, points_2d, z_min, z_max):
        """Create 3D mesh for a single safety zone as vertical extrusion of 2D polygon."""
        vertices = []
        faces = []
        
        n_points = len(points_2d)
        if n_points < 3:
            return vertices, faces
        
        # Bottom polygon vertices (at z_min)
        for x, y, _ in points_2d:
            vertices.append([x, y, z_min])
        
        # Top polygon vertices (at z_max)
        for x, y, _ in points_2d:
            vertices.append([x, y, z_max])
        
        # Create triangular faces for the 3D volume
        
        # 1. Bottom face (triangulated polygon)
        for i in range(1, n_points - 1):
            face = [0, i, i + 1]
            faces.append(face)
        
        # 2. Top face (triangulated polygon, reversed winding)
        top_base = n_points
        for i in range(1, n_points - 1):
            face = [top_base, top_base + i + 1, top_base + i]
            faces.append(face)
        
        # 3. Side faces (connecting bottom to top)
        for i in range(n_points):
            next_i = (i + 1) % n_points
            
            # Two triangles per side edge
            bottom_i = i
            bottom_next = next_i
            top_i = n_points + i
            top_next = n_points + next_i
            
            # First triangle: bottom_i -> bottom_next -> top_i
            faces.append([bottom_i, bottom_next, top_i])
            
            # Second triangle: bottom_next -> top_next -> top_i
            faces.append([bottom_next, top_next, top_i])
        
        return vertices, faces
    def _create_3d_safety_zones(self, safety_zones_coords, safety_params):
        """Create 3D safety zone meshes as vertical extrusions of the 2D polygons."""
        all_vertices = []
        all_faces = []
        
        debug_print(f"[SAFETY_ZONES] Creating 3D volumes with individual zone heights")
        
        for zone in safety_zones_coords:
            zone_id = zone['id']
            points_2d = zone['points']
            z_min = zone['z_min']  # Individual zone minimum height
            z_max = zone['z_max']  # Individual zone maximum height
            
            if len(points_2d) < 3:
                debug_print(f"[SAFETY_ZONES] Skipping zone {zone_id}: insufficient points ({len(points_2d)})")
                continue
            
            debug_print(f"[SAFETY_ZONES] Processing zone {zone_id} with {len(points_2d)} boundary points, height {z_min:.1f}m to {z_max:.1f}m")
            
            # Create bottom and top polygons
            base_index = len(all_vertices)
            
            # Bottom polygon vertices (at z_min)
            bottom_vertices = []
            for x, y, _ in points_2d:
                bottom_vertices.append([x, y, z_min])
                all_vertices.append([x, y, z_min])
            
            # Top polygon vertices (at z_max)
            top_vertices = []
            for x, y, _ in points_2d:
                top_vertices.append([x, y, z_max])
                all_vertices.append([x, y, z_max])
            
            n_points = len(points_2d)
            
            # Create triangular faces for the 3D volume
            
            # 1. Bottom face (triangulated polygon)
            for i in range(1, n_points - 1):
                face = [base_index, base_index + i, base_index + i + 1]
                all_faces.append(face)
            
            # 2. Top face (triangulated polygon, reversed winding)
            top_base = base_index + n_points
            for i in range(1, n_points - 1):
                face = [top_base, top_base + i + 1, top_base + i]
                all_faces.append(face)
            
            # 3. Side faces (connecting bottom to top)
            for i in range(n_points):
                next_i = (i + 1) % n_points
                
                # Two triangles per side edge
                bottom_i = base_index + i
                bottom_next = base_index + next_i
                top_i = base_index + n_points + i
                top_next = base_index + n_points + next_i
                
                # First triangle: bottom_i -> bottom_next -> top_i
                all_faces.append([bottom_i, bottom_next, top_i])
                
                # Second triangle: bottom_next -> top_next -> top_i
                all_faces.append([bottom_next, top_next, top_i])
            
            debug_print(f"[SAFETY_ZONES] Zone {zone_id}: created {n_points * 2} vertices, {2 * (n_points - 2) + 4 * n_points} faces")
        
        debug_print(f"[SAFETY_ZONES] Total 3D safety zone mesh: {len(all_vertices)} vertices, {len(all_faces)} faces")
        return all_vertices, all_faces


   # =====================================================================
    # FLIGHT ROUTE GENERATION SYSTEM: Overview Flight
    # =====================================================================

    def update_flight_routes(self):
        """Generate flight routes using clean FlightPathConstructor."""
        
        try:
            # update the safety zones 3d:
            self.update_safety_zones_3d()

            debug_print("\n" + "="*60)
            debug_print("🎯 UPDATE_FLIGHT_ROUTES - Starting flight route generation")
            debug_print("="*60)

            # Debug: Check current visualizer state before generation
            if hasattr(self, 'visualizer') and self.visualizer:
                current_meshes = list(self.visualizer.meshes.keys())
                debug_print(f"📊 Current meshes before generation: {current_meshes}")
            else:
                debug_print("📊 No visualizer available")
            
            
            
            
            flight_constructor = FlightPathConstructor(self)
            success = flight_constructor.generate_standard_flight_routes()
            
            # Debug: Check visualizer state after generation
            if hasattr(self, 'visualizer') and self.visualizer:
                after_meshes = list(self.visualizer.meshes.keys())
                debug_print(f"📊 Current meshes after generation: {after_meshes}")

                # Check if any important meshes were accidentally removed
                removed_meshes = set(current_meshes) - set(after_meshes)
                if removed_meshes:
                    debug_print(f"⚠️ WARNING: Meshes were removed during flight route generation: {removed_meshes}")
                else:
                    debug_print("✅ All existing meshes preserved during flight route generation")

            if not success:
                error_debug_print("❌ Flight route generation failed")
                QMessageBox.warning(self.ui, "Generation Error", "Flight route generation failed. Check textbox parameter formatting and trajectory data.")
            else:
                debug_print("✅ Flight route generation completed successfully")
                # Backup original waypoints for adjustment functionality
                self._backup_generated_waypoints()
                # Update the waypoints display
                self._update_waypoints_display()
                # Update flight routes combo box
                self._update_flight_routes_combo_box()
            
            debug_print("="*60)
            
        except Exception as e:
            debug_print(f"❌ Flight route generation failed: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self.ui, "Generation Error", f"Flight route generation failed:\n{str(e)}")

    def update_inspection_route(self):
        """Handle btn_tab2_Dock_updateInspectionRoute click – generate under-deck inspection routes."""
        try:
            debug_print("\n" + "="*60)
            debug_print("🛠  UNDER-DECK INSPECTION ROUTE GENERATION")
            debug_print("="*60)
            self.update_safety_zones_3d()
            routes = generate_underdeck_routes(self)
            if not routes:
                debug_print("⚠️  Under-deck route generation returned empty list")
                QMessageBox.warning(self.ui, "Generation Warning", "No under-deck routes were generated. Check input data.")
                return
            debug_print(f"✅ Successfully generated {len(routes)} under-deck routes")
            # Backup original underdeck waypoints for adjustment functionality
            self._backup_generated_waypoints()
            # Update flight routes combo box
            self._update_flight_routes_combo_box()
        except Exception as e:
            debug_print(f"❌ Under-deck route generation failed: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self.ui, "Generation Error", f"Under-deck route generation failed:\n{str(e)}")

    def export_overview_flight(self):
        """Export overview flight routes to console AND KMZ files using centralized exporter."""
        try:
            # First export to console
            exporter = OrbitFlightExporter(self)
            # Check if overview routes exist
            if not hasattr(self, "overview_flight_waypoints") or not self.overview_flight_waypoints:
                QMessageBox.warning(self.ui, "Export Failed", 
                                  "No overview flight routes found.\n"
                                  "Please generate routes first.")
                return
            
            debug_print("\n" + "="*60)
            debug_print("📤 OVERVIEW FLIGHT EXPORT")
            debug_print("="*60)
            console_success = True

            # Export waypoints to PLY for visualization (before transformation)
            self._export_overview_to_ply()

            # Also create KMZ files automatically
            kmz_result = self._export_kmz_automatically("overview")
            
            # Show combined result message with directory open option
            if console_success and kmz_result is True:
                # Get the flightroutes directory for the button
                bridge_name = "Bridge"
                project_dir_base = "."
                if hasattr(self, "parsed_data") and self.parsed_data:
                    project_data = self.parsed_data.get("project", {})
                    bridge_name = project_data.get("bridge_name", "Bridge")
                    project_dir_base = project_data.get("project_dir_base", ".")
                
                sanitized_bridge_name = self._sanitize_filename(bridge_name)
                project_dir = Path(project_dir_base) / sanitized_bridge_name
                flightroutes_dir = project_dir / "03_Flightroutes"

                self._save_complete_program_state()
                # Show success message with open folder option
                reply = QMessageBox.question(
                    self.ui,
                    "Export Complete",
                    "✅ Successfully exported overview flight routes:\n\n"
                    "📋 Console: Coordinates printed to console\n"
                    "📄 PLY Files: Flight route created in project 02_Visualization folder\n"
                    "📁 KMZ Files: Created in project 03_Flightroutes folder\n\n"
                    "Check the console output for detailed coordinates.\n\n"
                    f"📂 KMZ Location: {flightroutes_dir}\n\n"
                    "Would you like to open the KMZ export folder?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    self._open_directory(str(flightroutes_dir))
                    
            elif console_success and kmz_result is False:
                QMessageBox.information(self.ui, "Partial Export", 
                                      "✅ Console export successful\n"
                                      "⚠️ KMZ export failed - check console for details\n\n"
                                      "Check the console output for coordinates.")
            elif console_success and kmz_result is None:
                # User aborted safety validation - no message needed
                debug_print("   📤 Export aborted by user during safety validation")
            
        except Exception as e:
            debug_print(f"❌ Export overview flight failed: {e}")
            import traceback; traceback.print_exc()
            QMessageBox.critical(self.ui, "Export Error", f"Failed to export overview flight:\n{e}")

    def export_underdeck_flight(self):
        """Export underdeck inspection flight routes to console AND KMZ files using centralized exporter."""
        try:
            # First export to console
            exporter = OrbitFlightExporter(self)
            # Check if underdeck routes exist
            if not hasattr(self, "underdeck_flight_waypoints") or not self.underdeck_flight_waypoints:
                QMessageBox.warning(self.ui, "Export Failed", 
                                  "No underdeck inspection routes found.\n"
                                  "Please generate routes first.")
                return
            
            debug_print("\n" + "="*60)
            debug_print("📤 UNDERDECK INSPECTION EXPORT")
            debug_print("="*60)
            console_success = True

            # Export waypoints to PLY for visualization (before transformation)
            self._export_underdeck_to_ply()

            # Also create KMZ files automatically
            kmz_result = self._export_kmz_automatically("underdeck")
            
            # Show combined result message with directory open option
            if console_success and kmz_result is True:
                # Get the flightroutes directory for the button
                bridge_name = "Bridge"
                project_dir_base = "."
                if hasattr(self, "parsed_data") and self.parsed_data:
                    project_data = self.parsed_data.get("project", {})
                    bridge_name = project_data.get("bridge_name", "Bridge")
                    project_dir_base = project_data.get("project_dir_base", ".")
                
                sanitized_bridge_name = self._sanitize_filename(bridge_name)
                project_dir = Path(project_dir_base) / sanitized_bridge_name
                flightroutes_dir = project_dir / "03_Flightroutes"
                
                # Show success message with open folder option
                reply = QMessageBox.question(
                    self.ui,
                    "Export Complete",
                    "✅ Successfully exported underdeck inspection routes:\n\n"
                    "📋 Console: Coordinates printed to console\n"
                    "📄 PLY Files: Individual routes created in project 02_Visualization folder\n"
                    "📁 KMZ Files: Created in project 03_Flightroutes folder\n\n"
                    "Check the console output for detailed coordinates.\n\n"
                    f"📂 KMZ Location: {flightroutes_dir}\n\n"
                    "Would you like to open the KMZ export folder?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.Yes
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    self._open_directory(str(flightroutes_dir))
                    
            elif console_success and kmz_result is False:
                QMessageBox.information(self.ui, "Partial Export", 
                                      "✅ Console export successful\n"
                                      "⚠️ KMZ export failed - check console for details\n\n"
                                      "Check the console output for coordinates.")
            elif console_success and kmz_result is None:
                # User aborted safety validation - no message needed
                debug_print("   📤 Export aborted by user during safety validation")
            
        except Exception as e:
            debug_print(f"❌ Export underdeck flight failed: {e}")
            import traceback; traceback.print_exc()
            QMessageBox.critical(self.ui, "Export Error", f"Failed to export underdeck flight:\n{e}")

    def _open_directory(self, directory_path: str):
        """
        Open a directory in the system file explorer.
        
        Args:
            directory_path: Path to the directory to open
        """
        try:

            
            if platform.system() == "Windows":
                subprocess.run(["explorer", directory_path], check=True)
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", directory_path], check=True)
            else:  # Linux
                subprocess.run(["xdg-open", directory_path], check=True)
            
            debug_print(f"   📂 Opened directory: {directory_path}")
            
        except Exception as e:
            debug_print(f"   ⚠️ Error opening directory: {e}")
            # Silently fail - don't show error dialog

    def _export_overview_to_ply(self) -> None:
        """
        Export overview flight waypoints to PLY file for visualization (before transformation).
        """
        try:
            if not hasattr(self, "overview_flight_waypoints") or not self.overview_flight_waypoints:
                debug_print("   ⚠️  No overview waypoints available for PLY export")
                return

            # Get project information from parsed data
            bridge_name = "Bridge"
            project_dir_base = "."

            if hasattr(self, "parsed_data") and self.parsed_data:
                project_data = self.parsed_data.get("project", {})
                bridge_name = project_data.get("bridge_name", "Bridge")
                project_dir_base = project_data.get("project_dir_base", ".")

            # Create visualization directory
            sanitized_bridge_name = self._sanitize_filename(bridge_name)
            project_dir = Path(project_dir_base) / sanitized_bridge_name
            visualization_dir = project_dir / "02_Visualization"
            visualization_dir.mkdir(parents=True, exist_ok=True)

            # Export waypoints to PLY
            filename = f"{sanitized_bridge_name}_overview_flight"
            exporter = OrbitFlightExporter(self)
            ply_path = exporter.export_waypoints_to_ply(
                self.overview_flight_waypoints,
                filename,
                visualization_dir
            )

            if ply_path:
                debug_print(f"   📄 PLY file created: {ply_path}")
            else:
                debug_print("   ❌ Failed to create PLY file")

        except Exception as e:
            debug_print(f"   ❌ PLY export failed: {e}")
            import traceback
            traceback.print_exc()

    def _export_underdeck_to_ply(self) -> None:
        """
        Export underdeck flight waypoints to PLY files for visualization (before transformation).
        Exports each individual underdeck route as a separate PLY file.
        """
        try:
            # Get project information from parsed data
            bridge_name = "Bridge"
            project_dir_base = "."

            if hasattr(self, "parsed_data") and self.parsed_data:
                project_data = self.parsed_data.get("project", {})
                bridge_name = project_data.get("bridge_name", "Bridge")
                project_dir_base = project_data.get("project_dir_base", ".")

            # Create visualization directory
            sanitized_bridge_name = self._sanitize_filename(bridge_name)
            project_dir = Path(project_dir_base) / sanitized_bridge_name
            visualization_dir = project_dir / "02_Visualization"
            visualization_dir.mkdir(parents=True, exist_ok=True)

            exporter = OrbitFlightExporter(self)
            exported_files = []

            # Export individual underdeck routes
            if hasattr(self, "underdeck_flight_routes") and self.underdeck_flight_routes:
                for i, route in enumerate(self.underdeck_flight_routes):
                    route_id = route.get('id', f'underdeck_route_{i+1}')
                    route_points = route.get('points', [])

                    if route_points:
                        # Sanitize route ID for filename
                        sanitized_route_id = self._sanitize_filename(route_id)
                        filename = f"{sanitized_bridge_name}_{sanitized_route_id}"

                        ply_path = exporter.export_waypoints_to_ply(
                            route_points,
                            filename,
                            visualization_dir
                        )
                        if ply_path:
                            exported_files.append(ply_path)
                            debug_print(f"   📄 PLY file created: {ply_path}")

            # Export individual axial underdeck routes
            if hasattr(self, "underdeck_flight_routes_Axial") and self.underdeck_flight_routes_Axial:
                for i, route in enumerate(self.underdeck_flight_routes_Axial):
                    route_id = route.get('id', f'underdeck_axial_route_{i+1}')
                    route_points = route.get('points', [])

                    if route_points:
                        # Sanitize route ID for filename
                        sanitized_route_id = self._sanitize_filename(route_id)
                        filename = f"{sanitized_bridge_name}_{sanitized_route_id}"

                        ply_path = exporter.export_waypoints_to_ply(
                            route_points,
                            filename,
                            visualization_dir
                        )
                        if ply_path:
                            exported_files.append(ply_path)
                            debug_print(f"   📄 PLY file created: {ply_path}")

            if not exported_files:
                debug_print("   ⚠️  No underdeck routes available for PLY export")
            else:
                debug_print(f"   ✅ Exported {len(exported_files)} individual underdeck PLY file(s)")

        except Exception as e:
            debug_print(f"   ❌ PLY export failed: {e}")
            import traceback
            traceback.print_exc()

    def _export_kmz_automatically(self, route_type: str) -> bool:
        """
        Automatically export KMZ files without showing dialog, using default settings.
        
        Args:
            route_type: "overview" or "underdeck" to determine which routes to export
            
        Returns:
            bool: True if KMZ export succeeded, False otherwise
        """
        try:
            debug_print(f"\n📁 Creating KMZ files for {route_type} routes...")
            
            # Get project information from parsed data
            bridge_name = "Bridge"
            project_dir_base = "."
            
            if hasattr(self, "parsed_data") and self.parsed_data:
                project_data = self.parsed_data.get("project", {})
                bridge_name = project_data.get("bridge_name", "Bridge")
                project_dir_base = project_data.get("project_dir_base", ".")
            
            # Create 03_Flightroutes directory following ORBIT structure
            sanitized_bridge_name = self._sanitize_filename(bridge_name)
            project_dir = Path(project_dir_base) / sanitized_bridge_name
            flightroutes_dir = project_dir / "03_Flightroutes"
            flightroutes_dir.mkdir(parents=True, exist_ok=True)
            
            debug_print(f"   📂 Output directory: {flightroutes_dir}")
            
            # Use default configuration (no dialog)
            default_config = {
                "height_mode": "EGM96",  # Will be overridden by parsed data if available
                "drone_type": "DJI_Mavic_3_Enterprise",
                "payload_type": "none",
                "global_speed": 2.0,
                "takeoff_security_height": 30.0,
                "min_altitude": 2.0,
                "adjust_low_altitudes": False,
                "export_combined_route": True
            }
     
            # Use centralized export handler for KMZ export
            exporter = OrbitFlightExporter(self, default_config)
            export_paths = exporter.export_all_routes(str(flightroutes_dir))
            
            if export_paths:
                files_list = ", ".join([Path(p).name for p in export_paths])
                debug_print(f"   ✅ Created {len(export_paths)} KMZ files: {files_list}")
                return True
            else:
                debug_print(f"   ❌ KMZ export failed for {route_type} routes")
                return False
                
        except Exception as e:
            debug_print(f"   ❌ KMZ export error for {route_type}: {e}")
            return False

    def _show_cross_section_template_selection_and_wait(self):
        """Show cross-section template selection interface in the existing view and wait for user selection.
        
        Returns:
            bool: True if a template was selected, False if user cancelled
        """
        try:
            if not self.cross_section_view:
                debug_print("[TEMPLATE] No cross_section_view available")
                return False
                
            # Get paths to template images
            resources_dir = Path(__file__).parent / "orbit" / "resources"
            i_girder_template = resources_dir / "crosssection_template_I-girder.png"
            box_template = resources_dir / "crosssection_template_box.png"
            
            debug_print(f"[TEMPLATE] Looking for templates in: {resources_dir}")
            debug_print(f"[TEMPLATE] I-Girder template exists: {i_girder_template.exists()}")
            debug_print(f"[TEMPLATE] Box template exists: {box_template.exists()}")
            
            # Create a scene with template selection
            scene = QGraphicsScene()
            
            # Create a widget to hold the buttons
            widget = QWidget()
            layout = QVBoxLayout(widget)
            
            # Title label
            title_label = QLabel("No cross-section image found. Select a template:")
            title_label.setAlignment(Qt.AlignCenter)
            title_label.setStyleSheet("font-size: 14px; font-weight: bold; margin: 10px;")
            layout.addWidget(title_label)
            
            # Button layout
            button_layout = QHBoxLayout()
            
            # Create a flag to track if a template was selected
            self._template_selection_result = None
            
            # I-Girder button
            if i_girder_template.exists():
                i_girder_btn = QPushButton("I-Girder Template")
                i_girder_btn.setFixedSize(150, 40)
                i_girder_btn.clicked.connect(lambda: self._select_template_and_continue(i_girder_template))
                button_layout.addWidget(i_girder_btn)
            
            # Box girder button  
            if box_template.exists():
                box_btn = QPushButton("Box Girder Template")
                box_btn.setFixedSize(150, 40)
                box_btn.clicked.connect(lambda: self._select_template_and_continue(box_template))
                button_layout.addWidget(box_btn)
            
            layout.addLayout(button_layout)
            
            # Cancel button
            cancel_btn = QPushButton("Cancel")
            cancel_btn.setFixedSize(100, 30)
            cancel_btn.clicked.connect(lambda: self._cancel_template_selection())
            layout.addWidget(cancel_btn, alignment=Qt.AlignCenter)
            
            # Add some spacing
            layout.addStretch()
            
            widget.setFixedSize(400, 150)
            
            # Add widget to scene
            scene.addWidget(widget)
            self.cross_section_view.setScene(scene)
            self.cross_section_view.fitInView(scene.itemsBoundingRect(), Qt.KeepAspectRatio)
            
            debug_print("[TEMPLATE] Template selection interface displayed in existing view")
            
            # Show a message to guide the user
            QMessageBox.information(
                self.ui,
                "Select Template",
                "Please select a cross-section template from the display above.\n\n"
                "Click 'I-Girder Template' or 'Box Girder Template' to continue,\n"
                "or 'Cancel' to abort the project confirmation."
            )
            
            # Wait for user selection (this will be set by the button callbacks)
            # We'll check the result in the calling method
            return True
            
        except Exception as e:
            debug_print(f"[TEMPLATE] Error showing template selection: {e}")
            return False
    


    def _select_template_and_continue(self, template_path):
        """Select a template and mark selection as successful."""
        try:
            debug_print(f"[TEMPLATE] Selected template: {template_path.name}")
            
            # Display the selected template directly
            self._display_cross_section_template(template_path)
            
            # Mark selection as successful
            self._template_selection_result = True
            
            # Show confirmation message
            QMessageBox.information(
                self.ui,
                "Template Selected",
                f"Cross-section template '{template_path.stem}' has been selected and loaded.\n\n"
                "You can now continue with project confirmation."
            )
            
        except Exception as e:
            debug_print(f"[TEMPLATE] Error selecting template: {e}")
            self._template_selection_result = False
    
    def _cancel_template_selection(self):
        """Cancel template selection."""
        debug_print("[TEMPLATE] Template selection cancelled by user")
        self._template_selection_result = False
        
        # Clear the cross-section view
        if self.cross_section_view:
            self.cross_section_view.setScene(None)
    
    def _show_cross_section_template_selection(self, show_popup=True):
        """Show cross-section template selection interface.
        
        Args:
            show_popup: Whether to show popup messages (False for silent template selection)
        """
        try:
            # Ensure data loader is initialized before showing template selection
            if not getattr(self, 'data_loader', None):
                debug_print("[TEMPLATE] Data loader not initialized - initializing now")
                self._initialize_data_loader_safely()
            
            if not self.cross_section_view:
                debug_print("[TEMPLATE] No cross_section_view available")
                return False
                
            # Get paths to template images
            resources_dir = Path(__file__).parent / "orbit" / "resources"
            i_girder_template = resources_dir / "crosssection_template_I-girder.png"
            box_template = resources_dir / "crosssection_template_box.png"
            
            debug_print(f"[TEMPLATE] Looking for templates in: {resources_dir}")
            debug_print(f"[TEMPLATE] I-Girder template exists: {i_girder_template.exists()}")
            debug_print(f"[TEMPLATE] Box template exists: {box_template.exists()}")
            
            # Create a scene with template selection
            scene = QGraphicsScene()
            
            # Create a widget to hold the buttons
            widget = QWidget()
            layout = QVBoxLayout(widget)
            
            # Title label
            title_label = QLabel("No cross-section image found. Select a template:")
            title_label.setAlignment(Qt.AlignCenter)
            title_label.setStyleSheet("font-size: 14px; font-weight: bold; margin: 10px;")
            layout.addWidget(title_label)
            
            # Button layout
            button_layout = QHBoxLayout()
            
            # I-Girder button
            if i_girder_template.exists():
                i_girder_btn = QPushButton("I-Girder Template")
                i_girder_btn.setFixedSize(150, 40)
                i_girder_btn.clicked.connect(lambda: self._select_cross_section_template(i_girder_template, show_popup))
                button_layout.addWidget(i_girder_btn)
            
            # Box girder button  
            if box_template.exists():
                box_btn = QPushButton("Box Girder Template")
                box_btn.setFixedSize(150, 40)
                box_btn.clicked.connect(lambda: self._select_cross_section_template(box_template, show_popup))
                button_layout.addWidget(box_btn)
            
            layout.addLayout(button_layout)
            
            # Add some spacing
            layout.addStretch()
            
            widget.setFixedSize(400, 150)
            
            # Add widget to scene
            scene.addWidget(widget)
            self.cross_section_view.setScene(scene)
            self.cross_section_view.fitInView(scene.itemsBoundingRect(), Qt.KeepAspectRatio)
            
            debug_print("[TEMPLATE] Template selection interface displayed")
            return True
            
        except Exception as e:
            debug_print(f"[TEMPLATE] Error showing template selection: {e}")
            return False

    def _select_cross_section_template(self, template_path: Path, show_popup=True):
        """Handle cross-section template selection with comprehensive error handling.

        This method is designed to be crash-resistant when bridge_name is missing or
        when template files are corrupted/inaccessible.

        Args:
            template_path: Path to the selected template
            show_popup: Whether to show popup messages (False for silent selection)
        """
        lifecycle_tracker.log_operation("Template selection started", f"Path: {template_path.name}")

        debug_print(f"[TEMPLATE] ======= STARTING TEMPLATE SELECTION =======")
        debug_print(f"[TEMPLATE] Template path: {template_path}")
        debug_print(f"[TEMPLATE] Show popup: {show_popup}")

        try:
            debug_print(f"[TEMPLATE] [STEP 1] Validating template path...")

            # Validate template path exists and is readable
            if not template_path.exists():
                debug_print(f"[TEMPLATE] [ERROR] Template file does not exist: {template_path}")
                QMessageBox.warning(self.ui, "Template Not Found",
                                  f"The selected template file was not found:\n{template_path}")
                return

            if not template_path.is_file():
                debug_print(f"[TEMPLATE] [ERROR] Template path is not a file: {template_path}")
                QMessageBox.warning(self.ui, "Invalid Template",
                                  f"The selected template path is not a valid file:\n{template_path}")
                return

            debug_print(f"[TEMPLATE] [STEP 1] Template validation passed")

            debug_print(f"[TEMPLATE] [STEP 2] Displaying template...")
            # Display the selected template directly
            self._display_cross_section_template(template_path)
            debug_print(f"[TEMPLATE] [STEP 2] Template display completed")


            debug_print(f"[TEMPLATE] ======= TEMPLATE SELECTION COMPLETED SUCCESSFULLY =======")
            lifecycle_tracker.log_operation("Template selection completed", f"Path: {template_path.name}")

        except Exception as e:
            debug_print(f"[TEMPLATE] [CRITICAL ERROR] Exception in template selection: {e}")
            debug_print(f"[TEMPLATE] [CRITICAL ERROR] Template path: {template_path}")
            debug_print(f"[TEMPLATE] [CRITICAL ERROR] Show popup: {show_popup}")

            import traceback
            debug_print(f"[TEMPLATE] [CRITICAL ERROR] Full traceback:")
            traceback.print_exc()

            # Log the error to lifecycle tracker
            lifecycle_tracker.log_shutdown(f"Template selection error: {e}", "_select_cross_section_template")

            # Show user-friendly error message
            QMessageBox.critical(self.ui, "Template Selection Error",
                               f"A critical error occurred while selecting the template:\n\n"
                               f"Error: {str(e)}\n\n"
                               f"Template: {template_path.name}\n\n"
                               f"Please check the debug output for more details.")

            debug_print(f"[TEMPLATE] ======= TEMPLATE SELECTION FAILED =======")
    
    def _display_cross_section_template(self, template_path: Path):
        """Display a cross-section template in the graphics view and perform analysis."""
        lifecycle_tracker.log_operation("Template display started", f"Path: {template_path.name}")

        debug_print(f"[DISPLAY] ======= STARTING TEMPLATE DISPLAY =======")
        debug_print(f"[DISPLAY] Template path: {template_path}")

        # Store template path for error handling scope
        template_path_for_error = template_path

        try:
            debug_print(f"[DISPLAY] [STEP 1] Setting cross-section path...")
            # Store the current cross-section path
            self.current_crosssection_path = str(template_path)
            debug_print(f"[DISPLAY] [STEP 1] Stored cross-section path: {self.current_crosssection_path}")

            debug_print(f"[DISPLAY] [STEP 2] Loading image with OpenCV...")
            # ------------------------------------------------------------------
            # Always read the template through OpenCV -> RGB so the green scale
            # bar is preserved and detectable by `process_crosssection_image`.
            # We save a temporary RGB-corrected copy next to the original file
            # and feed that to the analysis routine.  The user never sees the
            # temp copy.
            # ------------------------------------------------------------------

            bgr_img = cv2.imread(str(template_path))
            if bgr_img is None:
                debug_print("[DISPLAY] [STEP 2] cv2.imread failed – falling back to QPixmap")
                pixmap = QPixmap(str(template_path))

                # Check if QPixmap loaded successfully
                if pixmap.isNull():
                    debug_print("[DISPLAY] [ERROR] QPixmap also failed to load template")
                    QMessageBox.warning(self.ui, "Template Load Error",
                                      f"Could not load the template image:\n{template_path}\n\n"
                                      f"The file may be corrupted or in an unsupported format.")
                    return

                debug_print("[DISPLAY] [STEP 2] QPixmap fallback successful")
                temp_rgb_path = template_path  # analysis may still fail
            else:
                debug_print(f"[DISPLAY] [STEP 2] OpenCV loaded image successfully: {bgr_img.shape}")
                try:
                    debug_print(f"[DISPLAY] [STEP 3] Converting BGR to RGB...")
                    rgb_img = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2RGB)

                    debug_print(f"[DISPLAY] [STEP 4] Creating temporary RGB file...")
                    # Write to a temp file (PNG keeps colours)
                    tmp_dir = Path(tempfile.gettempdir())
                    temp_rgb_path = tmp_dir / (template_path.stem + "_rgb.png")
                    success = cv2.imwrite(str(temp_rgb_path), cv2.cvtColor(rgb_img, cv2.COLOR_RGB2BGR))

                    if not success:
                        debug_print("[DISPLAY] [ERROR] Failed to write temporary RGB file")
                        QMessageBox.warning(self.ui, "Template Processing Error",
                                          f"Could not process the template image for analysis:\n{template_path}")
                        return

                    debug_print(f"[DISPLAY] [STEP 4] Created temporary file: {temp_rgb_path}")
                    pixmap = QPixmap(str(temp_rgb_path))

                    # Check if pixmap loaded successfully
                    if pixmap.isNull():
                        debug_print("[DISPLAY] [ERROR] Processed pixmap is null")
                        QMessageBox.warning(self.ui, "Template Display Error",
                                          f"Could not display the processed template:\n{template_path}")
                        return

                    debug_print(f"[DISPLAY] [STEP 4] Pixmap created successfully")
                    # Use the RGB-safe copy for later analysis
                    template_path = temp_rgb_path
                except Exception as cv_error:
                    debug_print(f"[DISPLAY] [ERROR] OpenCV processing error: {cv_error}")
                    QMessageBox.warning(self.ui, "Template Processing Error",
                                      f"Error processing template image:\n{str(cv_error)}")
                    return
 
            debug_print(f"[DISPLAY] [STEP 5] Checking cross-section view availability...")
            # Ensure cross_section_view exists before using it
            if not hasattr(self, 'cross_section_view') or self.cross_section_view is None:
                debug_print("[DISPLAY] [ERROR] Cross section view not available")
                QMessageBox.warning(self.ui, "Display Error",
                                  "Cross section display is not available. The template was processed but cannot be displayed.")
                return

            debug_print(f"[DISPLAY] [STEP 5] Cross-section view available")

            debug_print(f"[DISPLAY] [STEP 6] Creating graphics scene...")
            scene = QGraphicsScene()
            scene.addPixmap(pixmap)
            self.cross_section_view.setScene(scene)
            self.cross_section_view.fitInView(scene.itemsBoundingRect(), Qt.KeepAspectRatio)

            debug_print(f"[DISPLAY] [STEP 6] Graphics scene created and displayed")

            # Check if there's a pending processed image to display
            debug_print(f"[DISPLAY] [STEP 7] Checking for pending processed images...")
            if hasattr(self.data_loader, '_display_pending_processed_image'):
                debug_print(f"[DISPLAY] [STEP 7] Displaying pending processed image...")
                self.data_loader._display_pending_processed_image()
                debug_print(f"[DISPLAY] [STEP 7] Pending processed image displayed")
            else:
                debug_print(f"[DISPLAY] [STEP 7] No pending processed images to display")

            debug_print(f"[DISPLAY] ======= TEMPLATE DISPLAY COMPLETED SUCCESSFULLY =======")
            lifecycle_tracker.log_operation("Template display completed", f"Path: {template_path.name}")

            # Delegate to the BridgeDataLoader implementation
            debug_print(f"[DISPLAY] [STEP 8] Delegating to BridgeDataLoader...")
            if not self.data_loader:
                debug_print(f"[DISPLAY] [STEP 8] Creating new BridgeDataLoader...")
                self.data_loader = BridgeDataLoader(
                    self.ui,
                    self.project_text_edit,
                    self.flight_routes_text_edit,
                    self.cross_section_view
                )
            self.data_loader._perform_cross_section_analysis(Path(template_path))
            # Re-use its results
            self.processed_crosssection_image = getattr(self.data_loader,
                                                        "processed_crosssection_image",
                                                        None)
            self.crosssection_transformed_points = getattr(self.data_loader,
                                                        "crosssection_transformed_points",
                                                        None)
            
            # Ensure the data loader's path is synchronized with the main app's path
            if hasattr(self.data_loader, 'current_crosssection_path'):
                self.data_loader.current_crosssection_path = self.current_crosssection_path
                debug_print(f"[TEMPLATE] Synchronized data loader's cross-section path: {self.data_loader.current_crosssection_path}")
            
        except Exception as e:
            debug_print(f"[TEMPLATE] Error displaying template: {e}")
    
    
    def _parse_project_data_for_templates(self):
        """Return already parsed project dict for template analysis."""
        self._update_parsed_data()
        return self.parsed_data.get("project", {})
    
    def _update_cross_section_display_with_processed_image(self, processed_image):
        """Update the cross-section display with the processed image."""
        try:
            
            
            # Convert OpenCV image to QPixmap and update display
            height, width, channel = processed_image.shape
            bytes_per_line = 3 * width
            q_image = QImage(processed_image.data, width, height, bytes_per_line, QImage.Format_RGB888).rgbSwapped()
            processed_pixmap = QPixmap.fromImage(q_image)
            
            scene = QGraphicsScene()
            scene.addPixmap(processed_pixmap)
            self.cross_section_view.setScene(scene)
            self.cross_section_view.fitInView(scene.itemsBoundingRect(), Qt.KeepAspectRatio)
            
            debug_print("[TEMPLATE] Updated display with processed template image")
            
        except Exception as e:
            debug_print(f"[DISPLAY] [CRITICAL ERROR] Exception in template display: {e}")

            # Get template info safely (avoid linter issues with variable scope)
            template_name = "<unknown template>"
            debug_print(f"[DISPLAY] [CRITICAL ERROR] Template path: <unknown - check function context>")

            import traceback
            debug_print(f"[DISPLAY] [CRITICAL ERROR] Full traceback:")
            traceback.print_exc()

            # Show user-friendly error message
            QMessageBox.critical(self.ui, "Template Display Error",
                               f"A critical error occurred while displaying the template:\n\n"
                               f"Error: {str(e)}\n\n"
                               f"Template: {template_name}\n\n"
                               f"The template may not display correctly.")

            debug_print(f"[DISPLAY] ======= TEMPLATE DISPLAY FAILED =======")

    def _copy_template_to_project_directory(self, template_path: Path):
        """Copy the selected template to the project's input directory."""
        try:
            # If no project text, just use the template directly.
            if not getattr(self, "project_text_edit", None):
                self.current_crosssection_path = str(template_path)
                return

            text_content = self.project_text_edit.toPlainText().strip()
            if not text_content:
                self.current_crosssection_path = str(template_path)
                return

            # Parse project data
            self._update_parsed_data()
            project_cfg = self.parsed_data.get("project", {})
            bridge_name = project_cfg.get("bridge_name") or "DefaultBridge"
            import_dir = project_cfg.get("import_dir")
            project_dir_base = project_cfg.get("project_dir_base")

            # Determine target directory
            if import_dir and import_dir != "." and Path(import_dir).exists():
                target_dir = Path(import_dir)
            elif project_dir_base:
                target_dir = Path(project_dir_base) / bridge_name / "01_Input"
            else:
                target_dir = Path(".") / bridge_name

            target_dir.mkdir(parents=True, exist_ok=True)

            # Destination path (use sanitized name)
            sanitized_bridge_name = self._sanitize_filename(bridge_name)
            dest_path = target_dir / f"{sanitized_bridge_name}_crosssection{template_path.suffix}"

            # Copy
            shutil.copy2(template_path, dest_path)
            self.current_crosssection_path = str(dest_path)

            # Persist import_dir if it wasn't set
            if not import_dir or import_dir == ".":
                self._update_import_dir_in_text(str(target_dir))

            # Minimal success print
            debug_print(f"[COPY] Template copied to: {dest_path}")

        except Exception as e:
            # On any failure, fall back to original template and print the error
            self.current_crosssection_path = str(template_path)
            print(f"[COPY][ERROR] Template copy failed: {e}")
    
    def _update_import_dir_in_text(self, new_import_dir: str):
        """Update the import_dir in the project text edit."""
        try:
            if not self.project_text_edit:
                return
                
            text_content = self.project_text_edit.toPlainText()
            lines = text_content.split('\n')
            
            # Look for existing import_dir line
            import_dir_updated = False
            for i, line in enumerate(lines):
                if line.strip().startswith('import_dir'):
                    lines[i] = f'import_dir = "{new_import_dir}"'
                    import_dir_updated = True
                    break
            
            # If no import_dir line found, add it
            if not import_dir_updated:
                # Find a good place to add it (after bridge_name if it exists)
                insert_index = len(lines)
                for i, line in enumerate(lines):
                    if line.strip().startswith('bridge_name'):
                        insert_index = i + 1
                        break
                
                lines.insert(insert_index, f'import_dir = "{new_import_dir}"')
            
            # Update the text edit
            self.project_text_edit.setPlainText('\n'.join(lines))
            debug_print(f"[TEMPLATE] Updated project text with import_dir: {new_import_dir}")
            
        except Exception as e:
            debug_print(f"[TEMPLATE] Error updating import_dir in text: {e}")
    
    def _check_cross_section_availability(self):
        """Check if cross-section data is available (either from file or template)."""
        # Check main application's cross-section data
        main_app_available = (hasattr(self, 'crosssection_transformed_points') and 
                             self.crosssection_transformed_points is not None and 
                             len(self.crosssection_transformed_points) > 0)
        
        # Also check data loader's cross-section data (for templates that were just copied)
        data_loader_available = False
        if hasattr(self, 'data_loader') and self.data_loader:
            data_loader_available = (hasattr(self.data_loader, 'crosssection_transformed_points') and 
                                   self.data_loader.crosssection_transformed_points is not None and 
                                   len(self.data_loader.crosssection_transformed_points) > 0)
        
        # Return True if either source has cross-section data
        is_available = main_app_available or data_loader_available
        
        if is_available:
            if main_app_available:
                debug_print(f"[DEBUG] Cross-section data available in main app: {len(self.crosssection_transformed_points)} points")
            if data_loader_available:
                debug_print(f"[DEBUG] Cross-section data available in data loader: {len(self.data_loader.crosssection_transformed_points)} points")
        else:
            debug_print("[DEBUG] No cross-section data available in either main app or data loader")
        
        return is_available

    # ------------------------------------------------------------------
    # Unified data parsing helpers
    # ------------------------------------------------------------------

    def _update_parsed_data(self):
        """Re-parse both QTextEdit widgets and store result in self.parsed_data."""
        try:
            # Get text from both text boxes
            tab0 = self.ui.tab0_textEdit1_Photo.toPlainText() if hasattr(self.ui, 'tab0_textEdit1_Photo') else ""
            tab3 = self.ui.tab3_textEdit.toPlainText() if hasattr(self.ui, 'tab3_textEdit') else ""
            
            self.parsed_data = parse_text_boxes(tab0, tab3)

            # Debug: show keys parsed
            proj_keys = list(self.parsed_data.get("project", {}).keys())
            fr_keys   = list(self.parsed_data.get("flight_routes", {}).keys())
            debug_print(f"[PARSE] Updated parsed_data: project keys={proj_keys[:5]}..., flight_route keys={fr_keys[:5]}...")
        except Exception as e:
            error_debug_print(f"[PARSE] Failed to parse text boxes: {e}")

    def _normalize_waypoints_to_project(self, waypoints):
        """
        Returns a list of [x, y, z] in project/local-metric CRS for heterogeneous waypoint inputs.
        """
        out = []

        def wgs84_to_proj(lat, lon, z=0.0):
            if getattr(self, "_last_transform_func", None):
                X, Y, _ = self._last_transform_func(float(lat), float(lon), float(z))
                return float(X), float(Y), float(z)
            if getattr(self, "current_context", None):
                X, Y, _ = self.current_context.wgs84_to_project(float(lon), float(lat), float(z))  # (lon,lat,z)
                return float(X), float(Y), float(z)
            # identity fallback (only used if no context)
            return float(lon), float(lat), float(z)

        for wp in waypoints:
            try:
                # Dict variants
                if isinstance(wp, dict):
                    if "x" in wp and "y" in wp:
                        x = float(wp["x"]); y = float(wp["y"]); z = float(wp.get("z", wp.get("alt", 0.0)))
                        out.append([x, y, z]); continue
                    if "lat" in wp and ("lon" in wp or "lng" in wp):
                        lat = float(wp["lat"]); lon = float(wp.get("lon", wp.get("lng")))
                        z = float(wp.get("z", wp.get("alt", 0.0)))
                        x, y, z = wgs84_to_proj(lat, lon, z)
                        out.append([x, y, z]); continue

                # Sequence variants
                seq = list(wp)
                if len(seq) >= 3:
                    a, b, c = float(seq[0]), float(seq[1]), float(seq[2])
                    # Does it look like (lat,lon, z)?
                    if (-90.0 <= a <= 90.0) and (-180.0 <= b <= 180.0):
                        x, y, z = wgs84_to_proj(a, b, c)
                        out.append([x, y, z]); continue
                    # Or (lon,lat, z)?
                    if (-90.0 <= b <= 90.0) and (-180.0 <= a <= 180.0):
                        x, y, z = wgs84_to_proj(b, a, c)
                        out.append([x, y, z]); continue
                    # Otherwise assume already project
                    out.append([a, b, c]); continue

                if len(seq) == 2:
                    a, b = float(seq[0]), float(seq[1])
                    if (-90.0 <= a <= 90.0) and (-180.0 <= b <= 180.0):
                        x, y, z = wgs84_to_proj(a, b, 0.0)
                        out.append([x, y, z]); continue
                    if (-90.0 <= b <= 90.0) and (-180.0 <= a <= 180.0):
                        x, y, z = wgs84_to_proj(b, a, 0.0)
                        out.append([x, y, z]); continue
                    out.append([a, b, 0.0]); continue

            except Exception as ee:
                debug_print(f"[WAYPOINTS] Skipped invalid waypoint {wp}: {ee}")

        return out





    def _get_route_for_validation(self, route_type: str):
        """
        Returns best-available FINAL route for validation, normalized to project CRS [x,y,z].
        Tries several attribute names to find the post-processed route.
        """
        # Candidate attribute names, ordered from "most final" to "least final"
        if route_type == "overview":
            candidates = [
                "overview_flight_waypoints_project",
                "overview_flight_waypoints_final",
                "overview_flight_waypoints_processed",
                "overview_flight_waypoints",
            ]
        elif route_type == "underdeck":
            candidates = [
                "underdeck_flight_waypoints_project",
                "underdeck_flight_waypoints_final",
                "underdeck_flight_waypoints_processed",
                "underdeck_flight_waypoints",
            ]
        else:
            candidates = [route_type]  # allow custom

        picked = None
        for name in candidates:
            if hasattr(self, name):
                val = getattr(self, name)
                if val:
                    picked = val
                    break

        # If nothing found, return empty
        if not picked:
            return []

        # Normalize to project CRS
        if not hasattr(self, "_normalize_waypoints_to_project"):
            debug_print("[FINAL_SAFETY_VALIDATION] Missing _normalize_waypoints_to_project; cannot normalize")
            return picked

        normalized = self._normalize_waypoints_to_project(picked)
        return normalized

    def _should_perform_safety_check(self, route_type, section_index=0):
        """Check if safety validation should be performed based on safety check parameters."""
        try:
            if not hasattr(self, 'parsed_data') or not self.parsed_data:
                return False
                
            flight_routes = self.parsed_data.get("flight_routes", {})
            
            if route_type == "overview":
                # Check safety_check_photo parameter
                safety_check_photo = flight_routes.get("safety_check_photo", 0)
                return safety_check_photo == 1
                
            elif route_type == "underdeck":
                # Check safety_check_underdeck parameter
                safety_check_underdeck = flight_routes.get("safety_check_underdeck", [])
                if section_index < len(safety_check_underdeck):
                    return safety_check_underdeck[section_index] == 1
                else:
                    return False  # Default to 0 if not enough values
                    
            elif route_type == "underdeck_axial":
                # Check safety_check_underdeck_axial parameter
                safety_check_underdeck_axial = flight_routes.get("safety_check_underdeck_axial", [])
                if section_index < len(safety_check_underdeck_axial):
                    return safety_check_underdeck_axial[section_index] == 1
                else:
                    return False  # Default to 0 if not enough values
            
            return False  # Default to False for unknown route types
            
        except Exception as e:
            debug_print(f"Error checking safety check parameters: {e}")
            return False

    def _has_active_safety_zones(self):
        """Check if there are any active safety zones defined."""
        try:
            # Check current_safety_zones first (primary source - zones drawn on map)
            if hasattr(self, 'current_safety_zones') and self.current_safety_zones:
                return len(self.current_safety_zones) > 0

            # Fallback: check parsed_data for safety_zones_coords (legacy support)
            if hasattr(self, 'parsed_data') and self.parsed_data:
                flight_routes = self.parsed_data.get("flight_routes", {})
                safety_zones_coords = flight_routes.get("safety_zones_coords", [])
                if len(safety_zones_coords) > 0:
                    print("[#] Found active safety zones in parsed_data")
                    return True
                
            print("[#] No active safety zones found")
            return False

        except Exception as e:
            debug_print(f"Error checking for active safety zones: {e}")
            return False

    def _analyze_unsafe_segments(self, unsafe_points, safety_zones, safety_clearance):
        """Analyze unsafe points to group them into meaningful segments by safety zone."""
        try:
            # Group unsafe points by safety zone
            zone_groups = {}
            
            for unsafe in unsafe_points:
                zone_idx = unsafe['zone_idx'] - 1  # Convert back to 0-based index
                if zone_idx not in zone_groups:
                    zone_groups[zone_idx] = []
                zone_groups[zone_idx].append(unsafe)
            
            # Create segment information for each zone
            unsafe_segments = []
            
            for zone_idx, points in zone_groups.items():
                if zone_idx < len(safety_clearance):
                    z_min, z_max = safety_clearance[zone_idx]
                else:
                    z_min, z_max = None, None
                
                segment_info = {
                    'zone_idx': zone_idx + 1,  # Convert back to 1-based for display
                    'z_min': z_min,
                    'z_max': z_max,
                    'unsafe_count': len(points),
                    'points': points
                }
                
                unsafe_segments.append(segment_info)
            
            # Sort by zone index for consistent display
            unsafe_segments.sort(key=lambda x: x['zone_idx'])
            
            return unsafe_segments
            
        except Exception as e:
            debug_print(f"Error analyzing unsafe segments: {e}")
            return []

    def _is_point_in_polygon_with_threshold(self, point, polygon, threshold=0.2):
        """Point-in-polygon test with threshold - considers points within threshold distance as 'outside'."""
        try:
            x, y = point[0], point[1]
            n = len(polygon)
            if n < 3:
                return False
            
            # First check if point is inside the polygon
            inside = False
            j = n - 1
            
            for i in range(n):
                xi, yi = polygon[i][0], polygon[i][1]
                xj, yj = polygon[j][0], polygon[j][1]
                
                if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
                    inside = not inside
                j = i
            
            if not inside:
                return False  # Point is outside polygon
            
            # If point is inside, check if it's too close to the boundary
            min_distance_to_boundary = float('inf')
            
            for i in range(n):
                xi, yi = polygon[i][0], polygon[i][1]
                xj, yj = polygon[j][0], polygon[j][1]
                
                # Calculate distance to line segment
                line_length = ((xj - xi) ** 2 + (yj - yi) ** 2) ** 0.5
                if line_length == 0:
                    continue
                
                # Calculate projection of point onto line
                t = max(0, min(1, ((x - xi) * (xj - xi) + (y - yi) * (yj - yi)) / (line_length ** 2)))
                
                # Closest point on line segment
                closest_x = xi + t * (xj - xi)
                closest_y = yi + t * (yj - yi)
                
                # Distance from point to closest point on line
                distance = ((x - closest_x) ** 2 + (y - closest_y) ** 2) ** 0.5
                min_distance_to_boundary = min(min_distance_to_boundary, distance)
                
                j = i
            
            # If point is within threshold distance of boundary, consider it "outside"
            return min_distance_to_boundary > threshold
            
        except Exception as e:
            debug_print(f"Error in point-in-polygon test with threshold: {e}")
            return False

    def _is_point_in_polygon_simple(self, point, polygon):
        """Simple point-in-polygon test using ray casting algorithm."""
        try:
            x, y = point[0], point[1]
            n = len(polygon)
            if n < 3:
                return False
            
            inside = False
            j = n - 1
            
            for i in range(n):
                xi, yi = polygon[i][0], polygon[i][1]
                xj, yj = polygon[j][0], polygon[j][1]
                
                if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
                    inside = not inside
                j = i
            
            return inside
            
        except Exception as e:
            debug_print(f"Error in point-in-polygon test: {e}")
            return False

    def _sample_route_for_validation(self, waypoints, interval=0.1):
        """
        Samples a 3D polyline at fixed interval (meters).
        Input 'waypoints' should be [x,y,z] in project CRS (use _normalize_waypoints_to_project beforehand).
        """
        import numpy as np

        pts = []
        for w in waypoints:
            try:
                x, y = float(w[0]), float(w[1])
                z = float(w[2]) if len(w) > 2 else 0.0
                pts.append([x, y, z])
            except Exception:
                continue

        if len(pts) < 2:
            return pts

        pts = np.asarray(pts, dtype=float)
        seg = np.diff(pts[:, :3], axis=0)
        seg_len = np.linalg.norm(seg, axis=1)
        total = float(np.nansum(seg_len))
        if total <= 0:
            return pts.tolist()

        # desired stations (including end)
        n = max(2, int(np.floor(total / float(interval))) + 1)
        stations = np.linspace(0.0, total, n)

        # cumulative along distances
        s = np.concatenate([[0.0], np.cumsum(seg_len)])

        # interpolate per coordinate
        out = []
        for st in stations:
            # find segment
            idx = np.searchsorted(s, st, side="right") - 1
            idx = max(0, min(idx, len(seg_len) - 1))
            # local t
            denom = seg_len[idx] if seg_len[idx] > 0 else 1.0
            t = (st - s[idx]) / denom
            p0 = pts[idx]
            p1 = pts[idx + 1]
            p = (1.0 - t) * p0 + t * p1
            out.append([float(p[0]), float(p[1]), float(p[2])])

        return out
    
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize a filename by removing or replacing invalid characters.
        
        Args:
            filename: The original filename to sanitize
            
        Returns:
            A sanitized filename safe for use on Windows and other operating systems
        """

        
        if not filename:
            return "DefaultBridge"
        
        # Define invalid characters for Windows filesystems
        invalid_chars = '<>:"|?*'
        
        # Replace invalid characters with underscores
        sanitized = filename
        for char in invalid_chars:
            sanitized = sanitized.replace(char, '_')
        
        # Replace forward and backslashes with underscores (path separators)
        sanitized = sanitized.replace('/', '_').replace('\\', '_')
        
        # Remove or replace other problematic characters
        sanitized = re.sub(r'[^\w\s\-_.]', '_', sanitized)  # Keep alphanumeric, spaces, hyphens, underscores, dots
        
        # Handle Windows reserved names
        reserved_names = ['CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 
                         'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 
                         'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9']
        
        if sanitized.upper() in reserved_names:
            sanitized = f"{sanitized}_bridge"
        
        # Trim whitespace and ensure it's not empty
        sanitized = sanitized.strip()
        if not sanitized:
            sanitized = "DefaultBridge"
        
        # Limit length to avoid filesystem issues (most filesystems support 255 chars)
        if len(sanitized) > 200:  # Leave room for suffix
            sanitized = sanitized[:200].rstrip()
        
        return sanitized

    def _update_waypoints_display(self):
        """Update the waypoints text box with current overview flight waypoint count."""
        if not hasattr(self, 'waypoints_text_box') or not self.waypoints_text_box:
            debug_print("⚠️ Waypoints text box not available for display update")
            return
            
        # Get the current overview flight waypoints count
        waypoint_count = 0
        if hasattr(self, 'overview_flight_waypoints') and self.overview_flight_waypoints:
            waypoint_count = len(self.overview_flight_waypoints)
        
        # Get current angle threshold
        angle_threshold = self.get_min_angle_change()
        
        # Create the display text
        display_text = f"""<html>
<body style="font-family: Arial, sans-serif; font-size: 10pt; color: #d6d6d6;">
<p style="margin: 5px 0;"><strong>Overview Flight Waypoints</strong></p>
<p style="margin: 5px 0; color: #00ff00;">{waypoint_count} waypoints</p>
<p style="margin: 3px 0; font-size: 9pt; color: #cccccc;">Angle threshold: {angle_threshold}°</p>
<hr style="margin: 8px 0; border: 1px solid #444;">
<p style="margin: 5px 0; font-size: 9pt;"><strong>Visualization Controls:</strong></p>
<p style="margin: 2px 0; font-size: 8pt;">W - Wireframe</p>
<p style="margin: 2px 0; font-size: 8pt;">S - Faces</p>
<p style="margin: 2px 0; font-size: 8pt;">V - View all</p>
<p style="margin: 2px 0; font-size: 8pt;">F - Focus</p>
<p style="margin: 2px 0; font-size: 8pt;">Shift - Pan</p>
<p style="margin: 2px 0; font-size: 8pt;">Ctrl - Rotate</p>
</body>
</html>"""
        
        self.waypoints_text_box.setHtml(display_text)

    def clear_overview_flight_waypoints(self):
        """Clear overview flight waypoints and update the display."""
        if hasattr(self, 'overview_flight_waypoints'):
            self.overview_flight_waypoints = []
            debug_print("🗑️ Cleared overview flight waypoints")
            self._update_waypoints_display()

    def _setup_waypoints_controls(self):
        """Setup the waypoints slider and line edit controls."""
        if not self.waypoints_slider or not self.waypoints_line_edit:
            return
            
        # Set initial values
        self.waypoints_slider.setValue(15)  # Default 15 degrees
        self.waypoints_line_edit.setText("15°")
        
        # Connect slider to line edit
        self.waypoints_slider.valueChanged.connect(self._on_waypoints_slider_changed)
        
        # Connect line edit to slider (when user types)
        self.waypoints_line_edit.returnPressed.connect(self._on_waypoints_line_edit_changed)
        
        debug_print("✅ Waypoints controls setup complete")

    def _on_waypoints_slider_changed(self, value):
        """Handle waypoints slider value change."""
        self.waypoints_line_edit.setText(f"{value}°")
        debug_print(f"🔄 Waypoints slider changed to {value}°")
        
        # Automatically update flight routes if they exist
        if hasattr(self, 'overview_flight_waypoints') and self.overview_flight_waypoints:
            debug_print("🔄 Auto-updating flight routes with new angle threshold...")
            self.update_flight_routes()

    def _on_waypoints_line_edit_changed(self):
        """Handle waypoints line edit value change."""
        try:
            text = self.waypoints_line_edit.text().replace('°', '').strip()
            value = int(text)
            
            # Validate range
            if value < 5:
                value = 5
            elif value > 30:
                value = 30
                
            # Update slider and line edit
            self.waypoints_slider.setValue(value)
            self.waypoints_line_edit.setText(f"{value}°")
            
            debug_print(f"🔄 Waypoints line edit changed to {value}°")
            
            # Automatically update flight routes if they exist
            if hasattr(self, 'overview_flight_waypoints') and self.overview_flight_waypoints:
                debug_print("🔄 Auto-updating flight routes with new angle threshold...")
                self.update_flight_routes()
                
        except ValueError:
            # Invalid input, revert to slider value
            slider_value = self.waypoints_slider.value()
            self.waypoints_line_edit.setText(f"{slider_value}°")
            debug_print(f"⚠️ Invalid input, reverted to {slider_value}°")

    def get_min_angle_change(self):
        """Get the current min_angle_change value from the slider."""
        if self.waypoints_slider:
            return self.waypoints_slider.value()
        return 15  # Default fallback

    def _setup_flight_route_adjustment_controls(self):
        """Setup the flight route adjustment controls (combo box and sliders)."""
        try:
            # Get references to the adjustment widgets
            self.combo_box_flight_routes_transform = self.ui.findChild(QComboBox, "comboBox_FlightRoutes_transform")
            self.slider_offset_x = self.ui.findChild(QSlider, "slider_offset_X")
            self.slider_offset_y = self.ui.findChild(QSlider, "slider_offset_Y")
            self.slider_offset_z = self.ui.findChild(QSlider, "slider_offset_Z")
            self.text_slider_offset_x = self.ui.findChild(QLineEdit, "text_slider_offset_X")
            self.text_slider_offset_y = self.ui.findChild(QLineEdit, "text_slider_offset_Y")
            self.text_slider_offset_z = self.ui.findChild(QLineEdit, "text_slider_offset_Z")
            
            if not all([self.combo_box_flight_routes_transform, self.slider_offset_x, self.slider_offset_y, 
                       self.slider_offset_z, self.text_slider_offset_x, self.text_slider_offset_y, 
                       self.text_slider_offset_z]):
                debug_print("⚠️ Some flight route adjustment widgets not found")
                return
            
            debug_print("✅ Found all flight route adjustment widgets")
            
            # Initialize slider ranges and values
            self._initialize_adjustment_sliders()
            
            # Connect slider signals to text fields
            self.slider_offset_x.valueChanged.connect(self._on_offset_x_changed)
            self.slider_offset_y.valueChanged.connect(self._on_offset_y_changed)
            self.slider_offset_z.valueChanged.connect(self._on_offset_z_changed)
            
            # Connect text field signals to sliders
            self.text_slider_offset_x.returnPressed.connect(self._on_offset_x_text_changed)
            self.text_slider_offset_y.returnPressed.connect(self._on_offset_y_text_changed)
            self.text_slider_offset_z.returnPressed.connect(self._on_offset_z_text_changed)
            
            # Connect combo box signal
            self.combo_box_flight_routes_transform.currentIndexChanged.connect(self._on_flight_route_selected)
            
            # Initialize combo box with available routes
            self._update_flight_routes_combo_box()
            
            debug_print("✅ Flight route adjustment controls setup complete")
            

            
        except Exception as e:
            debug_print(f"❌ Error setting up flight route adjustment controls: {e}")

    def _initialize_adjustment_sliders(self):
        """Initialize the adjustment sliders with appropriate ranges and values."""
        # Set ranges for X, Y, Z offsets (in meters)
        x_range = (-50, 50)  # -50m to +50m
        y_range = (-50, 50)  # -50m to +50m
        z_range = (-20, 20)  # -20m to +20m (more conservative for height)
        
        self.slider_offset_x.setRange(x_range[0], x_range[1])
        self.slider_offset_y.setRange(y_range[0], y_range[1])
        self.slider_offset_z.setRange(z_range[0], z_range[1])
        
        # Set initial values to 0
        self.slider_offset_x.setValue(0)
        self.slider_offset_y.setValue(0)
        self.slider_offset_z.setValue(0)
        
        # Update text fields
        self.text_slider_offset_x.setText("0.0")
        self.text_slider_offset_y.setText("0.0")
        self.text_slider_offset_z.setText("0.0")
        
        # Store ranges for validation
        self.slider_ranges = {
            'x': x_range,
            'y': y_range,
            'z': z_range
        }
        
        debug_print("✅ Adjustment sliders initialized")

    def _validate_and_clamp_slider_value(self, slider, value):
        """Validate and clamp a slider value to its range."""
        min_val = slider.minimum()
        max_val = slider.maximum()
        clamped_value = max(min_val, min(max_val, value))
        
        if clamped_value != value:
            debug_print(f"⚠️ Slider value {value} clamped to {clamped_value} (range: {min_val} to {max_val})")
        
        return clamped_value

    def _update_flight_routes_combo_box(self):
        """Update the combo box with available flight routes."""
        if not self.combo_box_flight_routes_transform:
            return
            
        self.combo_box_flight_routes_transform.clear()
        self.combo_box_flight_routes_transform.addItem("Select Flight Route", None)
        
        # Check for overview flight route
        if hasattr(self, 'overview_flight_waypoints') and self.overview_flight_waypoints:
            self.combo_box_flight_routes_transform.addItem("Overview Flight Route", "overview")
            debug_print("✅ Added Overview Flight Route to combo box")
        
        # Check for individual underdeck flight routes
        if hasattr(self, 'underdeck_flight_routes') and self.underdeck_flight_routes:
            for i, route in enumerate(self.underdeck_flight_routes):
                route_id = route.get('id', f'underdeck_section_{i+1}')
                route_type = route.get('type', 'normal')
                
                # Use the actual route ID from the data instead of creating new ones
                if 'axial' in route_id.lower():
                    # Extract section number from route ID (e.g., "axial_underdeck_span_1" -> "1")
                    section_num = route_id.split('_')[-1] if route_id.split('_')[-1].isdigit() else str(i+1)
                    display_name = f"Underdeck (Axial) Section {section_num}"
                    route_key = route_id  # Use the actual route ID
                else:
                    # Extract section number from route ID (e.g., "underdeck_span_1_crossing" -> "1")
                    if 'span_' in route_id and '_crossing' in route_id:
                        section_num = route_id.split('span_')[1].split('_')[0]
                    else:
                        section_num = str(i+1)
                    display_name = f"Underdeck Section {section_num}"
                    route_key = route_id  # Use the actual route ID
                
                self.combo_box_flight_routes_transform.addItem(display_name, route_key)
                debug_print(f"✅ Added {display_name} to combo box (ID: {route_key})")
        
        # Legacy support for old underdeck waypoints format
        elif hasattr(self, 'underdeck_flight_waypoints') and self.underdeck_flight_waypoints:
            self.combo_box_flight_routes_transform.addItem("Underdeck Flight Route", "underdeck")
            debug_print("✅ Added Legacy Underdeck Flight Route to combo box")
        
        # Legacy support for old axial underdeck route
        if hasattr(self, 'underdeck_flight_waypoints_Axial') and self.underdeck_flight_waypoints_Axial:
            self.combo_box_flight_routes_transform.addItem("Underdeck Axial Route", "underdeck_axial")
            debug_print("✅ Added Legacy Underdeck Axial Route to combo box")
        
        debug_print(f"📋 Flight routes combo box updated with {self.combo_box_flight_routes_transform.count() - 1} routes")

    def _on_flight_route_selected(self, index):
        if index <= 0:
            return
        route_type = self.combo_box_flight_routes_transform.currentData()
        if route_type:
            debug_print(f"🔄 Selected flight route: {route_type}")
            self._backup_original_waypoints(route_type)        
            self._restore_slider_settings(route_type)          
            self._apply_route_adjustment()                     

    def _reset_adjustment_sliders(self):
        """Reset all adjustment sliders to 0."""
        self.slider_offset_x.setValue(0)
        self.slider_offset_y.setValue(0)
        self.slider_offset_z.setValue(0)
        debug_print("🔄 Reset adjustment sliders to 0")

    def _clear_slider_settings(self, route_type):
        """Clear slider settings for the specified route type."""
        if not route_type:
            return
            
        if hasattr(self, 'slider_settings') and route_type in self.slider_settings:
            del self.slider_settings[route_type]
            debug_print(f"🗑️ Cleared slider settings for {route_type}")

    def _on_offset_x_changed(self, value):
        """Handle X offset slider change."""
        # Validate and clamp value to slider range
        clamped_value = self._validate_and_clamp_slider_value(self.slider_offset_x, value)
        
        # If value was clamped, update the slider
        if clamped_value != value:
            self.slider_offset_x.setValue(clamped_value)
            value = clamped_value
        
        self.text_slider_offset_x.setText(f"{value:.1f}")
        self._apply_route_adjustment()
        # Save slider settings for current route
        route_type = self.combo_box_flight_routes_transform.currentData()
        if route_type:
            self._save_slider_settings(route_type)

    def _on_offset_y_changed(self, value):
        """Handle Y offset slider change."""
        # Validate and clamp value to slider range
        clamped_value = self._validate_and_clamp_slider_value(self.slider_offset_y, value)
        
        # If value was clamped, update the slider
        if clamped_value != value:
            self.slider_offset_y.setValue(clamped_value)
            value = clamped_value
        
        self.text_slider_offset_y.setText(f"{value:.1f}")
        self._apply_route_adjustment()
        # Save slider settings for current route
        route_type = self.combo_box_flight_routes_transform.currentData()
        if route_type:
            self._save_slider_settings(route_type)

    def _on_offset_z_changed(self, value):
        """Handle Z offset slider change."""
        # Validate and clamp value to slider range
        clamped_value = self._validate_and_clamp_slider_value(self.slider_offset_z, value)
        
        # If value was clamped, update the slider
        if clamped_value != value:
            self.slider_offset_z.setValue(clamped_value)
            value = clamped_value
        
        self.text_slider_offset_z.setText(f"{value:.1f}")
        self._apply_route_adjustment()
        # Save slider settings for current route
        route_type = self.combo_box_flight_routes_transform.currentData()
        if route_type:
            self._save_slider_settings(route_type)

    def _on_offset_x_text_changed(self):
        """Handle X offset text field change."""
        try:
            value = float(self.text_slider_offset_x.text())
            # Clamp to slider range
            min_val, max_val = self.slider_offset_x.minimum(), self.slider_offset_x.maximum()
            value = max(min_val, min(max_val, value))
            self.slider_offset_x.setValue(int(value))
            self._apply_route_adjustment()
            # Save slider settings for current route
            route_type = self.combo_box_flight_routes_transform.currentData()
            if route_type:
                self._save_slider_settings(route_type)
        except ValueError:
            # Invalid input, revert to slider value
            self.text_slider_offset_x.setText(f"{self.slider_offset_x.value():.1f}")

    def _on_offset_y_text_changed(self):
        """Handle Y offset text field change."""
        try:
            value = float(self.text_slider_offset_y.text())
            # Clamp to slider range
            min_val, max_val = self.slider_offset_y.minimum(), self.slider_offset_y.maximum()
            value = max(min_val, min(max_val, value))
            self.slider_offset_y.setValue(int(value))
            self._apply_route_adjustment()
            # Save slider settings for current route
            route_type = self.combo_box_flight_routes_transform.currentData()
            if route_type:
                self._save_slider_settings(route_type)
        except ValueError:
            # Invalid input, revert to slider value
            self.text_slider_offset_y.setText(f"{self.slider_offset_y.value():.1f}")

    def _on_offset_z_text_changed(self):
        """Handle Z offset text field change."""
        try:
            value = float(self.text_slider_offset_z.text())
            # Clamp to slider range
            min_val, max_val = self.slider_offset_z.minimum(), self.slider_offset_z.maximum()
            value = max(min_val, min(max_val, value))
            self.slider_offset_z.setValue(int(value))
            self._apply_route_adjustment()
            # Save slider settings for current route
            route_type = self.combo_box_flight_routes_transform.currentData()
            if route_type:
                self._save_slider_settings(route_type)
        except ValueError:
            # Invalid input, revert to slider value
            self.text_slider_offset_z.setText(f"{self.slider_offset_z.value():.1f}")

    def _save_slider_settings(self, route_type):
        """Save current slider settings for the specified route type."""
        if not route_type:
            return
            
        # Initialize slider settings storage if not exists
        if not hasattr(self, 'slider_settings'):
            self.slider_settings = {}
        
        # Save current slider values
        self.slider_settings[route_type] = {
            'x': self.slider_offset_x.value(),
            'y': self.slider_offset_y.value(),
            'z': self.slider_offset_z.value()
        }
        debug_print(f"💾 Saved slider settings for {route_type}: X={self.slider_settings[route_type]['x']}, Y={self.slider_settings[route_type]['y']}, Z={self.slider_settings[route_type]['z']}")

    def _restore_slider_settings(self, route_type):
        """Restore slider settings for the specified route type."""
        if not route_type:
            return
            
        # Initialize slider settings storage if not exists
        if not hasattr(self, 'slider_settings'):
            self.slider_settings = {}
        
        # Check if settings exist for this route type
        if route_type in self.slider_settings:
            settings = self.slider_settings[route_type]
            
            # Temporarily disconnect signals to avoid triggering adjustments
            self.slider_offset_x.valueChanged.disconnect()
            self.slider_offset_y.valueChanged.disconnect()
            self.slider_offset_z.valueChanged.disconnect()
            
            # Clamp values to slider ranges before restoring
            x_val = max(self.slider_offset_x.minimum(), min(self.slider_offset_x.maximum(), settings['x']))
            y_val = max(self.slider_offset_y.minimum(), min(self.slider_offset_y.maximum(), settings['y']))
            z_val = max(self.slider_offset_z.minimum(), min(self.slider_offset_z.maximum(), settings['z']))
            
            # Restore slider values (clamped to valid range)
            self.slider_offset_x.setValue(x_val)
            self.slider_offset_y.setValue(y_val)
            self.slider_offset_z.setValue(z_val)
            
            # Update text fields
            self.text_slider_offset_x.setText(f"{x_val:.1f}")
            self.text_slider_offset_y.setText(f"{y_val:.1f}")
            self.text_slider_offset_z.setText(f"{z_val:.1f}")
            
            # Reconnect signals
            self.slider_offset_x.valueChanged.connect(self._on_offset_x_changed)
            self.slider_offset_y.valueChanged.connect(self._on_offset_y_changed)
            self.slider_offset_z.valueChanged.connect(self._on_offset_z_changed)
            
            debug_print(f"📂 Restored slider settings for {route_type}: X={x_val}, Y={y_val}, Z={z_val}")
        else:
            # No saved settings, reset to 0
            self._reset_adjustment_sliders()
            debug_print(f"🔄 No saved settings for {route_type}, reset to 0")

    def _apply_route_adjustment(self):
        """Apply the current offset adjustments to the selected flight route."""
        route_type = self.combo_box_flight_routes_transform.currentData()
        if not route_type:
            return
            
        # Get current offset values
        offset_x = self.slider_offset_x.value()
        offset_y = self.slider_offset_y.value()
        offset_z = self.slider_offset_z.value()
        
        if offset_x == 0 and offset_y == 0 and offset_z == 0:
            # No adjustment needed, restore original route
            self._restore_original_route(route_type)
            # Clear slider settings since we're back to original
            self._clear_slider_settings(route_type)
            return
        
        debug_print(f"🔄 Applying adjustments: X={offset_x:.1f}m, Y={offset_y:.1f}m, Z={offset_z:.1f}m to {route_type}")
        
        # Get the original waypoints for the selected route
        original_waypoints = self._get_original_waypoints(route_type)
        if not original_waypoints:
            debug_print(f"❌ No original waypoints found for {route_type}")
            return
        
        # Apply adjustments to waypoints
        adjusted_waypoints = []
        for waypoint in original_waypoints:
            # Handle different waypoint formats: [x, y, z] or [x, y, z, tag]
            if len(waypoint) >= 4:
                # waypoint format: [x, y, z, tag]
                adjusted_waypoint = [
                    waypoint[0] + offset_x,
                    waypoint[1] + offset_y,
                    waypoint[2] + offset_z,
                    waypoint[3]  # Keep the tag
                ]
            elif len(waypoint) >= 3:
                # waypoint format: [x, y, z]
                adjusted_waypoint = [
                    waypoint[0] + offset_x,
                    waypoint[1] + offset_y,
                    waypoint[2] + offset_z
                ]
            else:
                # Invalid waypoint format, skip it
                debug_print(f"⚠️ Skipping invalid waypoint format: {waypoint}")
                continue
                
            adjusted_waypoints.append(adjusted_waypoint)
        
        # Store the adjusted waypoints
        self._store_adjusted_waypoints(route_type, adjusted_waypoints)
        
        # Update the visualization to reflect the changes
        self._update_route_visualization(route_type, adjusted_waypoints)
        
        debug_print(f"✅ Applied adjustments to {len(adjusted_waypoints)} waypoints")

    def _get_original_waypoints(self, route_type):
        """Get the original waypoints for the specified route type."""
        if route_type == "overview":
            return getattr(self, 'overview_flight_waypoints_original', None)
        elif route_type == "underdeck":
            return getattr(self, 'underdeck_flight_waypoints_original', None)
        elif route_type == "underdeck_axial":
            return getattr(self, 'underdeck_flight_waypoints_Axial_original', None)
        elif route_type.startswith("underdeck_span_") and route_type.endswith("_crossing"):
            # Handle individual underdeck sections using actual route IDs
            return self._get_underdeck_route_original_waypoints(route_type)
        elif route_type.startswith("axial_underdeck_span_"):
            # Handle individual underdeck axial sections using actual route IDs
            return self._get_underdeck_route_original_waypoints(route_type)
        return None

    def _get_current_waypoints(self, route_type):
        """Get the current waypoints for the specified route type."""
        if route_type == "overview":
            return getattr(self, 'overview_flight_waypoints', None)
        elif route_type == "underdeck":
            return getattr(self, 'underdeck_flight_waypoints', None)
        elif route_type == "underdeck_axial":
            return getattr(self, 'underdeck_flight_waypoints_Axial', None)
        elif route_type.startswith("underdeck_span_") and route_type.endswith("_crossing"):
            # Handle individual underdeck sections using actual route IDs
            return self._get_underdeck_route_current_waypoints(route_type)
        elif route_type.startswith("axial_underdeck_span_"):
            # Handle individual underdeck axial sections using actual route IDs
            return self._get_underdeck_route_current_waypoints(route_type)
        return None

    def _store_adjusted_waypoints(self, route_type, adjusted_waypoints):
        """Store the adjusted waypoints for the specified route type."""
        if route_type == "overview":
            self.overview_flight_waypoints = adjusted_waypoints
        elif route_type == "underdeck":
            self.underdeck_flight_waypoints = adjusted_waypoints
        elif route_type == "underdeck_axial":
            self.underdeck_flight_waypoints_Axial = adjusted_waypoints
        elif route_type.startswith("underdeck_span_") and route_type.endswith("_crossing"):
            # Handle individual underdeck sections using actual route IDs
            self._store_underdeck_route_adjusted_waypoints(route_type, adjusted_waypoints)
        elif route_type.startswith("axial_underdeck_span_"):
            # Handle individual underdeck axial sections using actual route IDs
            self._store_underdeck_route_adjusted_waypoints(route_type, adjusted_waypoints)

    def _restore_original_route(self, route_type):
        """Restore the original waypoints for the specified route type."""
        original_waypoints = self._get_original_waypoints(route_type)
        if original_waypoints:
            self._store_adjusted_waypoints(route_type, original_waypoints)
            # Update the visualization to reflect the restoration
            self._update_route_visualization(route_type, original_waypoints)
            debug_print(f"✅ Restored original {route_type} route")

    def _backup_original_waypoints(self, route_type):
        """Backup original waypoints before any adjustments (once per route)."""
        if route_type == "overview" and hasattr(self, 'overview_flight_waypoints'):
            if not hasattr(self, 'overview_flight_waypoints_original'):
                self.overview_flight_waypoints_original = deepcopy(self.overview_flight_waypoints)
        elif route_type == "underdeck" and hasattr(self, 'underdeck_flight_waypoints'):
            if not hasattr(self, 'underdeck_flight_waypoints_original'):
                self.underdeck_flight_waypoints_original = deepcopy(self.underdeck_flight_waypoints)
        elif route_type == "underdeck_axial" and hasattr(self, 'underdeck_flight_waypoints_Axial'):
            if not hasattr(self, 'underdeck_flight_waypoints_Axial_original'):
                self.underdeck_flight_waypoints_Axial_original = deepcopy(self.underdeck_flight_waypoints_Axial)
        elif route_type.startswith("underdeck_span_") and route_type.endswith("_crossing"):
            self._backup_underdeck_route_original_waypoints(route_type)  
        elif route_type.startswith("axial_underdeck_span_"):
            self._backup_underdeck_route_original_waypoints(route_type)  
        
    def _backup_generated_waypoints(self):
        """Backup all generated waypoints for adjustment functionality."""
        try:
            # Backup overview flight waypoints
            if hasattr(self, 'overview_flight_waypoints') and self.overview_flight_waypoints:
                self.overview_flight_waypoints_original = self.overview_flight_waypoints.copy()
                debug_print(f"✅ Backed up {len(self.overview_flight_waypoints)} overview waypoints")
            
            # Backup underdeck flight waypoints
            if hasattr(self, 'underdeck_flight_waypoints') and self.underdeck_flight_waypoints:
                self.underdeck_flight_waypoints_original = self.underdeck_flight_waypoints.copy()
                debug_print(f"✅ Backed up {len(self.underdeck_flight_waypoints)} underdeck waypoints")
            
            # Backup underdeck axial waypoints
            if hasattr(self, 'underdeck_flight_waypoints_Axial') and self.underdeck_flight_waypoints_Axial:
                self.underdeck_flight_waypoints_Axial_original = self.underdeck_flight_waypoints_Axial.copy()
                debug_print(f"✅ Backed up {len(self.underdeck_flight_waypoints_Axial)} underdeck axial waypoints")
            
            # Backup individual underdeck sections
            if hasattr(self, 'underdeck_flight_routes') and self.underdeck_flight_routes:
                for route in self.underdeck_flight_routes:
                    route_id = route.get('id', '')
                    if route_id:
                        self._backup_underdeck_route_original_waypoints(route_id)
                debug_print(f"✅ Backed up {len(self.underdeck_flight_routes)} individual underdeck sections")
            
            debug_print("✅ All generated waypoints backed up for adjustment functionality")
            
        except Exception as e:
            debug_print(f"❌ Error backing up generated waypoints: {e}")

    def _get_underdeck_section_original_waypoints(self, section_index, axial=False):
        """Get original waypoints for a specific underdeck section."""
        if not hasattr(self, 'underdeck_flight_routes_original'):
            return None
        
        if section_index < len(self.underdeck_flight_routes_original):
            route = self.underdeck_flight_routes_original[section_index]
            route_type = route.get('type', 'normal')
            
            # Check if this is the axial route we're looking for
            if axial and route_type == 'axial':
                return route.get('points', [])
            elif not axial and route_type != 'axial':
                return route.get('points', [])
        
        return None

    def _get_underdeck_section_current_waypoints(self, section_index, axial=False):
        """Get current waypoints for a specific underdeck section."""
        if not hasattr(self, 'underdeck_flight_routes'):
            return None
        
        if section_index < len(self.underdeck_flight_routes):
            route = self.underdeck_flight_routes[section_index]
            route_type = route.get('type', 'normal')
            
            # Check if this is the axial route we're looking for
            if axial and route_type == 'axial':
                return route.get('points', [])
            elif not axial and route_type != 'axial':
                return route.get('points', [])
        
        return None

    def _store_underdeck_section_adjusted_waypoints(self, section_index, adjusted_waypoints, axial=False):
        """Store adjusted waypoints for a specific underdeck section."""
        if not hasattr(self, 'underdeck_flight_routes'):
            return
        
        if section_index < len(self.underdeck_flight_routes):
            route = self.underdeck_flight_routes[section_index]
            route_type = route.get('type', 'normal')
            
            # Check if this is the axial route we're looking for
            if axial and route_type == 'axial':
                route['points'] = adjusted_waypoints
                debug_print(f"✅ Updated underdeck axial section {section_index + 1} with {len(adjusted_waypoints)} waypoints")
            elif not axial and route_type != 'axial':
                route['points'] = adjusted_waypoints
                debug_print(f"✅ Updated underdeck section {section_index + 1} with {len(adjusted_waypoints)} waypoints")

    def _backup_underdeck_section_original_waypoints(self, section_index, axial=False):
        """Backup original waypoints for a specific underdeck section."""
        if not hasattr(self, 'underdeck_flight_routes'):
            return
        
        # Initialize backup storage if not exists
        if not hasattr(self, 'underdeck_flight_routes_original'):
            self.underdeck_flight_routes_original = []
        
        if section_index < len(self.underdeck_flight_routes):
            route = self.underdeck_flight_routes[section_index]
            route_type = route.get('type', 'normal')
            
            # Check if this is the axial route we're looking for
            if axial and route_type == 'axial':
                # Ensure we have space in the backup list
                while len(self.underdeck_flight_routes_original) <= section_index:
                    self.underdeck_flight_routes_original.append({})
                
                self.underdeck_flight_routes_original[section_index] = route.copy()
                debug_print(f"✅ Backed up underdeck axial section {section_index + 1}")
            elif not axial and route_type != 'axial':
                # Ensure we have space in the backup list
                while len(self.underdeck_flight_routes_original) <= section_index:
                    self.underdeck_flight_routes_original.append({})
                
                self.underdeck_flight_routes_original[section_index] = route.copy()
                debug_print(f"✅ Backed up underdeck section {section_index + 1}")

    def _get_underdeck_route_original_waypoints(self, route_id):
        """Get original waypoints for a specific underdeck route by its actual ID."""
        if not hasattr(self, 'underdeck_flight_routes_original') or not self.underdeck_flight_routes_original:
            return None
        
        # Find the route with the specified ID
        for route in self.underdeck_flight_routes_original:
            if route.get('id') == route_id:
                return route.get('points', [])
        
        return None

    def _get_underdeck_route_current_waypoints(self, route_id):
        """Get current waypoints for a specific underdeck route by its actual ID."""
        if not hasattr(self, 'underdeck_flight_routes') or not self.underdeck_flight_routes:
            return None
        
        # Find the route with the specified ID
        for route in self.underdeck_flight_routes:
            if route.get('id') == route_id:
                return route.get('points', [])
        
        return None

    def _store_underdeck_route_adjusted_waypoints(self, route_id, adjusted_waypoints):
        """Store adjusted waypoints for a specific underdeck route by its actual ID."""
        if not hasattr(self, 'underdeck_flight_routes') or not self.underdeck_flight_routes:
            return
        
        # Find and update the route with the specified ID
        for route in self.underdeck_flight_routes:
            if route.get('id') == route_id:
                route['points'] = adjusted_waypoints
                debug_print(f"✅ Updated route {route_id} with {len(adjusted_waypoints)} adjusted waypoints")
                return
        
        debug_print(f"⚠️ Route {route_id} not found for storing adjusted waypoints")

    def _backup_underdeck_route_original_waypoints(self, route_id):
        """Backup original waypoints for a specific underdeck route by its actual ID."""
        if not hasattr(self, 'underdeck_flight_routes') or not self.underdeck_flight_routes:
            return
        
        # Initialize backup storage if not exists
        if not hasattr(self, 'underdeck_flight_routes_original'):
            self.underdeck_flight_routes_original = []
        
        # Find the route with the specified ID
        for route in self.underdeck_flight_routes:
            if route.get('id') == route_id:
                # Check if already backed up
                for backup_route in self.underdeck_flight_routes_original:
                    if backup_route.get('id') == route_id:
                        return  # Already backed up
                
                # Create backup
                
                backup_route = copy.deepcopy(route)
                self.underdeck_flight_routes_original.append(backup_route)
                debug_print(f"✅ Backed up original waypoints for route {route_id}")
                return
        
        debug_print(f"⚠️ Route {route_id} not found for backup")

    def _update_route_visualization(self, route_type, adjusted_waypoints):
        """Update the 3D visualization to reflect route adjustments."""
        if not hasattr(self, 'visualizer') or not self.visualizer:
            debug_print("⚠️ No visualizer available for route visualization update")
            return
        
        try:
            # Extract just [x, y, z] coordinates for visualization
            viz_points = [[p[0], p[1], p[2]] for p in adjusted_waypoints]
            
            if route_type == "overview":
                # Update overview flight visualization
                self.visualizer.add_polyline(
                    'Overview Flight',
                    viz_points,
                    color=[0.0, 1.0, 0.0],  # Green color
                    line_width=5,
                    tube_radius=0
                )
                debug_print(f"✅ Updated overview flight visualization with {len(viz_points)} points")
                
            elif route_type == "underdeck":
                # Update legacy underdeck visualization
                self.visualizer.add_polyline(
                    'Underdeck Flight Route',
                    viz_points,
                    color=[0.53, 0.81, 0.92],  # Light blue
                    line_width=5,
                    tube_radius=0
                )
                debug_print(f"✅ Updated legacy underdeck visualization with {len(viz_points)} points")
                
            elif route_type == "underdeck_axial":
                # Update legacy underdeck axial visualization
                self.visualizer.add_polyline(
                    'Underdeck Axial Route',
                    viz_points,
                    color=[1.0, 0.71, 0.76],  # Light pink
                    line_width=5,
                    tube_radius=0
                )
                debug_print(f"✅ Updated legacy underdeck axial visualization with {len(viz_points)} points")
                
            elif route_type.startswith("underdeck_span_") and route_type.endswith("_crossing"):
                # Update individual underdeck section visualization using actual route ID
                # Extract section number from route ID (e.g., "underdeck_span_1_crossing" -> "1")
                section_num = route_type.split("span_")[1].split("_")[0]
                # Use the original visualization name format
                route_name = f"underdeck_span_{section_num}_crossing"
                
                self.visualizer.add_polyline(
                    route_name,
                    viz_points,
                    color=[0.53, 0.81, 0.92],  # Light blue
                    line_width=5,
                    tube_radius=0
                )
                debug_print(f"✅ Updated underdeck section {section_num} visualization with {len(viz_points)} points")
                
            elif route_type.startswith("axial_underdeck_span_"):
                # Update individual underdeck axial section visualization using actual route ID
                # Extract section number from route ID (e.g., "axial_underdeck_span_1" -> "1")
                section_num = route_type.split("_")[-1]
                # Use the original axial visualization name format
                route_name = f"axial_underdeck_span_{section_num}"
                
                self.visualizer.add_polyline(
                    route_name,
                    viz_points,
                    color=[1.0, 0.71, 0.76],  # Light pink
                    line_width=5,
                    tube_radius=0
                )
                debug_print(f"✅ Updated underdeck axial section {section_num} visualization with {len(viz_points)} points")
            
        except Exception as e:
            debug_print(f"❌ Error updating route visualization: {e}")

    def _save_complete_program_state(self):
        """Save ALL current program settings and state in one comprehensive file (atomic, JSON-safe),
        including auto-detected program version from filename like 'ORBITv0.97b_GUI_main.py'."""


        # ---------- helpers ----------
        def _json_coerce(obj):
            """Coerce numpy/Path/sets/tuples/etc. into JSON-serializable types."""
            try:
                
                if isinstance(obj, (np.integer,)):   return int(obj)
                if isinstance(obj, (np.floating,)):  return float(obj)
                if isinstance(obj, (np.ndarray,)):   return obj.tolist()
            except Exception:
                pass
            if isinstance(obj, Path):                return str(obj)
            if isinstance(obj, (set, tuple)):        return [_json_coerce(x) for x in obj]
            if isinstance(obj, list):                return [_json_coerce(x) for x in obj]
            if isinstance(obj, dict):                return {str(k): _json_coerce(v) for k, v in obj.items()}
            try:
                json.dumps(obj)
                return obj
            except TypeError:
                return repr(obj)

        _ORBIT_VERSION_REGEX = re.compile(r'ORBIT(v[0-9][\w.\-]*)', re.IGNORECASE)
        def _detect_orbit_version_from_filename(default: str = "ORBIT vUnknown") -> str:
            """Return 'ORBIT v...' parsed from the running filename or executable."""
            candidates = []

            # 1) Normal script run
            try:
                main_mod = sys.modules.get('__main__')
                if main_mod and getattr(main_mod, '__file__', None):
                    candidates.append(Path(main_mod.__file__).name)
            except Exception:
                pass

            # 2) Frozen apps (PyInstaller)
            try:
                if getattr(sys, 'frozen', False) and getattr(sys, 'executable', None):
                    candidates.append(Path(sys.executable).name)
            except Exception:
                pass

            # 3) argv[0]
            try:
                if sys.argv and sys.argv[0]:
                    candidates.append(Path(sys.argv[0]).name)
            except Exception:
                pass

            for name in candidates:
                m = _ORBIT_VERSION_REGEX.search(name or "")
                if m:
                    return f"ORBIT {m.group(1)}"
            return default

        try:
            # -----------------------------
            # Project directories
            # -----------------------------
            project_data = {}
            try:
                if getattr(self, "data_loader", None) and hasattr(self.data_loader, "_parse_project_data"):
                    project_data = self.data_loader._parse_project_data(skip_epsg_check=True) or {}
            except Exception as e:
                debug_print(f"[STATE] warn: parse project data: {e}")

            bridge_name = project_data.get('bridge_name', 'DefaultBridge')
            project_dir_base = project_data.get('project_dir_base', '.')
            project_dir = Path(project_dir_base) / bridge_name
            input_dir = project_dir / "01_Input"
            viz_dir   = project_dir / "02_Visualization"
            temp_dir  = viz_dir / "temp"
            for d in (project_dir, input_dir, viz_dir, temp_dir):
                d.mkdir(parents=True, exist_ok=True)

            # -----------------------------
            # Program version (cache on instance if not set)
            # -----------------------------
            if not getattr(self, 'PROGRAM_VERSION', None):
                try:
                    self.PROGRAM_VERSION = _detect_orbit_version_from_filename()
                except Exception:
                    self.PROGRAM_VERSION = "ORBIT vUnknown"

            # -----------------------------
            # Gather parameters & data
            # -----------------------------
            # Flight route settings (comprehensive)
            all_flight_settings = {}
            try:
                if hasattr(self, "_parse_all_flight_route_parameters"):
                    all_flight_settings = self._parse_all_flight_route_parameters() or {}
            except Exception as e:
                debug_print(f"[STATE] warn: parse all flight route parameters: {e}")

            # Safety params (for resolved z ranges)
            safety_params = {}
            try:
                if hasattr(self, "_parse_safety_zone_parameters"):
                    safety_params = self._parse_safety_zone_parameters() or {}
            except Exception as e:
                debug_print(f"[STATE] warn: parse safety params: {e}")

            zones = list(getattr(self, "current_safety_zones", []) or [])
            clearance = safety_params.get("safety_zones_clearance", []) or []
            default_z_min = safety_params.get("default_z_min", 0.0)
            default_z_max = safety_params.get("default_z_max", 50.0)
            resolved_zones = []
            for i, z in enumerate(zones):
                zmin, zmax = default_z_min, default_z_max
                if i < len(clearance) and isinstance(clearance[i], (list, tuple)) and len(clearance[i]) == 2:
                    zmin, zmax = clearance[i]
                resolved_zones.append({
                    "id": z.get("id", f"zone_{i}"),
                    "points": z.get("points", []),  # [[lat, lon], ...]
                    "z_min": float(zmin),
                    "z_max": float(zmax),
                })

            # Cross-section listify if numpy
            cs_pts = getattr(self, 'crosssection_transformed_points', None)
            if cs_pts is not None and hasattr(cs_pts, 'tolist'):
                cs_pts = cs_pts.tolist()

            # Booleans / states
            coord_selected = getattr(self, 'selected_coord_system', 'custom')

            has_context    = bool(getattr(self, 'current_context', None))
            has_transform  = bool(getattr(self, '_last_transform_func', None))

            # “runtime” names commonly used elsewhere
            last_coord_name = getattr(self, '_last_coordinate_system', None)


            # UI details
            try:
                current_tab_idx = getattr(self.ui, 'tabWidget', None).currentIndex() if hasattr(self.ui, 'tabWidget') else None
            except Exception:
                current_tab_idx = None

            # Counts
            traj = getattr(self, 'current_trajectory', []) or []
            pillars = getattr(self, 'current_pillars', []) or []
            cur_zone_pts = getattr(self, 'current_zone_points', []) or []
            counts = {
                "trajectory_points": len(traj),
                "pillars": len(pillars),
                "safety_zones": len(zones),
                "zone_points": len(cur_zone_pts),
                "cross_section_points": len(cs_pts or []),
            }

            # Flight routes availability
            overview_wp  = getattr(self, 'overview_flight_waypoints', []) or []
            underdeck_wp = getattr(self, 'underdeck_flight_waypoints', []) or []

            # Parsed-data keys snapshot
            parsed_proj_keys  = list(getattr(self, 'parsed_data', {}).get("project", {}).keys())
            parsed_route_keys = list(getattr(self, 'parsed_data', {}).get("flight_routes", {}).keys())

            # -----------------------------
            # Build final state
            # -----------------------------
            complete_state = {
                "metadata": {
                    "created_date": datetime.now().isoformat(),
                    "program_version": self.PROGRAM_VERSION,
                    "save_type": "complete_program_state",
                    "snapshot_version": 1
                },

                # 1. PROJECT SETTINGS (from Tab-0)
                "project_settings": project_data,

                # 2. FLIGHT ROUTE SETTINGS (from Tab-3 – comprehensive)
                "flight_route_settings": all_flight_settings,

                # 3. CURRENT GEOMETRY DATA
                "current_geometry": {
                    "trajectory_points": traj,
                    "pillars": pillars,
                    "safety_zones": zones,                     # raw (id + lat/lon)
                    "safety_zones_resolved": resolved_zones,   # id + lat/lon + z_min/z_max
                    "current_zone_points": cur_zone_pts,
                    "cross_section_points": cs_pts,
                    "counts": counts
                },

                # 4. COORDINATE SYSTEM INFORMATION
                "coordinate_system": {
                    "selected_system": coord_selected,

                    "context_available": has_context,
                    "transform_function_available": has_transform,
                    "last_project_coordinate_system": last_coord_name,

                },

                # 5. BRIDGE MODEL DATA
                "bridge_model": {
                    "bridge_object_available": bool(getattr(self, 'current_bridge', None)),
                    "context_object_available": has_context,
                    "cross_section_path": getattr(self, 'current_crosssection_path', None),
                    "cross_section_processed": cs_pts is not None
                },

                # 6. FLIGHT ROUTE GENERATION STATE
                "flight_routes": {
                    "overview_waypoints_available": bool(overview_wp),
                    "underdeck_waypoints_available": bool(underdeck_wp),
                    "overview_waypoints_count": len(overview_wp),
                    "underdeck_waypoints_count": len(underdeck_wp)
                },

                # 7. UI STATE
                "ui_state": {
                    "current_tab": current_tab_idx,
                    "drawing_mode": getattr(self, 'drawing_mode', 'none'),
                    "current_zone_id": getattr(self, 'current_zone_id', 0),
                    "visualizer_available": bool(getattr(self, 'visualizer', None))
                },

                # 8. PARSED DATA STATE
                "parsed_data_state": {
                    "project_keys": parsed_proj_keys,
                    "flight_route_keys": parsed_route_keys,

                },

                # 9. SAFETY VALIDATION STATE
                "safety_validation": {
                    "safety_zones_exist": len(zones) > 0,
                    "safety_check_photo_enabled": getattr(self, 'parsed_data', {}).get("flight_routes", {}).get("safety_check_photo", 0) == 1,
                    "safety_check_underdeck_enabled": any(
                        any(check == 1 for check in section)
                        for section in getattr(self, 'parsed_data', {}).get("flight_routes", {}).get("safety_check_underdeck", [])
                    )
                },

                # 10. FILE PATHS AND DIRECTORIES
                "file_paths": {
                    "project_directory": str(project_dir),
                    "input_directory": str(input_dir),
                    "visualization_directory": str(viz_dir),
                    "temp_directory": str(temp_dir),
                    "last_save_directory": str(getattr(self, '_last_save_dir', Path('.'))),
                    "last_bridge_name": getattr(self, '_last_bridge_name', bridge_name)
                }
            }

            # -----------------------------
            # Atomic write into 01_Input
            # -----------------------------
            state_file = input_dir / "complete_program_state.json"
            tmp = state_file.with_suffix(state_file.suffix + ".tmp")
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(_json_coerce(complete_state), f, indent=2, ensure_ascii=False)
            os.replace(tmp, state_file)

            debug_print(f"[SAVE] Complete program state saved to: {state_file}")
            return str(state_file)

        except Exception as e:
            try:
                if 'tmp' in locals() and Path(tmp).exists():
                    Path(tmp).unlink(missing_ok=True)
            except Exception:
                pass
            debug_print(f"[ERROR] Failed to save complete program state: {e}")
            import traceback; traceback.print_exc()
            return None


### Load Safety Zones from JSON
    def load_SafetyZones_fromJSON(self):
        """Load safety zones from JSON file."""
        try:
            # Get project_dir_base from parsed data
            project_data = self.parsed_data.get("project", {})
            project_dir_base = project_data.get('project_dir_base', '.')
            
            debug_print(f"[SAFETY_ZONE] Project Directory Base: {project_dir_base}")

            file_path, _ = QFileDialog.getOpenFileName(
                self.ui,
                "Select JSON file with safety zones",
                str(Path(project_dir_base)),  # Use the correct project_dir_base
                "JSON files (*.json);;All files (*.*)"
            )
            
            if not file_path:
                debug_print("[SAFETY_ZONE] No file selected")
                return
                
            debug_print(f"[SAFETY_ZONE] Loading safety zones from: {file_path}")
            
            # Read and parse JSON file
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Extract safety zones from different possible locations in JSON
            safety_zones = []
            
            # Check for safety zones in different possible locations
            if 'safety_zones' in data and data['safety_zones']:
                safety_zones = data['safety_zones']
                debug_print(f"[SAFETY_ZONE] Found {len(safety_zones)} safety zones in 'safety_zones' field")
            elif 'current_safety_zones' in data and data['current_safety_zones']:
                safety_zones = data['current_safety_zones']
                debug_print(f"[SAFETY_ZONE] Found {len(safety_zones)} safety zones in 'current_safety_zones' field")
            elif 'bridge_data' in data and 'safety_zones' in data['bridge_data']:
                safety_zones = data['bridge_data']['safety_zones']
                debug_print(f"[SAFETY_ZONE] Found {len(safety_zones)} safety zones in 'bridge_data.safety_zones' field")
            else:
                # Search for safety zones in nested structures
                def find_safety_zones(obj, path=""):
                    if isinstance(obj, dict):
                        for key, value in obj.items():
                            current_path = f"{path}.{key}" if path else key
                            if key in ['safety_zones', 'current_safety_zones'] and isinstance(value, list):
                                return value, current_path
                            result = find_safety_zones(value, current_path)
                            if result:
                                return result
                    elif isinstance(obj, list):
                        for i, item in enumerate(obj):
                            current_path = f"{path}[{i}]"
                            result = find_safety_zones(item, current_path)
                            if result:
                                return result
                    return None
                
                result = find_safety_zones(data)
                if result:
                    safety_zones, path = result
                    debug_print(f"[SAFETY_ZONE] Found {len(safety_zones)} safety zones in '{path}' field")
                else:
                    QMessageBox.warning(self.ui, "No Safety Zones Found", 
                                      "No safety zones found in the selected JSON file.")
                    return
            
            if not safety_zones:
                QMessageBox.information(self.ui, "No Safety Zones", 
                                      "The selected JSON file contains no safety zones.")
                return
            
            # Convert safety zones to the expected format
            converted_zones = []
            for i, zone in enumerate(safety_zones):
                if isinstance(zone, dict) and 'points' in zone:
                    # Zone already has the expected format
                    converted_zone = {
                        'id': zone.get('id', f'SZ{i}'),
                        'points': zone['points']
                    }
                elif isinstance(zone, list):
                    # Zone is just a list of points
                    converted_zone = {
                        'id': f'SZ{i}',
                        'points': zone
                    }
                else:
                    debug_print(f"[SAFETY_ZONE] Skipping invalid zone format: {zone}")
                    continue
                
                # Validate zone has at least 3 points
                if len(converted_zone['points']) >= 3:
                    converted_zones.append(converted_zone)
                else:
                    debug_print(f"[SAFETY_ZONE] Skipping zone {converted_zone['id']} with insufficient points: {len(converted_zone['points'])}")
            
            if not converted_zones:
                QMessageBox.warning(self.ui, "No Valid Safety Zones", 
                                  "No valid safety zones found in the selected JSON file.")
                return
            
            # Clear existing safety zones
            self.current_safety_zones.clear()
            self.current_zone_points.clear()
            self.safety_zones_redo_stack.clear()
            
            # Add loaded safety zones
            self.current_safety_zones.extend(converted_zones)
            
            # Update zone ID counter
            max_id = 0
            for zone in converted_zones:
                if zone['id'].startswith('SZ'):
                    try:
                        zone_num = int(zone['id'][2:])
                        max_id = max(max_id, zone_num)
                    except ValueError:
                        pass
            self.current_zone_id = max_id + 1
            
            # Update safety zones history
            self.safety_zones_history.append(self.current_safety_zones.copy())
            
            # Update map visualization
            self._update_safety_zones_on_map()
            
            # Load and update clearance information in tab3_textEdit
            self._load_clearance_information_to_tab3(data, converted_zones)
            
            debug_print(f"[SAFETY_ZONE] Successfully loaded {len(converted_zones)} safety zones")
            QMessageBox.information(self.ui, "Safety Zones Loaded", 
                                  f"Successfully loaded {len(converted_zones)} safety zones from the JSON file.")
            
            # Update last save directory
            self._last_save_dir = Path(file_path).parent
            
        except json.JSONDecodeError as e:
            QMessageBox.critical(self.ui, "JSON Error", 
                               f"Failed to parse JSON file: {str(e)}")
            debug_print(f"[SAFETY_ZONE] JSON parsing error: {e}")
        except Exception as e:
            QMessageBox.critical(self.ui, "Error", 
                               f"Failed to load safety zones: {str(e)}")
            debug_print(f"[SAFETY_ZONE] Error loading safety zones: {e}")
            import traceback
            traceback.print_exc()    

    def _load_clearance_information_to_tab3(self, data, converted_zones):
        """Load clearance information from JSON and update tab3_textEdit with colored formatting."""
        try:
            # Extract clearance information from different possible locations
            safety_zones_clearance = []
            safety_zones_clearance_adjust = []
            
            # Check for clearance information in different possible locations
            debug_print(f"[CLEARANCE] Debug: Available keys in JSON: {list(data.keys())}")
            
            # First, check in flight_route_settings (the correct location for saved program state)
            if 'flight_route_settings' in data and isinstance(data['flight_route_settings'], dict):
                flight_settings = data['flight_route_settings']
                debug_print(f"[CLEARANCE] Found flight_route_settings with keys: {list(flight_settings.keys())}")
                
                if 'safety_zones_clearance' in flight_settings and flight_settings['safety_zones_clearance']:
                    safety_zones_clearance = flight_settings['safety_zones_clearance']
                    debug_print(f"[CLEARANCE] Found {len(safety_zones_clearance)} clearance entries in flight_route_settings.safety_zones_clearance")
                    debug_print(f"[CLEARANCE] Clearance values: {safety_zones_clearance}")
                
                if 'safety_zones_clearance_adjust' in flight_settings and flight_settings['safety_zones_clearance_adjust']:
                    safety_zones_clearance_adjust = flight_settings['safety_zones_clearance_adjust']
                    debug_print(f"[CLEARANCE] Found {len(safety_zones_clearance_adjust)} adjustment entries in flight_route_settings.safety_zones_clearance_adjust")
                    debug_print(f"[CLEARANCE] Adjustment values: {safety_zones_clearance_adjust}")
            
            # Fallback: check for direct fields (for simple JSON files)
            if not safety_zones_clearance and 'safety_zones_clearance' in data and data['safety_zones_clearance']:
                safety_zones_clearance = data['safety_zones_clearance']
                debug_print(f"[CLEARANCE] Found {len(safety_zones_clearance)} clearance entries in direct 'safety_zones_clearance' field")
                debug_print(f"[CLEARANCE] Clearance values: {safety_zones_clearance}")
            
            if not safety_zones_clearance_adjust and 'safety_zones_clearance_adjust' in data and data['safety_zones_clearance_adjust']:
                safety_zones_clearance_adjust = data['safety_zones_clearance_adjust']
                debug_print(f"[CLEARANCE] Found {len(safety_zones_clearance_adjust)} adjustment entries in direct 'safety_zones_clearance_adjust' field")
                debug_print(f"[CLEARANCE] Adjustment values: {safety_zones_clearance_adjust}")
            
            # Fallback: check in current_safety_zones (for individual zone clearance)
            if not safety_zones_clearance and 'current_safety_zones' in data and data['current_safety_zones']:
                # Extract clearance from individual safety zones
                for zone in data['current_safety_zones']:
                    if isinstance(zone, dict) and 'clearance' in zone:
                        safety_zones_clearance.append(zone['clearance'])
                        debug_print(f"[CLEARANCE] Found clearance {zone['clearance']} for zone {zone.get('id', 'unknown')}")
            
            if not safety_zones_clearance:
                debug_print("[CLEARANCE] No safety_zones_clearance found in JSON data")
            if not safety_zones_clearance_adjust:
                debug_print("[CLEARANCE] No safety_zones_clearance_adjust found in JSON data")
            
            # If no clearance information found, create default values
            if not safety_zones_clearance:
                safety_zones_clearance = [[0, 20] for _ in converted_zones]
                debug_print(f"[CLEARANCE] No clearance information found, using default values: {safety_zones_clearance}")
            
            if not safety_zones_clearance_adjust:
                safety_zones_clearance_adjust = [[20] for _ in converted_zones]
                debug_print(f"[CLEARANCE] No adjustment information found, using default values: {safety_zones_clearance_adjust}")
            
            # Note: Don't force clearance arrays to match the number of safety zones
            # The clearance arrays can be independent of the loaded safety zones
            
            # Get the current content of tab3_textEdit
            if hasattr(self.ui, 'tab3_textEdit'):
                current_content = self.ui.tab3_textEdit.toHtml()
                
                # Update the clearance information in the content
                updated_content = self._update_clearance_in_text(
                    current_content, 
                    safety_zones_clearance, 
                    safety_zones_clearance_adjust
                )
                
                # Set the updated content back to tab3_textEdit
                self.ui.tab3_textEdit.setHtml(updated_content)
                
                debug_print(f"[CLEARANCE] Updated tab3_textEdit with clearance information")
                debug_print(f"[CLEARANCE] safety_zones_clearance = {safety_zones_clearance}")
                debug_print(f"[CLEARANCE] safety_zones_clearance_adjust = {safety_zones_clearance_adjust}")
            else:
                debug_print("[CLEARANCE] Warning: tab3_textEdit not found")
                
        except Exception as e:
            debug_print(f"[CLEARANCE] Error updating clearance information: {e}")
            import traceback
            traceback.print_exc()
    
    def _update_clearance_in_text(self, text_content, safety_zones_clearance, safety_zones_clearance_adjust):
        """Update clearance information in the text content with colored formatting."""
        
        
        # Convert lists to string representation
        clearance_str = str(safety_zones_clearance)
        adjust_str = str(safety_zones_clearance_adjust)
        
        # Check if content is HTML or plain text
        is_html = text_content.startswith('<!DOCTYPE HTML')
        
        if is_html:
            # Handle HTML content - update only the variable values while preserving HTML structure
            # Simpler approach: Find the specific lines and replace the array values
            # Update safety_zones_clearance in HTML
            clearance_pattern = r'(safety_zones_clearance.*?=.*?)\[\[.*?\]\]'
            clearance_replacement = r'\1' + clearance_str
            text_content = re.sub(clearance_pattern, clearance_replacement, text_content, flags=re.DOTALL)
            
            # Update safety_zones_clearance_adjust in HTML
            adjust_pattern = r'(safety_zones_clearance_adjust.*?=.*?)\[\[.*?\]\]'
            adjust_replacement = r'\1' + adjust_str
            text_content = re.sub(adjust_pattern, adjust_replacement, text_content, flags=re.DOTALL)
            
            # Add color highlighting to the updated values
            # Find the updated values and wrap them in colored spans (avoid double-wrapping)
            clearance_color_pattern = r'(safety_zones_clearance.*?=.*?)(\[\[.*?\]\])(?!.*?color:#aaaaff)'
            clearance_color_replacement = r'\1<span style=" font-family:\'Consolas,Courier New,monospace\'; font-size:11pt; color:#aaaaff;">\2</span>'
            text_content = re.sub(clearance_color_pattern, clearance_color_replacement, text_content, flags=re.DOTALL)
            
            adjust_color_pattern = r'(safety_zones_clearance_adjust.*?=.*?)(\[\[.*?\]\])(?!.*?color:#aaaaff)'
            adjust_color_replacement = r'\1<span style=" font-family:\'Consolas,Courier New,monospace\'; font-size:11pt; color:#aaaaff;">\2</span>'
            text_content = re.sub(adjust_color_pattern, adjust_color_replacement, text_content, flags=re.DOTALL)
            
        else:
            # Handle plain text content
            # Update safety_zones_clearance
            clearance_pattern = r'(safety_zones_clearance\s*=\s*)\[\[.*?\]\]'
            if re.search(clearance_pattern, text_content):
                text_content = re.sub(
                    clearance_pattern, 
                    r'\1' + clearance_str, 
                    text_content, 
                    flags=re.DOTALL
                )
            else:
                # If not found, add it after the Safety Zones section
                safety_section_pattern = r'(Safety Zones:.*?)(?=\n\n|\Z)'
                replacement = r'\1\nsafety_zones_clearance = ' + clearance_str
                text_content = re.sub(safety_section_pattern, replacement, text_content, flags=re.DOTALL)
            
            # Update safety_zones_clearance_adjust
            adjust_pattern = r'(safety_zones_clearance_adjust\s*=\s*)\[\[.*?\]\]'
            if re.search(adjust_pattern, text_content):
                text_content = re.sub(
                    adjust_pattern, 
                    r'\1' + adjust_str, 
                    text_content, 
                    flags=re.DOTALL
                )
            else:
                # If not found, add it after safety_zones_clearance
                clearance_line_pattern = r'(safety_zones_clearance\s*=\s*\[\[.*?\]\].*?)(?=\n|\Z)'
                replacement = r'\1\nsafety_zones_clearance_adjust = ' + adjust_str
                text_content = re.sub(clearance_line_pattern, replacement, text_content, flags=re.DOTALL)
        
        return text_content

    def _convert_plain_text_to_html(self, plain_text):
        """Convert plain text to Qt HTML with simple syntax highlighting.
        - Escapes HTML first
        - Highlights keywords only before '#'
        - Leaves comments green
        """
        

        def style_kw(s):
            return f"<span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#9cdcfe;\">{s}</span>"

        def style_eq():
            return "<span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#d4d4d4;\">=</span>"

        def style_comment(s):
            return f"<span style=\" font-family:'Consolas,Courier New,monospace'; font-size:11pt; color:#6a9955;\">{s}</span>"

        html_content = """<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.0//EN" "http://www.w3.org/TR/REC-html40/strict.dtd">
    <html><head><meta name="qrichtext" content="1" /><style type="text/css">
    p, li { white-space: pre-wrap; }
    </style></head><body style=" font-family:'MS Shell Dlg 2'; font-size:8.25pt; font-weight:400; font-style:normal;">
    """

        keywords = [
            'safety_zones_clearance',
            'safety_zones_clearance_adjust',
        ]

        for raw in plain_text.split('\n'):
            if raw.strip() == '':
                html_content += '<p style="-qt-paragraph-type:empty; margin:0;"><br /></p>\n'
                continue

            esc = html.escape(raw, quote=False)

            # split into code | comment (first '#')
            if '#' in esc:
                code, comment = esc.split('#', 1)
                comment = '#' + comment
            else:
                code, comment = esc, ''

            # highlight in code part only
            for kw in keywords:
                code = code.replace(kw, style_kw(kw))
            code = code.replace('=', style_eq())

            # style comment
            if comment:
                comment = style_comment(comment)

            line_html = code + comment
            html_content += f'<p style=" margin:0; -qt-block-indent:0; text-indent:0px;">{line_html}</p>\n'

        html_content += "</body></html>"
        return html_content
    def _update_project_data_in_text(self, text_content, updated_data):
        """Thin wrapper that uses the robust colored updater to avoid divergence."""
        try:
            fn = getattr(self, '_update_project_data_in_text_with_colors', None)
            if callable(fn):
                return fn(text_content, updated_data)
        except Exception:
            pass

        # Fallback: same robust logic (copied) to be safe if the colored function is missing.
        
        if not updated_data:
            return text_content

        def _to_str(v): return str(v)
        is_html = text_content.lstrip().lower().startswith("<!doctype html") or text_content.lstrip().lower().startswith("<html")

        if not is_html:
            for key, value in updated_data.items():
                if value is None: continue
                new_val = _to_str(value)
                pattern = re.compile(
                    rf'(^|\n)(?P<prefix>[ \t]*{re.escape(key)}\s*=\s*)(?P<val>[^\n#]*?)(?P<comment>[ \t]*#.*)?(?=\r?\n|$)',
                    flags=re.IGNORECASE
                )
                def _repl(m):
                    prefix = m.group('prefix')
                    old_val = (m.group('val') or '').strip()
                    comment = m.group('comment') or ''
                    had_quotes = (old_val.startswith('"') and old_val.endswith('"')) or (old_val.startswith("'") and old_val.endswith("'"))
                    if had_quotes:
                        return m.group(1) + f"{prefix}\"{new_val}\"{comment}"
                    else:
                        return m.group(1) + f"{prefix}{new_val}{comment}"
                new_text, n = pattern.subn(_repl, text_content, count=1)
                if n == 0:
                    text_content = text_content.rstrip('\n') + f'\n{key} = "{new_val}"'
                else:
                    text_content = new_text
            return text_content

        # HTML robust path
        SP = r'(?:\s|&nbsp;|<[^>]*>)*'
        for key, value in updated_data.items():
            if value is None: continue
            new_val = _to_str(value)
            pattern = re.compile(
                rf'({re.escape(key)}{SP}={SP})(?P<val>.*?)(?=(?:{SP}#|{SP}</p>))',
                flags=re.IGNORECASE | re.DOTALL
            )
            def _repl_html(m):
                prefix = m.group(1)
                colored = (
                    "<span style=\" font-family:'Consolas,Courier New,monospace'; "
                    "font-size:11pt; color:#aaaaff;\">"
                    f"\"{new_val}\""
                    "</span>"
                )
                return prefix + colored
            new_text, n = pattern.subn(_repl_html, text_content, count=1)
            if n == 0:
                new_line = (
                    f'<p style=" margin:0; -qt-block-indent:0; text-indent:0px;">'
                    f'{key} = '
                    f'<span style=" font-family:\'Consolas,Courier New,monospace\'; font-size:11pt; color:#aaaaff;">'
                    f'"{new_val}"'
                    f'</span></p>'
                )
                low = text_content.lower()
                idx = low.rfind('</body>')
                if idx != -1:
                    text_content = text_content[:idx] + new_line + text_content[idx:]
                else:
                    text_content += new_line
            else:
                text_content = new_text
        return text_content






    def update_textbox_variables(self, text_edit_ref, updates: dict, *, color="#aaaaff", font_pt=11):
        """
        Replace values for given variables in a QTextEdit while preserving comments
        and styling the new value in purple (pt 11).

        Parameters
        ----------
        text_edit_ref : str | QTextEdit
            Either the objectName of a QTextEdit on self.ui (e.g. "tab0_textEdit1_Photo",
            "tab3_textEdit") or a QTextEdit instance.
        updates : dict
            Mapping of variable_name -> value (None or "*" are ignored).
            Example: {"coordinate_system": self.selected_coord_system, "epsilonInput": self.epsilonInput}
        color : str
            CSS color for the updated value span (default: #aaaaff).
        font_pt : int
            Point size for the updated value (default: 11).
        """
        

        # Resolve the QTextEdit
        if isinstance(text_edit_ref, str):
            te = getattr(self.ui, text_edit_ref, None)
            if te is None or not isinstance(te, QTextEdit):
                debug_print(f"[TEXTBOX_UPDATE] ❌ Could not resolve QTextEdit '{text_edit_ref}'")
                return
        else:
            te = text_edit_ref
            if not isinstance(te, QTextEdit):
                debug_print(f"[TEXTBOX_UPDATE] ❌ Provided widget is not a QTextEdit")
                return

        # Get current content; we always work in HTML so we can colorize the value
        html_text = te.toHtml()
        is_html = html_text.strip().lower().startswith("<!doctype html") or "<html" in html_text.lower()

        if not is_html:
            # Convert to a minimal HTML so we can style values
            plain = te.toPlainText()
            # Simple safe conversion: escape and wrap each line in <p>
            html_lines = []
            for line in plain.splitlines():
                if line.strip():
                    html_lines.append(f'<p style=" margin:0; -qt-block-indent:0; text-indent:0px;">{html.escape(line, quote=False)}</p>')
                else:
                    html_lines.append('<p style="-qt-paragraph-type:empty; margin:0;"><br /></p>')
            html_text = (
                "<!DOCTYPE HTML PUBLIC \"-//W3C//DTD HTML 4.0//EN\" "
                "\"http://www.w3.org/TR/REC-html40/strict.dtd\">\n"
                "<html><head><meta name=\"qrichtext\" content=\"1\" />"
                "<style type=\"text/css\">p, li { white-space: pre-wrap; }</style>"
                "</head><body style=\" font-family:'MS Shell Dlg 2'; font-size:8.25pt;\">"
                + "\n".join(html_lines) +
                "</body></html>"
            )

        # Build a robust pattern for "var = value [# comment]" within HTML paragraphs
        # SP matches spaces/tags/&nbsp; sequences between tokens inside HTML
        SP = r'(?:\s|&nbsp;|<[^>]*>)*'

        def replace_var_in_html(text: str, var: str, value) -> str:
            if value is None:
                return text
            val_str = str(value).strip()
            if val_str == "*":   # skip placeholder updates
                return text

            # Capture:
            #  prefix = "<var> <spaces> = <spaces>"
            #  val    = anything up to (optional) comment or paragraph end
            #  comment= (spaces) '#' not followed by a digit (so "#10" stays part of value) ... up to </p>
            pattern = re.compile(
                rf'(?P<prefix>\b{re.escape(var)}{SP}={SP})'
                rf'(?P<val>.*?)'
                rf'(?P<comment>{SP}#(?!\d).*?)?'
                rf'(?=(?:{SP}</p>|{SP}$))',
                flags=re.IGNORECASE | re.DOTALL
            )

            # Style the value (escaped)
            colored_val = (
                f"<span style=\" font-family:'Consolas,Courier New,monospace'; "
                f"font-size:{font_pt}pt; color:{color};\">{html.escape(val_str, quote=False)}</span>"
            )

            def _repl(m: re.Match) -> str:
                prefix = m.group('prefix')
                comment = m.group('comment') or ''
                # Replace entire value region, keep prefix and comment untouched
                return prefix + colored_val + comment

            # Replace only the first occurrence in the document
            new_text, n = pattern.subn(_repl, text, count=1)
            if n == 0:
                # Append a new line before </body>
                new_line = (f'<p style=" margin:0; -qt-block-indent:0; text-indent:0px;">'
                            f'{html.escape(var, quote=False)} = {colored_val}</p>')
                low = text.lower()
                idx = low.rfind('</body>')
                if idx >= 0:
                    text = text[:idx] + new_line + text[idx:]
                else:
                    text += new_line
                return text
            return new_text

        # Apply all updates
        new_html = html_text
        for var, val in (updates or {}).items():
            new_html = replace_var_in_html(new_html, var, val)

        # Push back to the editor
        te.setHtml(new_html)
        debug_print(f"[TEXTBOX_UPDATE] ✓ Updated variables: {', '.join([k for k in updates.keys() if updates[k] not in (None, '*')])}")

# Global application lifecycle tracker
class ApplicationLifecycleTracker:
    """Tracks application lifecycle and logs shutdown points."""

    def __init__(self):
        self.start_time = time.time()
        self.last_operation = "Application startup"
        self.operation_stack = []

    def log_operation(self, operation: str, details: str = ""):
        """Log a major application operation."""
        timestamp = time.strftime("%H:%M:%S")
        self.last_operation = operation
        self.operation_stack.append(f"{timestamp}: {operation}")
        if len(self.operation_stack) > 50:  # Keep last 50 operations
            self.operation_stack.pop(0)

        detail_str = f" | {details}" if details else ""
        debug_print(f"📋 [{timestamp}] OPERATION: {operation}{detail_str}")

    def log_shutdown(self, reason: str, location: str = "", exit_code: int = None):
        """Log application shutdown with comprehensive information."""
        shutdown_time = time.time()
        runtime = shutdown_time - self.start_time

        debug_print("🛑 ======= APPLICATION SHUTDOWN DETECTED =======")
        debug_print(f"🛑 Reason: {reason}")
        debug_print(f"🛑 Location: {location}")
        if exit_code is not None:
            debug_print(f"🛑 Exit code: {exit_code}")
        debug_print(".2f")
        debug_print(f"🛑 Last operation: {self.last_operation}")

        debug_print("🛑 ======= LAST 10 OPERATIONS =======")
        for i, op in enumerate(self.operation_stack[-10:], 1):
            debug_print(f"🛑 {i:2d}: {op}")

        debug_print("🛑 ======= END SHUTDOWN LOG =======")

# Global lifecycle tracker
lifecycle_tracker = ApplicationLifecycleTracker()

def global_exception_handler(exctype, value, traceback_obj):
    """Global exception handler to catch any unhandled exceptions."""
    import traceback as tb

    debug_print("💥 ======= UNHANDLED EXCEPTION CAUGHT =======")
    debug_print(f"💥 Exception type: {exctype.__name__}")
    debug_print(f"💥 Exception message: {value}")
    debug_print(f"💥 Last operation: {lifecycle_tracker.last_operation}")

    debug_print("💥 ======= FULL TRACEBACK =======")
    for line in tb.format_exception(exctype, value, traceback_obj):
        debug_print(f"💥 {line.strip()}")

    debug_print("💥 ======= END UNHANDLED EXCEPTION =======")

    # Log shutdown
    lifecycle_tracker.log_shutdown(
        f"Unhandled exception: {exctype.__name__}: {value}",
        "global_exception_handler"
    )

def signal_handler(signum, frame):
    """Handle system signals for clean shutdown."""
    signal_names = {
        1: "SIGHUP", 2: "SIGINT", 3: "SIGQUIT", 6: "SIGABRT",
        9: "SIGKILL", 15: "SIGTERM"
    }
    signal_name = signal_names.get(signum, f"Signal {signum}")

    debug_print(f"📡 ======= SIGNAL RECEIVED =======")
    debug_print(f"📡 Signal: {signal_name} ({signum})")
    debug_print(f"📡 Last operation: {lifecycle_tracker.last_operation}")

    debug_print("📡 ======= STACK TRACE AT SIGNAL =======")
    for line in traceback.format_stack(frame):
        debug_print(f"📡 {line.strip()}")

    lifecycle_tracker.log_shutdown(f"Signal received: {signal_name}", "signal_handler")

def setup_crash_detection():
    """Set up comprehensive crash detection and logging."""
    debug_print("🛡️ ======= SETTING UP CRASH DETECTION =======")

    # Set up global exception handler
    sys.excepthook = global_exception_handler
    debug_print("🛡️ Global exception handler installed")

    # Set up signal handlers
    signals_to_handle = [signal.SIGINT, signal.SIGTERM, signal.SIGABRT]
    for sig in signals_to_handle:
        try:
            signal.signal(sig, signal_handler)
            debug_print(f"🛡️ Signal handler installed for {sig}")
        except (OSError, ValueError) as e:
            debug_print(f"🛡️ Could not install handler for signal {sig}: {e}")

    debug_print("🛡️ ======= CRASH DETECTION SETUP COMPLETE =======")

def main():
    """Main application entry point with comprehensive crash detection."""
    debug_print("🚀 ======= ORBIT APPLICATION STARTING =======")
    debug_print(f"🚀 Application version: ORBIT v0.97b")
    debug_print(f"🚀 Python version: {sys.version}")
    debug_print(f"🚀 Platform: {sys.platform}")
    debug_print(f"🚀 Working directory: {os.getcwd()}")
    debug_print(f"🚀 Command line args: {sys.argv}")

    lifecycle_tracker.log_operation("Application startup", f"Args: {sys.argv}")

    # Set up crash detection
    setup_crash_detection()

    try:
        lifecycle_tracker.log_operation("Creating QApplication")
        app = QApplication(sys.argv)
        debug_print("🚀 QApplication created successfully")

        # Set application properties
        app.setApplicationName("ORBIT Flight Planning")
        app.setApplicationVersion("0.1")
        app.setOrganizationName("KU Leuven")
        ico_path = Path(__file__).parent / "resources" / "icons" / "icon.ico"
        app.setWindowIcon(QIcon(str(ico_path)))
        debug_print("🚀 Application properties set")

        lifecycle_tracker.log_operation("Creating main window")
        debug_print("🚀 Creating main window...")
        window = OrbitMainApp()
        debug_print("🚀 Main window created successfully")

        lifecycle_tracker.log_operation("Showing main window")
        debug_print("🚀 Showing main window...")
        window.show()
        debug_print("🚀 Main window shown")

        lifecycle_tracker.log_operation("Starting Qt event loop")
        debug_print("🚀 Starting Qt event loop...")
        result = app.exec()
        debug_print(f"🚀 Qt event loop exited with code: {result}")

        lifecycle_tracker.log_shutdown("Normal application exit", "main() function", result)
        debug_print("🛑 ======= ORBIT APPLICATION SHUTTING DOWN NORMALLY =======")

        return result

    except Exception as e:
        debug_print(f"💥 ======= CRITICAL ERROR IN MAIN() =======")
        debug_print(f"💥 Exception: {e}")
        debug_print("💥 ======= TRACEBACK =======")
        traceback.print_exc()
        debug_print("💥 ======= END CRITICAL ERROR =======")

        lifecycle_tracker.log_shutdown(f"Critical error in main(): {e}", "main() function")
        return 1


if __name__ == "__main__":
    sys.exit(main()) 