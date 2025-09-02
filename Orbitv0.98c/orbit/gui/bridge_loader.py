from __future__ import annotations

"""Bridge data loader that integrates with existing GUI button and text fields."""

import glob
import os
import ast
import re
import pandas as pd
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List

from PySide6.QtWidgets import (QFileDialog, QMessageBox, QTextEdit, QGraphicsView,
                              QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                              QComboBox, QButtonGroup, QRadioButton, QScrollArea,
                              QWidget, QFrame, QGraphicsScene, QGraphicsPixmapItem, QLineEdit,
                              QCheckBox)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

from ..io.context import ProjectContext, VerticalRef, CoordinateSystemRegistry


from ..io import load_bridge
from ..io.models import Bridge
from ..resources.templates import get_default_project_data, create_default_input_folder, get_default_flight_route_settings
from ..io.data_parser import parse_text_boxes, DEBUG_PRINT
from ..gui.cross_section_analysis import process_crosssection_image, calculate_maximum_width

# Debug control functions - use the same pattern as main app
def debug_print(*args, **kwargs) -> None:
    """Print function that only outputs when DEBUG is True."""
    # Import DEBUG from main app context
    try:
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

class BridgeDataLoader:
    """Handles loading bridge data from various sources with GUI integration."""
    
    def __init__(self, parent_widget, project_text_edit: QTextEdit, flight_routes_text_edit: QTextEdit = None, cross_section_view: QGraphicsView = None):
        self.parent = parent_widget
        self.project_text_edit = project_text_edit
        self.flight_routes_text_edit = flight_routes_text_edit
        self.cross_section_view = cross_section_view
        
        # Initialize coordinate system preferences to prevent crashes
        self.last_coord_system = None

        self.current_bridge: Optional[Bridge] = None
        self.current_context: Optional[ProjectContext] = None
        self.flight_route_data: Dict[str, Any] = {}
        self.project_data: Dict[str, Any] = {}
        self.current_crosssection_path = None  # Track selected cross-section image path
    
    def import_directory(self) -> bool:
        """Handle btn_tab0_ImportDirectory click - open directory dialog and update text box."""
        
        # Get current import directory from text box (if any)
        current_dir = self._get_import_directory_from_text()
        
        # Open directory selection dialog
        selected_dir = QFileDialog.getExistingDirectory(
            self.parent,
            "Select Import Directory (01_Input folder)",
            str(current_dir) if current_dir else "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if selected_dir:
            debug_print(f"[DEBUG] import_directory - Selected directory: {selected_dir}")
            # Update the text box with the new import directory
            self._update_import_directory_in_text(selected_dir)
            QMessageBox.information(self.parent, "Success", 
                                  f"Import directory updated to:\n{selected_dir}")
            return True
        
        return False
    
    def _get_import_directory_from_text(self) -> Optional[Path]:
        """Extract import_dir from the project text box."""
        if not self.project_text_edit:
            return None
        
        text_content = self.project_text_edit.toPlainText().strip()
        
        for line in text_content.split('\n'):
            line = line.strip()
            if line.startswith('import_dir') and '=' in line:
                _, value = line.split('=', 1)
                value = value.strip().strip('"\'')
                if value:
                    return Path(value)
        
        return None
    
    def _update_import_directory_in_text(self, new_directory: str):
        """Update the import_dir line in the project text box while preserving formatting."""
        try:

            # Add null check for project_text_edit
            if not self.project_text_edit:
                debug_print("[DEBUG] No project text edit available for update")
                return

            # Check if content is HTML or plain text
            current_content = self.project_text_edit.toHtml()
            is_html = current_content.startswith('<!DOCTYPE HTML')
            
            if is_html:
                # Use HTML-aware update to preserve formatting and colors
                updated_data = {'import_dir': new_directory}
                updated_content = self._update_project_data_in_text_with_colors(current_content, updated_data)
                self.project_text_edit.setHtml(updated_content)
                debug_print(f"[DEBUG] Updated import_dir in HTML format: {new_directory}")
            else:
                # Fallback to plain text update for backward compatibility
                text_content = self.project_text_edit.toPlainText()
                lines = text_content.split('\n')
                
                # Find and update import_dir line, preserving original formatting
                updated = False
                for i, line in enumerate(lines):
                    stripped_line = line.strip()
                    if stripped_line.startswith('import_dir') and '=' in stripped_line:
                        # Preserve leading whitespace from original line
                        leading_space = line[:len(line) - len(line.lstrip())]
                        
                        # Check if the original line had quotes and preserve that style
                        original_line = line.strip()
                        if '=' in original_line:
                            value_part = original_line.split('=', 1)[1].strip()
                            # Check if the original value was quoted
                            had_quotes = (value_part.startswith('"') and value_part.endswith('"')) or (value_part.startswith("'") and value_part.endswith("'"))
                            if had_quotes:
                                lines[i] = f'{leading_space}import_dir = "{new_directory}"'
                            else:
                                lines[i] = f'{leading_space}import_dir = {new_directory}'
                        else:
                            # Default to no quotes if we can't determine the original style
                            lines[i] = f'{leading_space}import_dir = {new_directory}'
                        
                        updated = True
                        debug_print(f"[DEBUG] Updated import_dir to: {new_directory}")
                        break
                
                # If import_dir wasn't found, add it after bridge_name with same indentation
                if not updated:
                    insert_index = len(lines)  # Default to end
                    leading_space = ""  # Default indentation
                    
                    for i, line in enumerate(lines):
                        if line.strip().startswith('bridge_name'):
                            insert_index = i + 1
                            # Use same leading whitespace as bridge_name line
                            leading_space = line[:len(line) - len(line.lstrip())]
                            break
                    
                    # For new lines, default to no quotes to match the original format
                    new_line = f'{leading_space}import_dir = {new_directory}'
                    lines.insert(insert_index, new_line)
                    debug_print(f"[DEBUG] Added new import_dir line: {new_directory}")
                
                # Update the text box
                self.project_text_edit.setPlainText('\n'.join(lines))
                
        except Exception as e:
            debug_print(f"[ERROR] Failed to update import_dir in text: {e}")
            import traceback
            traceback.print_exc()
    
    def _update_project_data_in_text_with_colors(self, text_content, updated_data):
        """Update project data in text content with colored formatting for imported values.
        - Replaces only the value (keeps any trailing # comment as-is)
        - HTML mode: injects purple 11pt span; preserves paragraph and any tags
        - Plain text mode: preserves quoting style of the original value
        """
        import re

        if not updated_data:
            return text_content

        # ---------- Helpers ----------
        def _to_str(v):
            # Convert to string; lists/tuples/dicts come out as Python literals, which matches your existing style.
            return str(v)

        # HTML detection (Qt rich text usually starts with <!DOCTYPE HTML> or <html>)
        is_html = text_content.lstrip().lower().startswith("<!doctype html") or text_content.lstrip().lower().startswith("<html")

        # ----------------------------------------------------------------------
        # PLAIN TEXT PATH
        # ----------------------------------------------------------------------
        if not is_html:
            # For each key, replace the value (up to # or end-of-line), preserving the comment.
            for key, value in updated_data.items():
                if value is None:
                    continue
                new_val = _to_str(value)

                # ^ or \n  +  optional indent + key  =  value(until # or EOL)  +  optional comment
                # We use a function to preserve the original quoting style if present.
                pattern = re.compile(
                    rf'(^|\n)(?P<prefix>[ \t]*{re.escape(key)}\s*=\s*)(?P<val>[^\n#]*?)(?P<comment>[ \t]*#.*)?(?=\r?\n|$)',
                    flags=re.IGNORECASE
                )

                def _repl(m):
                    prefix = m.group('prefix')
                    old_val = (m.group('val') or '').strip()
                    comment = m.group('comment') or ''
                    # Preserve quoting if the old value had quotes
                    had_quotes = (old_val.startswith('"') and old_val.endswith('"')) or (old_val.startswith("'") and old_val.endswith("'"))
                    if had_quotes:
                        return m.group(1) + f"{prefix}\"{new_val}\"{comment}"
                    else:
                        return m.group(1) + f"{prefix}{new_val}{comment}"

                new_text, n = pattern.subn(_repl, text_content, count=1)
                if n == 0:
                    # Key not found → append new line at the end
                    text_content = text_content.rstrip('\n') + f'\n{key} = "{new_val}"'
                else:
                    text_content = new_text

            return text_content

        # ----------------------------------------------------------------------
        # HTML (Qt Rich Text) PATH
        # ----------------------------------------------------------------------
        # Allow tags/nbsp between tokens
        SP = r'(?:\s|&nbsp;|<[^>]*>)*'
        # Build a pattern that matches:
        #   key [tags/spaces] = [tags/spaces] (VALUE)  stopping before either a '#' (optionally preceded by tags) OR the end of the paragraph </p>
        # We replace only the VALUE part.
        for key, value in updated_data.items():
            if value is None:
                continue
            new_val = _to_str(value)

            # Regex: (prefix up to and including '=')  (value non-greedily)  (?= tags* '#' OR tags* '</p>')
            pattern = re.compile(
                rf'({re.escape(key)}{SP}={SP})(?P<val>.*?)(?=(?:{SP}#|{SP}</p>))',
                flags=re.IGNORECASE | re.DOTALL
            )

            def _repl_html(m):
                prefix = m.group(1)
                old_val = m.group('val').strip()
                # Check if the original value was quoted and preserve that style
                had_quotes = (old_val.startswith('"') and old_val.endswith('"')) or (old_val.startswith("'") and old_val.endswith("'"))
                
                if had_quotes:
                    # Preserve quotes
                    colored = (
                        "<span style=\" font-family:'Consolas,Courier New,monospace'; "
                        "font-size:11pt; color:#aaaaff;\">"
                        f"\"{new_val}\""
                        "</span>"
                    )
                else:
                    # No quotes
                    colored = (
                        "<span style=\" font-family:'Consolas,Courier New,monospace'; "
                        "font-size:11pt; color:#aaaaff;\">"
                        f"{new_val}"
                        "</span>"
                    )
                return prefix + colored

            new_text, n = pattern.subn(_repl_html, text_content, count=1)
            if n == 0:
                # Key not found – append a new paragraph before </body
                # For new lines, default to no quotes to match the original format
                new_line = (
                    f'<p style=" margin:0; -qt-block-indent:0; text-indent:0px;">'
                    f'{key} = '
                    f'<span style=" font-family:\'Consolas,Courier New,monospace\'; font-size:11pt; color:#aaaaff;">'
                    f'{new_val}'
                    f'</span></p>'
                )
                # Try to insert before </body>, else just append
                if '</body>' in text_content.lower():
                    # Case-insensitive safe replace: find the exact closing tag
                    close_idx = text_content.lower().rfind('</body>')
                    text_content = text_content[:close_idx] + new_line + text_content[close_idx:]
                else:
                    text_content = text_content + new_line
            else:
                text_content = new_text

        return text_content

    ### not used def _load_complete_state_json(self, json_path: Path) -> Tuple[Optional[Bridge], Optional[ProjectContext]]:
        """
        Load a saved ORBIT 'complete_program_state' (or similar) JSON and
        apply project settings, CRS, geometry, safety zones, cross-section,
        and flight-route settings. Returns (Bridge, ProjectContext).
        """
        try:
            import json, numpy as np
            from ..models import Trajectory, Bridge

            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # ----- Pull sections (support both old/new keys) -----
            meta = data.get('metadata', {})
            proj = data.get('project_settings') or data.get('project_data') or {}
            geom = data.get('current_geometry') or data.get('bridge_data') or {}
            fr   = data.get('flight_route_settings') or {}

            bridge_name = proj.get('bridge_name') or data.get('bridge_name') or json_path.stem
            ground_elev = float(proj.get('ground_elevation', 0.0))

            # ----- Build ProjectContext -----
            ctx = None
            try:
                coord_info = data.get('coordinate_system') or {}
                sel_sys = coord_info.get('selected_system') or proj.get('coordinate_system')
                if sel_sys:
                    # Extract custom EPSG if system is custom
                    custom_epsg = None
                    if sel_sys == "custom":
                        # Try to get custom EPSG from coordinate info or project data
                        custom_epsg = coord_info.get('custom_epsg') or proj.get('epsg_code')
                        if custom_epsg:
                            custom_epsg = int(custom_epsg)

                    # Create context with coordinate system, vertical datum handled by heightStartingPoint
                    ctx = CoordinateSystemRegistry.create_project_context(sel_sys, 'ellipsoid', custom_epsg, ground_elev)
                    self.last_coord_system = sel_sys
                    if custom_epsg:
                        self.last_custom_epsg = custom_epsg
            except Exception as _:
                ctx = None

            if ctx is None:
                # Fallback to EPSG with ellipsoid height (vertical datum handled by heightStartingPoint)
                epsg = int(proj.get('epsg_code', 4326))
                ctx = ProjectContext.from_epsg(epsg, VerticalRef.ELLIPSOID, ground_elev)

            # ----- Build Bridge from geometry (accept 2D or 3D) -----
            traj_pts = geom.get('trajectory_points') or geom.get('trajectory') or []
            traj_arr = np.array(traj_pts, dtype=float) if traj_pts else np.empty((0, 3), dtype=float)

            # If only lat/lon (N×2), pad a zero z-column to make N×3
            if traj_arr.ndim == 2 and traj_arr.shape[0] > 0 and traj_arr.shape[1] == 2:
                zcol = np.zeros((traj_arr.shape[0], 1), dtype=float)
                traj_arr = np.hstack([traj_arr, zcol])

            # If shape is still not (N×3), fall back to empty trajectory to avoid crashing
            if traj_arr.ndim != 2 or (traj_arr.shape[1] not in (0, 3)):
                debug_print(f"[JSON-LOAD] Unexpected trajectory shape {traj_arr.shape}; using empty trajectory.")
                traj_arr = np.empty((0, 3), dtype=float)

            trajectory = Trajectory(traj_arr)
            bridge = Bridge(name=bridge_name, trajectory=trajectory, pillars=[], safety_zones=[])

            # ----- Apply to app (parent) if available -----
            app = self.parent
            if app:
                # Parsed data snapshot
                try:
                    if not hasattr(app, 'parsed_data') or not isinstance(getattr(app, 'parsed_data'), dict):
                        app.parsed_data = {}
                    app.parsed_data['project'] = proj
                    app.parsed_data['flight_routes'] = fr
                except Exception:
                    pass

                # Core geometry attrs used elsewhere
                try:
                    app.current_trajectory = traj_pts or []
                    app.current_pillars = geom.get('pillars', []) or []
                    app.current_safety_zones = geom.get('safety_zones', []) or geom.get('safety_zones_resolved', []) or []
                    app.current_zone_points = []
                except Exception:
                    pass

                # Cross-section (display is best-effort)
                cs_path = (data.get('bridge_model') or {}).get('cross_section_path') or geom.get('cross_section_path')
                cs_pts  = geom.get('cross_section_points') or (data.get('bridge_model') or {}).get('cross_section_points')
                if cs_pts is not None:
                    try:
                        app.crosssection_transformed_points = cs_pts
                    except Exception:
                        pass
                if cs_path:
                    try:
                        self._display_cross_section_image(Path(cs_path))
                    except Exception as e:
                        debug_print(f"[JSON-LOAD] Cross-section display skipped: {e}")

                # Optional: update the textboxes with loaded settings where keys exist
                if hasattr(app, 'update_textbox_variables'):
                    try:
                        app.update_textbox_variables("tab0_textEdit1_Photo", {
                            k: proj[k] for k in (
                                'bridge_name','project_dir_base','import_dir','epsg_code',
                                'ground_elevation','input_scale_meters','epsilonInput',
                                'coordinate_system'
                            ) if k in proj
                        })
                    except Exception:
                        pass
                    try:
                        app.update_textbox_variables("tab3_textEdit", fr)
                    except Exception:
                        pass

                # If you have a map updater:
                if hasattr(app, '_update_safety_zones_on_map'):
                    try:
                        app._update_safety_zones_on_map()
                    except Exception:
                        pass

            # Cache on loader
            self.project_data = proj
            self.flight_route_data = fr
            self.current_bridge = bridge
            self.current_context = ctx
            self.last_selected_file = json_path

            debug_print(f"[JSON-LOAD] Loaded complete state from: {json_path.name}")
            return bridge, ctx

        except Exception as e:
            debug_print(f"[JSON-LOAD] Failed to load JSON state: {e}")
            import traceback; traceback.print_exc()
            return None, None
   
    def _load_minimal_json(self, json_path: Path, context: Optional[ProjectContext]):
        """
        Minimal JSON import (TXT-equivalent) with heights:
        • trajectory: WGS84 → projected, Z from JSON or ground_elevation + fitted trajectory_heights
        • pillars:    WGS84 → projected, Z from JSON or ground_elevation (else 0)
        • keeps self.current_pillars as WGS84 dicts for downstream usage
        """
        import json
        import numpy as np
        from ..io.models import Trajectory, Bridge
        try:
            from ..io.models import Pillar
        except Exception:
            Pillar = None  # if your model name differs, import/construct accordingly

        # --- read JSON
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            debug_print(f"[JSON] Failed to read {json_path}: {e}")
            return None, context

        ps = (data.get("project_settings") or {})
        cg = (data.get("current_geometry") or {})
        bridge_name = ps.get("bridge_name", json_path.stem)

        raw_traj = cg.get("trajectory_points") or []
        raw_pillars = cg.get("pillars") or []

        # --- inputs for Z logic
        # prefer ground_elevation from parsed tab-0 (self.project_data), else from JSON, else 0
        try:
            ground_elev = float((self.project_data or {}).get("ground_elevation",
                            ps.get("ground_elevation", 0.0)))
        except Exception:
            ground_elev = 0.0

        # trajectory_heights: prefer JSON, else what’s in tab-0, else empty
        traj_h_src = ps.get("trajectory_heights")
        if traj_h_src is None:
            traj_h_src = (self.project_data or {}).get("trajectory_heights", [])
        try:
            traj_heights = [float(v) for v in (traj_h_src or [])]
        except Exception:
            traj_heights = []

        # --- helper to compute fitted heights (quadratic / linear / constant)
        def _fit_heights(n_points: int) -> np.ndarray:
            if n_points <= 0:
                return np.zeros(0)
            if not traj_heights:
                return np.zeros(n_points, dtype=float)

            M = len(traj_heights)
            x_sample = np.linspace(0.0, 1.0, M) if M > 1 else np.array([0.0])
            y_sample = np.asarray(traj_heights, dtype=float)
            x_target = np.linspace(0.0, 1.0, n_points) if n_points > 1 else np.array([0.0])

            if M >= 3:
                # quadratic fit
                try:
                    coeffs = np.polyfit(x_sample, y_sample, 2)
                    return np.polyval(coeffs, x_target)
                except Exception:
                    # fallback to linear on any numerical hiccup
                    return np.interp(x_target, x_sample, y_sample)
            elif M == 2:
                # linear interp
                return np.interp(x_target, x_sample, y_sample)
            else:
                # constant
                return np.full(n_points, y_sample[0], dtype=float)

        # --- project trajectory (JSON arrays are [lat, lon, (optional z)])
        traj_xy = []
        N = len(raw_traj)
        fitted = _fit_heights(N)

        def _extract_lat_lon_z(pt, idx):
            # return lat, lon, z_or_None
            if isinstance(pt, (list, tuple)):
                lat = float(pt[0]); lon = float(pt[1])
                zval = float(pt[2]) if len(pt) >= 3 else None
                return lat, lon, zval
            if isinstance(pt, dict):
                lat = float(pt.get("lat") or pt.get("latitude"))
                lon = float(pt.get("lon") or pt.get("lng") or pt.get("longitude"))
                zraw = pt.get("z") or pt.get("alt") or pt.get("height")
                zval = float(zraw) if zraw is not None else None
                return lat, lon, zval
            return None, None, None

        if context and hasattr(context, "wgs84_to_project"):
            for i, p in enumerate(raw_traj):
                lat, lon, zval = _extract_lat_lon_z(p, i)
                if lat is None or lon is None:
                    continue
                if zval is None:
                    # derive z from fitted heights + ground level ONLY when no original Z exists
                    zval = ground_elev + (fitted[i] if i < len(fitted) else 0.0)
                try:
                    x, y, z = context.wgs84_to_project(lon, lat, float(zval))
                except Exception:
                    x, y, z = lon, lat, float(zval)
                traj_xy.append([x, y, z])
        else:
            # no context yet → store lon/lat in x/y and keep derived z
            for i, p in enumerate(raw_traj):
                lat, lon, zval = _extract_lat_lon_z(p, i)
                if lat is None or lon is None:
                    continue
                if zval is None:
                    # derive z from fitted heights + ground level ONLY when no original Z exists
                    zval = ground_elev + (fitted[i] if i < len(fitted) else 0.0)
                traj_xy.append([lon, lat, float(zval)])

        traj_np = np.array(traj_xy, dtype=float) if traj_xy else np.empty((0, 3))

        # --- build Bridge (with original Z values for flight computations)
        # IMPORTANT: trajectory Z values are preserved as-is for flight calculations.
        # ground_elev is NOT applied to existing trajectory Z values - only used as fallback
        # when trajectory points lack Z coordinates, and for pillar visualization.
        bridge = Bridge(name=bridge_name, trajectory=Trajectory(traj_np), pillars=[], safety_zones=[])

        # --- pillars: keep WGS84 dicts + projected Pillar objects
        wgs_pillars = []
        proj_pillars = []

        for idx, pi in enumerate(raw_pillars, 1):
            # accept dicts {"id","lat","lon"(,"z")} or lists [lat, lon] or [lat,lon,z]
            if isinstance(pi, dict):
                pid = pi.get("id", f"P{idx}")
                lat = pi.get("lat") or pi.get("latitude")
                lon = pi.get("lon") or pi.get("lng") or pi.get("longitude")
                zraw = pi.get("z") or pi.get("alt") or pi.get("height")
            elif isinstance(pi, (list, tuple)) and len(pi) >= 2:
                pid = f"P{idx}"
                lat, lon = pi[0], pi[1]
                zraw = pi[2] if len(pi) >= 3 else None
            else:
                continue

            if lat is None or lon is None:
                continue

            lat = float(lat); lon = float(lon)
            # pillar Z: prefer provided, else ground, else 0
            if zraw is not None:
                try:
                    pz = float(zraw)
                except Exception:
                    pz = float(ground_elev)
            else:
                pz = float(ground_elev) if ground_elev is not None else 0.0

            wgs_pillars.append({"id": pid, "lat": lat, "lon": lon})

            if context and hasattr(context, "wgs84_to_project") and Pillar:
                try:
                    x, y, z = context.wgs84_to_project(lon, lat, pz)
                    proj_pillars.append(Pillar(id=pid, x=float(x), y=float(y), z=float(z)))
                except Exception as e:
                    debug_print(f"[JSON] Pillar projection failed for {pid}: {e}")
            else:
                # keep lon/lat as x/y when no context yet
                if Pillar:
                    proj_pillars.append(Pillar(id=pid, x=float(lon), y=float(lat), z=float(pz)))

        self.current_pillars = wgs_pillars
        if proj_pillars:
            bridge.pillars = proj_pillars

        # Populate project-CRS lists ONLY if we truly have project coords (i.e., a context)
        if hasattr(self, 'parent') and self.parent:
            if context and hasattr(context, "wgs84_to_project"):
                if traj_np.size > 0:
                    self.parent.trajectory_list = traj_np.tolist()
                    setattr(self.parent, "_crs_of_trajectory_list", "project")
                    debug_print(f"[JSON] Set trajectory_list with {len(traj_np)} points in PROJECT coordinates")

                if proj_pillars:
                    flat = [[p.x, p.y, p.z] for p in proj_pillars]
                    self.parent.pillars_list = [flat[i:i + 2] for i in range(0, len(flat), 2)]
                    setattr(self.parent, "_crs_of_pillars_list", "project")
                    debug_print(f"[JSON] Set pillars_list with {len(proj_pillars)} pillars in PROJECT coordinates")

            # Always set live WGS84 lists for the map
            wgs84_traj = []
            for p in raw_traj:
                lat, lon, _ = _extract_lat_lon_z(p, 0)
                if lat is not None and lon is not None:
                    wgs84_traj.append([lat, lon])
            if wgs84_traj:
                self.parent.current_trajectory = wgs84_traj
                debug_print(f"[JSON] Set current_trajectory with {len(wgs84_traj)} WGS84 points for map display")

            # WGS84 pillar dicts for map drawing
            self.parent.current_pillars = wgs_pillars

        # keep stored cross-section path if present; auto-finder will still run
        cs_path = (data.get("bridge_model") or {}).get("cross_section_path")
        if cs_path:
            self.current_crosssection_path = cs_path

        debug_print(f"[JSON] Minimal import with Z: traj={len(traj_np)} pillars={len(proj_pillars)} (ground={ground_elev}, heights={len(traj_heights)})")
        return bridge, context

    def _ensure_context_from_project_data(self, project_data) -> ProjectContext:
        """Return a ProjectContext using (1) last dialog choice if present, else (2) Tab-0 fallback."""
        # Prefer the CRS the user picked in the file dialog (if any)
        if getattr(self, 'last_coord_system', None):
            ground_elevation = float(project_data.get("ground_elevation", 0.0))
            custom_epsg = getattr(self, 'last_custom_epsg', None)
            # Use ellipsoid height, vertical datum handled by heightStartingPoint
            return CoordinateSystemRegistry.create_project_context(
                self.last_coord_system,
                'ellipsoid',
                custom_epsg,
                ground_elevation
            )
        # Fallback to Tab-0
        epsg_code = int(project_data.get("epsg_code", 4326))
        vertical_ref = str(project_data.get("vertical_reference", "AGL"))
        ground_elevation = float(project_data.get("ground_elevation", 0.0))
        # Always use ellipsoid height - vertical datum handled by heightStartingPoint
        return ProjectContext.from_epsg(epsg_code, VerticalRef.ELLIPSOID, ground_elevation)
    
    def load_bridge_data(self) -> Tuple[Optional[Bridge], Optional[ProjectContext]]:
        """Load selected bridge data while honoring the CRS chosen in the file dialog.
        Order matters: (1) parse Tab-0 -> (2) select file (dialog sets CRS) -> (3) build context -> (4) load.
        Also carries the "Swap X/Y on import" option from the selection dialog into the import context.
        """
        # 0) Parse Tab-0 / Tab-3
        # Skip EPSG check since it will be determined by dialog selection or fallback
        project_data = self._parse_project_data(skip_epsg_check=True)
        if not project_data:
            return None, None
        self.project_data = project_data

        if self.flight_routes_text_edit:
            self.flight_route_data = self._parse_flight_route_data()

        bridge_name = project_data.get("bridge_name", "DefaultBridge")
        import_dir = Path(project_data.get("import_dir", "."))

        debug_print(f"[DEBUG] load_bridge_data – bridge={bridge_name} import_dir={import_dir}")

        # 1) Find/select file *first* (dialog sets last_coord_system and swap XY)
        bridge_file = self._find_and_select_bridge_file(import_dir, project_data)
        if bridge_file:
            debug_print(f"[DEBUG] Selected file: {bridge_file.name}")
        else:
            debug_print("[DEBUG] No file selected/found; will create empty bridge.")

        # 2) Build context *after* selection so dialog choice wins
        #    (If no dialog choice, fall back to Tab-0 epsg_code.)
        context: Optional[ProjectContext] = None
        # Try dialog selections first
        coord_key = getattr(self, 'last_coord_system', None)
        ground_elevation = float(project_data.get("ground_elevation", 0.0))

        if coord_key:
            debug_print(f"[DEBUG] Using dialog CRS: {coord_key}")
            custom_epsg = getattr(self, 'last_custom_epsg', None)
            if coord_key == "custom" and custom_epsg:
                debug_print(f"[DEBUG] Using custom EPSG: {custom_epsg}")
            # Use ellipsoid height, vertical datum handled by heightStartingPoint
            context = CoordinateSystemRegistry.create_project_context(coord_key, 'ellipsoid', custom_epsg, ground_elevation)
            # If Tab-0 had no epsg_code, backfill it (in-memory) from registry so downstream code can use it
            try:
                info = CoordinateSystemRegistry.get_system_info(coord_key) or {}
                epsg_from_dialog = int(info.get('epsg') or info.get('EPSG'))
                if 'epsg_code' not in self.project_data or self.project_data.get('epsg_code') in (None, '', 0):
                    self.project_data['epsg_code'] = epsg_from_dialog
                    debug_print(f"[DEBUG] Backfilled epsg_code from dialog mapping: {epsg_from_dialog}")
            except Exception:
                pass
        else:
            # Fallback to Tab-0
            epsg_code = int(project_data.get("epsg_code", 4326))
            vertical_ref = str(project_data.get("vertical_reference", "AGL"))
            debug_print(f"[DEBUG] Using Tab-0 CRS: EPSG={epsg_code}, vertical={vertical_ref}")
            # Always use ellipsoid height - vertical datum handled by heightStartingPoint
            context = ProjectContext.from_epsg(epsg_code, VerticalRef.ELLIPSOID, ground_elevation)

        # 2b) Inject "Swap X/Y on import" flag from file dialog into the context (default False)
        try:
            setattr(context, "swap_xy", bool(getattr(self, "last_swap_xy", False)))
            debug_print(f"[DEBUG] Context swap_xy={getattr(context, 'swap_xy', False)}")
        except Exception:
            pass

        # 3) JSON minimal path (behaves like TXT: traj + pillars; plus cross-section auto-search)
        if bridge_file and bridge_file.suffix.lower() == ".json":
            debug_print(f"[DEBUG] JSON minimal import: {bridge_file.name}")
            bridge, ctx2 = self._load_minimal_json(bridge_file, context)
            if bridge is None:
                QMessageBox.warning(self.parent, "Warning", f"Failed to load JSON: {bridge_file}")
                return None, None

            # Same cross-section auto-search that TXT path uses
            self._handle_cross_section_image(import_dir, bridge_name)

            self.current_bridge = bridge
            self.current_context = ctx2 or context
            self.last_selected_file = bridge_file
            # Geometry invariants for visualization stability
            self._geometry_space = "project"   # we always store geometry in project CRS
            try:
                # keep an EPSG tag if your context exposes it (optional, for debugging)
                self._geometry_epsg = int(getattr(self.current_context, "epsg", 0) or 0)
            except Exception:
                self._geometry_epsg = None

            return bridge, (ctx2 or context)

        # 4) Non-JSON: run cross-section finder, then import via loaders
        self._handle_cross_section_image(import_dir, bridge_name)

        if bridge_file:
            try:
                # Determine input_epsg for importer (prefer dialog CRS mapping; fallback to Tab-0)
                input_epsg: Optional[int] = None
                if coord_key:
                    if coord_key == "custom":
                        # For custom EPSG, use the user-entered value
                        custom_epsg = getattr(self, 'last_custom_epsg', None)
                        if custom_epsg:
                            input_epsg = custom_epsg
                            debug_print(f"[DEBUG] Using custom input_epsg: {input_epsg}")
                    else:
                        info = CoordinateSystemRegistry.get_system_info(coord_key) or {}
                        try:
                            input_epsg = int(info.get('epsg') or info.get('EPSG') or 0) or None
                        except Exception:
                            input_epsg = None
                if input_epsg is None:
                    input_epsg = int(self.project_data.get("epsg_code", 4326))
                    debug_print(f"[DEBUG] (fallback) input_epsg from Tab-0: {input_epsg}")

                # Diagnostics: importer reprojection vs identity
                target_epsg: Optional[int] = None
                try:
                    if hasattr(context, 'epsg') and context.epsg:
                        target_epsg = int(context.epsg)
                    elif hasattr(context, 'crs') and hasattr(context.crs, 'to_epsg'):
                        te = context.crs.to_epsg()
                        target_epsg = int(te) if te else None
                except Exception:
                    pass

                if target_epsg is not None:
                    msg = "identity" if input_epsg == target_epsg else f"reprojection {input_epsg} → {target_epsg}"
                    debug_print(f"[DEBUG] Importer: {msg}")
                else:
                    debug_print(f"[DEBUG] Importer: input_epsg={input_epsg}, target EPSG unknown.")

                # Load via importer
                bridge = load_bridge(bridge_file, context, input_epsg)
                bridge.name = bridge_name
                self.last_selected_file = bridge_file
                debug_print(f"[DEBUG] Loaded {bridge_file.name} as '{bridge_name}'")

            except Exception as e:
                QMessageBox.warning(self.parent, "Error", f"Failed to load {bridge_file}: {str(e)}")
                return None, None
        else:
            # No file → still return a valid empty project
            parent_dir = import_dir.parent
            if not parent_dir.exists():
                parent_dir.mkdir(parents=True, exist_ok=True)
            bridge = self._create_empty_bridge(bridge_name)
            debug_print(f"[DEBUG] No data source found. Created empty bridge '{bridge_name}'")

        # 5) Cache + return
        self.current_bridge = bridge
        self.current_context = context
        return bridge, context
    def _parse_project_data(self, skip_epsg_check: bool = False) -> Optional[dict]:
        """Parse project data (Tab-0 textbox) into a dict.
        Missing keys are filled from default_values.json via default_loader.DEFAULTS.
        No hard-coded literals remain in this function.

        Args:
            skip_epsg_check: If True, skip checking for epsg_code as required field
                           (useful when EPSG will be determined by dialog selection)
        """
        try:
            # Check if project_text_edit is available
            if not self.project_text_edit:
                debug_print("[DEBUG] No project text edit available")
                return None
            
            text_content = self.project_text_edit.toPlainText().strip()
            if not text_content:
                debug_print("[DEBUG] Project text is empty")
                QMessageBox.warning(self.parent, "Warning", 
                                  "Project data is empty. Please fill in project details.")
                return None

            # Use the central parser from orbit.data_parser
            try:
                parsed_data = parse_text_boxes(text_content)["project"]
                debug_print(f"[DEBUG] Parsed project data using central parser: {list(parsed_data.keys())}")
                
                # Check for required fields
                missing_fields = []
                required_fields = ["bridge_name", "import_dir"]
                if not skip_epsg_check:
                    required_fields.append("epsg_code")

                for _req in required_fields:
                    if _req not in parsed_data:
                        missing_fields.append(_req)
                        debug_print(f"[ERROR] Required project field '{_req}' missing in Tab-0 input.")

                if missing_fields:
                    debug_print(f"[WARNING] Missing required fields: {missing_fields}")
                    # Don't return None for missing fields, let the calling code handle it
                
                return parsed_data
                
            except Exception as parse_error:
                debug_print(f"[ERROR] Failed to parse project data with central parser: {parse_error}")
                # Fallback to manual parsing if central parser fails
                return self._fallback_parse_project_data(text_content)
            
        except Exception as e:
            debug_print(f"[ERROR] Failed to get project text content: {e}")
            QMessageBox.warning(self.parent, "Error", f"Failed to parse project data: {str(e)}")
            return None
    
    def _fallback_parse_project_data(self, text_content: str) -> Optional[dict]:
        """Fallback manual parsing if the central parser fails."""
        try:
            parsed_data = {}
            
            # Parse each line
            for line in text_content.split('\n'):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                if '=' in line:
                    try:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"\'')
                        
                        # Remove comments from value (everything after #)
                        if '#' in value:
                            value = value.split('#')[0].strip()
                        
                        # Handle comma-separated values on same line
                        if ',' in value and key in ['input_scale_meters', 'bridge_width']:
                            # Parse "input_scale_meters = 17.27, bridge_width = 17.27"
                            parts = value.split(',')
                            for part in parts:
                                if '=' in part:
                                    sub_key, sub_value = part.split('=', 1)
                                    sub_key = sub_key.strip()
                                    sub_value = sub_value.strip()
                                    
                                    # Convert appropriate values
                                    if sub_key in ['epsg_code']:
                                        parsed_data[sub_key] = int(sub_value)
                                    elif sub_key in ['ground_elevation', 'input_scale_meters', 'bridge_width', 'epsilonInput']:
                                        parsed_data[sub_key] = float(sub_value)
                                    else:
                                        parsed_data[sub_key] = sub_value
                                else:
                                    # Use first part as the value for the original key
                                    first_value = parts[0].strip()
                                    if key in ['epsg_code']:
                                        parsed_data[key] = int(first_value)
                                    elif key in ['ground_elevation', 'input_scale_meters', 'bridge_width', 'epsilonInput']:
                                        parsed_data[key] = float(first_value)
                                    else:
                                        parsed_data[key] = first_value
                                    break
                        else:
                            # Handle single values
                            if key in ['epsg_code']:
                                parsed_data[key] = int(value)
                            elif key in ['ground_elevation', 'input_scale_meters', 'bridge_width', 'epsilonInput']:
                                parsed_data[key] = float(value)
                            else:
                                parsed_data[key] = value
                    except (ValueError, IndexError) as e:
                        debug_print(f"[WARNING] Could not parse line '{line}': {e}")
                        continue
            
            debug_print(f"[DEBUG] Fallback parsed project data: {list(parsed_data.keys())}")
            return parsed_data
            
        except Exception as e:
            error_debug_print(f"[ERROR] Fallback parsing failed: {e}")
            return None
    
    def _parse_flight_route_data(self) -> Dict[str, Any]:
        """Parse flight-route textbox via the central orbit.data_parser module."""
        try:
            if not self.flight_routes_text_edit:
                return {}
                
            raw = self.flight_routes_text_edit.toPlainText()
            if not raw.strip():
                debug_print("[ERROR] Flight-route textbox is empty.")
                return {}
            return parse_text_boxes("", raw)["flight_routes"]  # central parser

            
        except Exception as e:
            debug_print(f"[WARNING] Failed to parse flight route data: {e}")
            return {}
    
    def get_flight_route_setting(self, key: str, default=None):
        """Get a specific flight route setting."""
        return self.flight_route_data.get(key, default)
    
    def get_project_setting(self, key: str, default=None):
        """Get a specific project setting."""
        return self.project_data.get(key, default)
    
    def _find_and_select_bridge_file(self, search_dir: Path, project_data: dict) -> Optional[Path]:
        """Search for bridge data files and handle multiple file selection."""
        if not search_dir.exists():
            debug_print(f"[DEBUG] Search directory does not exist: {search_dir}")
            return None

        bridge_name = project_data.get("bridge_name", "DefaultBridge")

        # Include extensionless file and common text-ish extensions
        patterns = [
            f"{bridge_name}",          # exact filename, no extension
            f"{bridge_name}.*",        # any extension
        ]
        found_files: list[Path] = []

        debug_print(f"[DEBUG] Searching for files matching {patterns} in directory: {search_dir}")

        # Broader supported set (treat '' as text)
        known_exts = {'.xlsx', '.xls', '.kml', '.kmz', '.csv', '.txt', '.json'}
        text_like_exts = {'.txt', '.csv', '.dat', '.xyz', '.pts', '.tsv', ''}

        for pattern in patterns:
            for file_path in search_dir.glob(pattern):
                if file_path.is_file() and file_path not in found_files:
                    ext = file_path.suffix.lower()
                    if ext in known_exts or ext in text_like_exts:
                        found_files.append(file_path)

        # Debug
        for pattern in patterns:
            pattern_files = [f.name for f in search_dir.glob(pattern) if f.is_file()]
            debug_print(f"[DEBUG] Found {len(pattern_files)} file(s) with pattern '{pattern}': {pattern_files}")

        debug_print(f"[DEBUG] Total files found matching '{bridge_name}': {len(found_files)}")
        for f in found_files:
            debug_print(f"[DEBUG]   - {f.name}")

        if not found_files:
            debug_print(f"[DEBUG] No bridge data files found for '{bridge_name}' in {search_dir}")
            return None

        if len(found_files) == 1:
            single_file = found_files[0]
            ext = single_file.suffix.lower()
            # Text-like and JSON → need CRS selection (user may also toggle Swap X/Y)
            if ext in text_like_exts or ext == ".json":
                debug_print("[DEBUG] Single text-like/JSON file found – showing CRS selection dialog …")
                return self._show_file_selection_dialog(found_files, bridge_name)

            debug_print(f"[DEBUG] Single file found: {single_file.name}")
            return single_file

        # Multiple files → show selection dialog
        debug_print(f"Found {len(found_files)} files with bridge name: {[f.name for f in found_files]}")
        return self._show_file_selection_dialog(found_files, bridge_name)
    def _show_file_selection_dialog(self, files: List[Path], bridge_name: str) -> Optional[Path]:
        """Show enhanced file selection dialog with coordinate system options"""
        try:
            dialog = FileSelectionDialog(
                self.parent, files, bridge_name,
                last_coord_system=getattr(self, 'last_coord_system', None),
                last_swap_xy=getattr(self, 'last_swap_xy', False)
            )
            if hasattr(self, 'last_coord_system') and self.last_coord_system:
                dialog.last_coord_system = self.last_coord_system

            if dialog.exec() == QDialog.Accepted:
                selected_file = dialog.selected_file
                selected_coord_system = dialog.selected_coordinate_system
                selected_custom_epsg = getattr(dialog, 'selected_custom_epsg', None)

                # Store selections for later use in context creation
                self.last_coord_system = selected_coord_system
                if selected_custom_epsg is not None:
                    self.last_custom_epsg = selected_custom_epsg

                # NEW: remember swap XY preference
                self.last_swap_xy = bool(getattr(dialog, 'selected_swap_xy', False))
                debug_print(f"Selected file: {selected_file}")
                debug_print(f"Selected coordinate system: {selected_coord_system}")
                if selected_custom_epsg is not None:
                    debug_print(f"Selected custom EPSG: {selected_custom_epsg}")
                debug_print(f"[FILE_DIALOG] Swap X/Y: {self.last_swap_xy}")

                return selected_file
            else:
                debug_print("File selection cancelled by user")
                return None

        except Exception as e:
            error_debug_print(f"Error in file selection dialog: {e}")
            if files:
                debug_print(f"Using fallback selection: {files[0].name}")
                return files[0]
            return None
    def get_user_coordinate_preferences(self) -> str:
        """Get the coordinate system preferences selected by the user."""
        coord_sys = getattr(self, '_user_coordinate_system', 'custom')
        return coord_sys
    
    def _create_empty_bridge(self, name: str) -> Bridge:
        """Create an empty bridge structure for new projects."""
        from ..io.models import Trajectory
        import numpy as np
        
        # Create minimal trajectory (user will draw this)
        empty_traj = Trajectory(np.empty((0, 3)))
        return Bridge(name=name, trajectory=empty_traj, pillars=[], safety_zones=[])
    
    def _handle_cross_section_image(self, input_dir: Path, bridge_name: str):
        """Search for cross-section image and handle template selection if not found."""
        debug_print(f"[DEBUG] _handle_cross_section_image called with dir: {input_dir}, bridge: {bridge_name}")
        
        if not self.cross_section_view:
            debug_print("[DEBUG] No cross_section_view available, skipping cross-section handling")
            return
        
        # Search for cross-section images
        cross_section_patterns = [
            f"{bridge_name}_crosssection.*",
            f"{bridge_name}_cross_section.*",
            "crosssection.*",
            "cross_section.*"
        ]
        
        cross_section_files = []
        if input_dir.exists():
            for pattern in cross_section_patterns:
                cross_section_files.extend(input_dir.glob(pattern))
        
        # Filter for image files
        image_extensions = {'.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.svg'}
        cross_section_images = [f for f in cross_section_files 
                               if f.suffix.lower() in image_extensions]
        
        debug_print(f"[DEBUG] Found {len(cross_section_images)} cross-section images: {[f.name for f in cross_section_images]}")
        
        if cross_section_images:
            # Use the first found image
            debug_print(f"[DEBUG] Displaying cross-section image: {cross_section_images[0]}")
            self._display_cross_section_image(cross_section_images[0])
        else:
            # Show template selection buttons
            debug_print("[DEBUG] No cross-section images found, showing templates")
            self._show_cross_section_templates()
    
    def _display_cross_section_image(self, image_path: Path):
        """Display a cross-section image in the graphics view and perform 2D shape analysis."""
        try:
            # Validate input
            if not image_path or not isinstance(image_path, Path):
                error_debug_print(f"[ERROR] Invalid image path: {image_path}")
                return
            
            if not image_path.exists():
                error_debug_print(f"[ERROR] Image file does not exist: {image_path}")
                return
            
            if not image_path.is_file():
                error_debug_print(f"[ERROR] Image path is not a file: {image_path}")
                return
            
            # Check if cross_section_view is available
            if not self.cross_section_view:
                debug_print("[WARNING] Cross-section view not available")
                return
            
            # Store the current cross-section path
            self.current_crosssection_path = str(image_path)
            debug_print(f"[DEBUG] Stored cross-section path: {self.current_crosssection_path}")
            
            # Load and validate the image
            try:
                pixmap = QPixmap(str(image_path))
                if pixmap.isNull():
                    debug_print(f"[ERROR] Failed to load image: {image_path}")
                    return
                
                debug_print(f"[DEBUG] Successfully loaded image: {image_path.name} ({pixmap.width()}x{pixmap.height()})")
                
            except Exception as e:
                debug_print(f"[ERROR] Failed to load image with QPixmap: {e}")
                return
            
            # Create and set the scene
            try:
                scene = QGraphicsScene()
                scene.addPixmap(pixmap)
                self.cross_section_view.setScene(scene)
                self.cross_section_view.fitInView(scene.itemsBoundingRect(), Qt.KeepAspectRatio)
                debug_print(f"[DEBUG] Cross-section image displayed: {image_path.name}")
                
            except Exception as e:
                error_debug_print(f"[ERROR] Failed to set scene: {e}")
                return
            
            # Perform 2D shape analysis (with error handling)
            try:
                self._perform_cross_section_analysis(image_path)
            except Exception as e:
                debug_print(f"[WARNING] Cross-section analysis failed (non-critical): {e}")
                # Continue without analysis - the image is still displayed
            
        except Exception as e:
            error_debug_print(f"[ERROR] Error displaying cross-section image: {e}")
            import traceback
            traceback.print_exc()
    
    def _perform_cross_section_analysis(self, image_path: Path):
        """Perform 2D shape analysis on the cross-section image."""
        try:
            # Store the current cross-section path for consistency
            self.current_crosssection_path = str(image_path)
            debug_print(f"[DEBUG] Stored cross-section path in data loader: {self.current_crosssection_path}")
            
            # Get project parameters
            # Skip EPSG check since it should already be properly set during bridge loading
            project_data = self._parse_project_data(skip_epsg_check=True)
            
            # Handle case where no project data is available (template selection scenario)
            if not project_data:
                debug_print("[DEBUG] No project data available for cross-section analysis - using defaults")
                # Use default values when no project data is available
                input_scale_meters = 17.27  # Default value
                epsilon_input = 0.003  # Default value
            else:
                input_scale_meters = project_data.get('input_scale_meters')
                epsilon_input = project_data.get('epsilonInput', 0.003)
                
                # Validate that required parameters are available
                if input_scale_meters is None:
                    debug_print("[ERROR] input_scale_meters not found in project data - using default")
                    input_scale_meters = 17.27  # Default value
            
            input_scale_meters = float(input_scale_meters)
            debug_print(f"[DEBUG] Using input_scale_meters: {input_scale_meters}")
            debug_print(f"[DEBUG] Using epsilonInput: {epsilon_input}")
            
            debug_print(f"[DEBUG] Starting cross-section analysis with scale={input_scale_meters}m, epsilon={epsilon_input}")
            
            # Import the cross section analysis function
            import sys
            from pathlib import Path
            

            # Try to import cross-section analysis module
            process_crosssection_image = None
            try:
                # Import the cross-section analysis function (try relative import first)
                debug_print("[DEBUG] Attempting to import cross-section analysis module...")
                from .cross_section_analysis import process_crosssection_image
                debug_print("[DEBUG] Successfully imported cross-section analysis module (relative)")
            except ImportError as e:
                debug_print(f"[DEBUG] Relative import failed: {e}")
                try:
                    # Try absolute import as fallback
                    debug_print("[DEBUG] Trying absolute import...")
                    from ..gui.cross_section_analysis import process_crosssection_image
                    debug_print("[DEBUG] Successfully imported cross-section analysis module (absolute)")
                except ImportError as e2:
                    debug_print(f"[DEBUG] Absolute import also failed: {e2}")
                    debug_print("[DEBUG] Cross-section analysis module not found - continuing with basic image display only")
                    process_crosssection_image = None

            # Only perform analysis if the module was successfully imported
            if process_crosssection_image is not None:
                try:
                    # Process the cross section image
                    processed_image, transformed_points = process_crosssection_image(
                        str(image_path), input_scale_meters, epsilon_input
                    )

                    # Check if the processing was successful
                    if processed_image is None or transformed_points is None:
                        debug_print("[DEBUG] Cross-section analysis returned None values")
                        debug_print("[DEBUG] Continuing with basic image display")
                        return

                    # Store the processed data for later use
                    self.processed_crosssection_image = processed_image
                    self.crosssection_transformed_points = transformed_points

                    # Compute bridge_width from the maximum distance across the cross-section
                    bridge_width = calculate_maximum_width(transformed_points)
                    debug_print(f"[DEBUG] Computed bridge_width from cross-section: {bridge_width:.3f}m")

                    # Store the computed bridge_width in parsed data for use by flight planners
                    if not hasattr(self, 'parsed_data'):
                        self.parsed_data = {}
                    if 'project' not in self.parsed_data:
                        self.parsed_data['project'] = {}

                    self.parsed_data['project']['bridge_width'] = bridge_width
                    debug_print(f"[DEBUG] Stored bridge_width in parsed_data: {self.parsed_data['project']['bridge_width']}")

                    debug_print(f"[DEBUG] Cross-section analysis completed:")
                    debug_print(f"[DEBUG] Found {len(transformed_points)} contour points")
                    debug_print(f"[DEBUG] 2D shape points: {transformed_points.tolist()}")

                    # Check if processed_image has the expected shape attribute
                    if processed_image is not None and hasattr(processed_image, 'shape'):
                        # Convert OpenCV image to QPixmap and update display
                        import cv2
                        from PySide6.QtGui import QImage
                        
                        height, width, channel = processed_image.shape
                        bytes_per_line = 3 * width
                        q_image = QImage(processed_image.data, width, height, bytes_per_line, QImage.Format_RGB888).rgbSwapped()
                        processed_pixmap = QPixmap.fromImage(q_image)
                        
                        # Check if cross_section_view exists before using it
                        if hasattr(self, 'cross_section_view') and self.cross_section_view is not None:
                            scene = QGraphicsScene()
                            scene.addPixmap(processed_pixmap)
                            self.cross_section_view.setScene(scene)
                            self.cross_section_view.fitInView(scene.itemsBoundingRect(), Qt.KeepAspectRatio)
                            debug_print(f"[DEBUG] Updated display with processed image (with measurements)")
                        else:
                            debug_print(f"[DEBUG] Cross-section view not available for processed image display")
                            # Store the processed data for later use when the view becomes available
                            self.pending_processed_image = processed_pixmap
                
                except Exception as e:
                    debug_print(f"[DEBUG] Error in cross-section analysis: {e}")
                    debug_print("[DEBUG] Continuing with basic image display")
            else:
                debug_print("[DEBUG] Cross-section analysis not available - using basic image display only")
        
        except Exception as e:
            debug_print(f"[DEBUG] Error in cross-section analysis: {e}")
            debug_print("[DEBUG] Continuing with basic image display")
            debug_print(f"[DEBUG] Error in cross-section analysis setup: {e}")

    def _display_pending_processed_image(self):
        """Display any pending processed image if the cross-section view is now available."""
        if (hasattr(self, 'pending_processed_image') and
            hasattr(self, 'cross_section_view') and
            self.cross_section_view is not None):
            try:
                scene = QGraphicsScene()
                scene.addPixmap(self.pending_processed_image)
                self.cross_section_view.setScene(scene)
                self.cross_section_view.fitInView(scene.itemsBoundingRect(), Qt.KeepAspectRatio)
                debug_print("[DEBUG] Displayed pending processed image")
                # Clear the pending image
                delattr(self, 'pending_processed_image')
            except Exception as e:
                debug_print(f"[DEBUG] Error displaying pending processed image: {e}")
            debug_print("[DEBUG] Continuing with basic image display")
    
    def _show_cross_section_templates(self):
        """Show template selection buttons in the graphics view when no cross-section image is found."""
        # Get paths to template images
        resources_dir = Path(__file__).parent.parent / "resources"
        i_girder_template = resources_dir / "crosssection_template_I-girder.png"
        box_template = resources_dir / "crosssection_template_box.png"
        
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
            i_girder_btn.clicked.connect(lambda: self._select_template(i_girder_template))
            button_layout.addWidget(i_girder_btn)
        
        # Box girder button  
        if box_template.exists():
            box_btn = QPushButton("Box Girder Template")
            box_btn.setFixedSize(150, 40)
            box_btn.clicked.connect(lambda: self._select_template(box_template))
            button_layout.addWidget(box_btn)
        
        layout.addLayout(button_layout)
        
        # Add some spacing
        layout.addStretch()
        
        widget.setFixedSize(400, 150)
        
        # Add widget to scene
        scene.addWidget(widget)
        self.cross_section_view.setScene(scene)
        self.cross_section_view.fitInView(scene.itemsBoundingRect(), Qt.KeepAspectRatio)
    
    def _select_template(self, template_path: Path):
        """Handle template selection - display the template and optionally copy to project."""
        # Display the selected template
        try:
            self._display_cross_section_image(template_path)
            self._copy_template_to_project(template_path)
            self.current_crosssection_path = str(template_path)
            self._perform_cross_section_analysis(template_path)
        except Exception as e:
            debug_print(f"[DEBUG] Cross-section analysis failed for template (non-critical): {e}")
                # Continue without analysis - the template is still displayed
    
    def _copy_template_to_project(self, template_path: Path):
        """Copy the selected template to the project's input directory (minimal version)."""
        from pathlib import Path
        import shutil
        
        try:
            debug_print(f"[COPY] Start: {template_path}")

            # Project data (fall back to sane defaults)
            project_data = self._parse_project_data(skip_epsg_check=True) or {}
            bridge_name = project_data.get("bridge_name") or "DefaultBridge"
            import_dir = Path(project_data.get("import_dir") or ".")

            # Ensure target directory exists and is a directory
            import_dir.mkdir(parents=True, exist_ok=True)
            if not import_dir.is_dir():
                raise NotADirectoryError(f"Import directory is not a directory: {import_dir}")

            # Validate source
            if not template_path.exists() or not template_path.is_file():
                raise FileNotFoundError(f"Template file not found or not a file: {template_path}")

            # Destination
            sanitized = self._sanitize_filename(bridge_name) or "DefaultBridge"
            dest_path = import_dir / f"{sanitized}_crosssection{template_path.suffix}"

            # Copy
            shutil.copy2(template_path, dest_path)
            self.current_crosssection_path = str(dest_path)

            debug_print(f"[COPY] Done -> {dest_path}")

        except Exception as e:
            # On any failure, keep using the original template and report the error.
            self.current_crosssection_path = str(template_path)

            debug_print(f"[ERROR] Template copy failed: {e}")
    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize a filename by removing or replacing invalid characters.
        
        Args:
            filename: The original filename to sanitize
            
        Returns:
            A sanitized filename safe for use on Windows and other operating systems
        """
        import re
        import os
        
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

    def _setup_project_structure(
        self,
        project_data: dict,
        *,
        write_back_to_text: bool = False,          # do NOT rewrite the textbox unless True
        pin_import_dir_to_project: bool = False,   # if True, project_data["import_dir"] := <project>/01_Input
        existing_context: "ProjectContext" | None = None,  # NEW: allow caller to supply a context
        build_context: bool = True                                # NEW: skip building a new one when False
    ) -> "ProjectContext | None":
        """Set up project directory structure and (optionally) create/reuse ProjectContext.

        Returns the context to use (existing or newly built), or None on failure.
        """
        try:
            from ..io.context import ProjectContext, VerticalRef
            import shutil
            from datetime import datetime
            from pathlib import Path

            # ---------- 1) Resolve inputs and sanitize project folder name ----------
            bridge_name = project_data.get("bridge_name", "DefaultBridge")
            project_dir_base = Path(project_data.get("project_dir_base", "."))
            user_import_dir = Path(project_data.get("import_dir", "."))  # preserve user's source folder

            sanitized_bridge_name = self._sanitize_filename(bridge_name) if hasattr(self, "_sanitize_filename") else bridge_name

            # ---------- 2) Create project structure ----------
            project_dir = project_dir_base / sanitized_bridge_name
            project_input_dir = project_dir / "01_Input"
            project_dir.mkdir(parents=True, exist_ok=True)
            project_input_dir.mkdir(parents=True, exist_ok=True)
            debug_print(f"[STRUCTURE] Project root: {project_dir}")
            debug_print(f"[STRUCTURE] Input folder: {project_input_dir}")

            # ---------- 3) Archive existing *files* in 01_Input (keep subfolders) ----------
            existing_files = [f for f in project_input_dir.iterdir() if f.is_file()]
            if existing_files:
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                archive_dir = project_input_dir / f"archive_{ts}"
                archive_dir.mkdir(parents=True, exist_ok=True)
                for f in existing_files:
                    shutil.move(str(f), str(archive_dir / f.name))
                debug_print(f"[ARCHIVE] Moved {len(existing_files)} files → {archive_dir}")

            # ---------- 4) Copy relevant files from user's import_dir into 01_Input ----------
            copied_files = 0
            if user_import_dir.exists() and user_import_dir.is_dir() and user_import_dir != project_input_dir:
                debug_print(f"[COPY] From: {user_import_dir}")
                debug_print(f"[COPY]   To: {project_input_dir}")

                name_variants = {bridge_name, sanitized_bridge_name}
                for stem in name_variants:
                    for src in user_import_dir.glob(f"{stem}.*"):
                        if src.is_file():
                            shutil.copy2(src, project_input_dir / src.name)
                            copied_files += 1
                            debug_print(f"  • Copied: {src.name}")
                    for pattern in (f"{stem}_crosssection.*", f"{stem}_cross_section.*"):
                        for src in user_import_dir.glob(pattern):
                            if src.is_file():
                                shutil.copy2(src, project_input_dir / src.name)
                                copied_files += 1
                                debug_print(f"  • Copied cross-section: {src.name}")
            debug_print(f"[COPY] Total files copied: {copied_files}")

            # ---------- 5) Decide whether to pin import_dir ----------
            if pin_import_dir_to_project:
                project_data["import_dir"] = str(project_input_dir)
                debug_print(f"[IMPORT_DIR] Pinned import_dir → {project_input_dir}")
                if write_back_to_text:
                    if hasattr(self, "_update_import_directory_in_text"):
                        self._update_import_directory_in_text(str(project_input_dir))
                        debug_print("[TEXTBOX] Updated via _update_import_directory_in_text")
                    elif hasattr(self, "update_textbox_variables"):
                        self.update_textbox_variables("tab0_textEdit1_Photo", {"import_dir": str(project_input_dir)})
                        debug_print("[TEXTBOX] Updated via update_textbox_variables(import_dir)")
            else:
                debug_print(f"[IMPORT_DIR] Preserved user import_dir → {user_import_dir}")

            # ---------- 6) Context handling (NEW logic) ----------
            ctx = None
            if not build_context:
                # Caller told us to *not* build a new context
                ctx = existing_context
                debug_print("[CONTEXT] Skipping context build (build_context=False).")
            else:
                # Build a new context, unless caller already provided one (we reuse it)
                if existing_context is not None:
                    ctx = existing_context
                    debug_print("[CONTEXT] Reusing provided existing_context.")
                else:
                    epsg_code = project_data.get("epsg_code", 4326)
                    vertical_reference = str(project_data.get("vertical_reference", "AGL")).strip().lower()
                    # All vertical references now map to ellipsoid - handled by heightStartingPoint
                    vertical_ref = VerticalRef.ELLIPSOID
                    ground_elevation = float(project_data.get("ground_elevation", 0.0))
                    ctx = ProjectContext.from_epsg(epsg_code, vertical_ref, ground_elevation)
                    debug_print(f"[CONTEXT] Built new context EPSG:{epsg_code}, VerticalRef:{vertical_ref.name}, Ground:{ground_elevation}")


            return ctx

        except Exception as e:
            error_msg = str(e)
            if "Custom EPSG code must be provided" in error_msg:
                debug_print(f"[ERROR] Custom EPSG code is missing. Please ensure you entered a valid EPSG code when selecting 'Custom EPSG...'.")
            else:
                debug_print(f"[ERROR] Failed to setup project structure: {e}")
                import traceback; traceback.print_exc()
            return None

    def _save_project_configuration(self, project_dir: Path, project_data: dict):
        """Save project configuration to JSON file."""
        try:
            import json
            from datetime import datetime
            
            # Store current bridge and context data
            config = {
                "project_data": project_data,
                "created_at": datetime.now().isoformat(),
                "bridge_name": project_data.get("bridge_name"),
                "epsg_code": project_data.get("epsg_code"),
                "vertical_reference": project_data.get("vertical_reference"),
                "ground_elevation": project_data.get("ground_elevation", 0.0)
            }
            
            # Save bridge geometry if available
            if hasattr(self, 'current_bridge') and self.current_bridge:
                trajectory_points = []
                pillar_points = []
                abutment_points = []
                
                # Extract trajectory points
                if hasattr(self.current_bridge, 'trajectory') and self.current_bridge.trajectory.points.size > 0:
                    trajectory_points = self.current_bridge.trajectory.points.tolist()
                
                # Extract pillar points  
                if hasattr(self.current_bridge, 'pillars'):
                    pillar_points = [{"id": p.id, "x": p.x, "y": p.y, "z": p.z} for p in self.current_bridge.pillars]
                
                # Extract abutment points
                if hasattr(self.current_bridge, 'abutments'):
                    abutment_points = [{"id": a.id, "x": a.x, "y": a.y, "z": a.z} for a in self.current_bridge.abutments]
                
                config["geometry"] = {
                    "trajectory": trajectory_points,
                    "pillars": pillar_points,
                    "abutments": abutment_points
                }
                
                debug_print(f"[INFO] Saved component geometry – traj:{len(trajectory_points)} pillars:{len(pillar_points)} abut:{len(abutment_points)}")

            # Save to file
            config_file = project_dir / "project_config.json"
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)

            debug_print(f"Project configuration saved to: {config_file}")
            
        except Exception as e:
            debug_print(f"[ERROR] Failed to save project configuration: {e}")


class FileSelectionDialog(QDialog):
    """Enhanced file selection dialog with coordinate system options"""

    def _create_styled_message_box(self, icon, title, text):
        """Create a QMessageBox with consistent styling matching the dialog theme"""
        msg_box = QMessageBox(self)
        msg_box.setIcon(icon)
        msg_box.setWindowTitle(title)
        msg_box.setText(text)

        # Apply consistent styling to match the dialog theme
        msg_box.setStyleSheet("""
            QMessageBox {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1e3c72, stop:1 #2a5298);
                color: white;
                border-radius: 10px;
            }
            QMessageBox QLabel {
                color: white;
                font-size: 12px;
            }
            QMessageBox QPushButton {
                background-color: transparent;
                color: #4CAF50;
                border: 2px solid #4CAF50;
                border-radius: 22px;
                font-weight: bold;
                font-size: 12px;
                padding: 8px 16px;
                min-width: 80px;
            }
            QMessageBox QPushButton:hover {
                background-color: rgba(76, 175, 80, 0.1);
                border-color: #45a049;
                color: #45a049;
            }
            QMessageBox QPushButton:pressed {
                background-color: rgba(76, 175, 80, 0.2);
                border-color: #3d8b40;
                color: #3d8b40;
            }
        """)

        return msg_box

    def __init__(self, parent, files_list, bridge_name, last_coord_system=None, last_swap_xy=False):
        super().__init__(parent)
        self.setWindowTitle(f"Select Data Source for {bridge_name}")
        self.setMinimumSize(1000, 700)
        self.resize(1200, 800)
        self.setWindowState(Qt.WindowMaximized)  # Open fullscreen
        self.selected_file = None
        self.selected_coordinate_system = None
        self.selected_swap_xy = False
        self.files = files_list  # Store the original files list
        self.bridge_name = bridge_name  # Store bridge name
        self.files_data = []

        self.last_coord_system = last_coord_system
        self.last_swap_xy = last_swap_xy
        # Analyze files
        for file_path in files_list:
            file_data = self.analyze_file_for_dialog(file_path)
            self.files_data.append(file_data)
        
        self.setup_ui()
    

    def check_coordinate_columns(self, columns):
        """Check if DataFrame columns contain coordinate-like data"""
        coord_keywords = ['x', 'y', 'z', 'lat', 'lon', 'longitude', 'latitude', 'east', 'north', 'coordinate']
        columns_lower = [str(col).lower() for col in columns]
        
        coord_matches = sum(1 for keyword in coord_keywords 
                           for col in columns_lower 
                           if keyword in col)
        return coord_matches >= 2  # At least 2 coordinate-like columns
    
    def _is_numeric(self, value):
        """Check if a value is numeric"""
        try:
            float(value)
            return True
        except (ValueError, TypeError):
            return False
    

    def analyze_file_for_dialog(self, file_path: Path) -> dict:
        """Analyze a file for the selection dialog.
        Robust: treats many extensions as text; falls back to a tolerant numeric preview.
        """
        import re

        def _preview_text_numbers(lines, max_rows=200):
            float_re = re.compile(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?')
            rows = []
            for raw in lines:
                line = raw.strip()
                if not line:
                    continue
                if '#' in line:
                    line = line.split('#', 1)[0].strip()
                    if not line:
                        continue
                nums = [m.group(0) for m in float_re.finditer(line)]
                if len(nums) >= 2:
                    rows.append(", ".join(nums[:3]))
                if len(rows) >= max_rows:
                    break
            return rows

        file_data = {
            'path': file_path,
            'name': file_path.name,
            'error': None,
            'dataframes': [],
            'row_count': None,
        }

        ext = file_path.suffix.lower()

        # Treat these as "plain text" too
        text_like_exts = {'.txt', '.csv', '.dat', '.xyz', '.pts', '.tsv', '.list', ''}
        excel_exts = {'.xlsx', '.xls'}
        kml_exts = {'.kml', '.kmz'}
        json_exts = {'.json'}

        try:
            if ext in excel_exts:
                try:
                    all_sheets = pd.read_excel(file_path, sheet_name=None, nrows=5)
                    if "00_Input" not in all_sheets:
                        file_data['error'] = 'No sheet called "00_Input" found. Please check the template.xlsx file.'
                    else:
                        df = all_sheets["00_Input"]
                        with pd.option_context('display.max_rows', None, 'display.max_columns', None, 'display.width', 0):
                            preview_text = df.to_string(index=False) if not df.empty else "(empty sheet)"
                        file_data['dataframes'].append({
                            'sheet_name': "00_Input",
                            'total_rows': len(df),
                            'headers': list(df.columns),
                            'full_preview_text': preview_text,
                        })
                        file_data['row_count'] = len(df)
                except Exception as e:
                    file_data['error'] = f"Excel read error: {str(e)[:80]}..."

            elif ext in kml_exts:
                file_data['dataframes'].append({
                    'sheet_name': 'KML Data',
                    'total_rows': '?',
                    'headers': ['Longitude', 'Latitude', 'Altitude'],
                    'full_preview_text': '(Geographic coordinates from KML/KMZ file)',
                })
                file_data['row_count'] = None

            elif ext in json_exts:
                try:
                    import json
                    with open(file_path, 'r', encoding='utf-8') as f:
                        j = json.load(f)

                    ps = (j.get("project_settings") or {})
                    cg = (j.get("current_geometry") or {})
                    bname = ps.get("bridge_name", file_path.stem)
                    traj = cg.get("trajectory_points") or []
                    pillars = cg.get("pillars") or []

                    n_show = 8
                    traj_lines = []
                    for k, p in enumerate(traj[:n_show], 1):
                        if isinstance(p, (list, tuple)) and len(p) >= 2:
                            traj_lines.append(f"  {k:02d}: lat={float(p[0]):.8f}, lon={float(p[1]):.8f}")
                        elif isinstance(p, dict) and "lat" in p and ("lon" in p or "lng" in p):
                            lat = float(p["lat"])
                            lon = float(p.get("lon", p.get("lng")))
                            traj_lines.append(f"  {k:02d}: lat={lat:.8f}, lon={lon:.8f}")

                    pil_lines = []
                    for k, pi in enumerate(pillars[:n_show], 1):
                        if isinstance(pi, dict):
                            lat = pi.get("lat") or pi.get("latitude")
                            lon = pi.get("lon") or pi.get("lng") or pi.get("longitude")
                            pid = pi.get("id", f"P{k}")
                            if lat is not None and lon is not None:
                                pil_lines.append(f"  {pid}: lat={float(lat):.8f}, lon={float(lon):.8f}")
                        elif isinstance(pi, (list, tuple)) and len(pi) >= 2:
                            pil_lines.append(f"  P{k}: lat={float(pi[0]):.8f}, lon={float(pi[1]):.8f}")

                    preview_text = "\n".join([
                        f"JSON Overview: {bname}",
                        f"Trajectory points: {len(traj)}",
                        *(traj_lines if traj_lines else ["  (no trajectory points)"]),
                        "",
                        f"Pillars: {len(pillars)}",
                        *(pil_lines if pil_lines else ["  (no pillars)"]),
                    ])
                    file_data['dataframes'].append({
                        'sheet_name': 'JSON Overview',
                        'total_rows': len(traj),
                        'headers': ['lat', 'lon'],
                        'full_preview_text': preview_text,
                    })
                    file_data['row_count'] = len(traj)
                except Exception as e:
                    file_data['error'] = f"JSON read error: {str(e)[:80]}..."

            elif ext in text_like_exts:
                # Show the original file content for better preview
                try:
                    lines = file_path.read_text(encoding='utf-8', errors='ignore').splitlines()
                    # Limit to reasonable number of lines for display
                    max_lines = 100
                    if len(lines) > max_lines:
                        preview_lines = lines[:max_lines]
                        preview_lines.append(f"... ({len(lines) - max_lines} more lines)")
                    else:
                        preview_lines = lines

                    # Create left-aligned preview with line numbers
                    preview_text = ""
                    for i, line in enumerate(preview_lines, 1):
                        # Left-align the content and preserve original formatting
                        preview_text += f"{i:4d}: {line}\n"

                    file_data['dataframes'].append({
                        'sheet_name': f'Text File ({ext[1:].upper() or "TXT"})',
                        'total_rows': len(lines),
                        'headers': ['Line', 'Content'],
                        'full_preview_text': preview_text,
                    })
                    file_data['row_count'] = len(lines)
                except Exception as e:
                    file_data['error'] = f"Text read error: {str(e)[:80]}..."

            else:
                # Instead of blocking, treat unknown extensions as text and preview anyway
                try:
                    lines = file_path.read_text(encoding='utf-8', errors='ignore').splitlines()
                    # Limit to reasonable number of lines for display
                    max_lines = 100
                    if len(lines) > max_lines:
                        preview_lines = lines[:max_lines]
                        preview_lines.append(f"... ({len(lines) - max_lines} more lines)")
                    else:
                        preview_lines = lines

                    # Create left-aligned preview with line numbers
                    preview_text = ""
                    for i, line in enumerate(preview_lines, 1):
                        # Left-align the content and preserve original formatting
                        preview_text += f"{i:4d}: {line}\n"

                    file_data['dataframes'].append({
                        'sheet_name': f'Text File ({ext[1:].upper() or "TXT"})',
                        'total_rows': len(lines),
                        'headers': ['Line', 'Content'],
                        'full_preview_text': preview_text,
                    })
                    file_data['row_count'] = len(lines)
                except Exception as e:
                    file_data['error'] = f"Unsupported file type: {ext or '(no extension)'} — {str(e)[:80]}..."

            return file_data

        except Exception as e:
            return {
                'path': file_path,
                'name': file_path.name,
                'error': f"Analysis failed: {str(e)[:80]}...",
                'dataframes': [],
                'row_count': None,
            }

    def setup_ui(self):
    # Theme (unchanged)
        self.setStyleSheet("""
            QDialog {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1e3c72, stop:1 #2a5298);
                color: white;
            }
            QLabel { color: white; }
            QComboBox {
                background-color: rgba(255, 255, 255, 0.9);
                border: 2px solid #4CAF50;
                border-radius: 8px;
                padding: 8px;
                font-size: 12px;
                color: #333333;
            }
            QComboBox::drop-down { border: none; background: #4CAF50; border-radius: 4px; }
            QComboBox::down-arrow { image: none; border: 2px solid white; width: 6px; height: 6px; background: white; }
            QPushButton {
                background-color: #4CAF50; color: white; border: none; border-radius: 22px;
                font-weight: bold; font-size: 14px;
            }
            QPushButton:hover { background-color: #45a049; transform: translateY(-1px); }
            QPushButton:pressed { background-color: #3d8b40; transform: translateY(1px); }
            QRadioButton { color: white; font-weight: bold; font-size: 14px; spacing: 10px; }
            QRadioButton::indicator {
                width: 16px; height: 16px; border-radius: 8px; border: 2px solid white;
                background-color: rgba(255, 255, 255, 0.2);
            }
            QRadioButton::indicator:checked { background-color: #4CAF50; border: 2px solid white; }
            QRadioButton::indicator:hover { background-color: rgba(255, 255, 255, 0.4); }
        """)

        from PySide6.QtWidgets import QSizePolicy

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(30, 30, 30, 30)

        # Title
        title = QLabel(f"🚀 Select Data Source for: {self.bridge_name}")
        title.setStyleSheet("font-size: 20px; font-weight: bold; margin-bottom: 15px;")
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        # Split
        content_layout = QHBoxLayout()
        content_layout.setSpacing(30)

        # LEFT: files
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setSpacing(10)

        files_label = QLabel("📁 Available Files:")
        files_label.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px;")
        left_layout.addWidget(files_label)

        files_scroll = QScrollArea()
        files_scroll.setWidgetResizable(True)
        files_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        files_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        files_scroll.setStyleSheet("""
            QScrollArea { border: none; background-color: transparent; }
            QScrollBar:vertical {
                background-color: rgba(255, 255, 255, 0.1);
                width: 12px; border-radius: 6px;
            }
            QScrollBar::handle:vertical { background-color: #4CAF50; border-radius: 6px; min-height: 20px; }
            QScrollBar::handle:vertical:hover { background-color: #45a049; }
        """)

        files_container = QWidget()
        files_container_layout = QVBoxLayout(files_container)
        files_container_layout.setSpacing(10)

        self.file_buttons = QButtonGroup()

        for i, file_data in enumerate(self.files_data):
            file_widget = QWidget()
            file_widget.setStyleSheet("""
                QWidget {
                    background-color: rgba(255, 255, 255, 0.9);
                    border-radius: 10px;
                    margin: 5px 0px;
                    padding: 15px;
                }
            """)
            file_layout = QVBoxLayout(file_widget)
            file_layout.setSpacing(8)

            # Radio label: "name (x rows)" when available
            rows_suffix = ""
            rc = file_data.get('row_count')
            if isinstance(rc, int):
                rows_suffix = f" ({rc} rows)"

            radio = QRadioButton(f"📄 {file_data['name']}{rows_suffix}")
            radio.setCursor(Qt.PointingHandCursor)
            radio.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            # Hide dot + turn whole title bar green on hover/checked
            radio.setStyleSheet("""
                QRadioButton {
                    color: #333333;
                    font-size: 14px;
                    font-weight: bold;
                    background-color: rgba(0,0,0,0.04);
                    border-radius: 8px;
                    padding: 10px 12px;
                }
                QRadioButton:hover {
                    background-color: #45a049; /* green on hover */
                    color: white;
                }
                QRadioButton:checked {
                    background-color: #4CAF50; /* green when selected */
                    color: white;
                }
                QRadioButton::indicator { width: 0; height: 0; margin: 0; padding: 0; } /* hide the dot */
            """)
            self.file_buttons.addButton(radio, i)
            file_layout.addWidget(radio)
            if i == 0:
                radio.setChecked(True)

            if file_data['error']:
                error_label = QLabel(f"❌ {file_data['error']}")
                error_label.setStyleSheet("color: red; font-size: 11px;")
                file_layout.addWidget(error_label)
            else:
                # One scrollable, monospaced preview (headers + all rows)
                df_infos = file_data.get('dataframes') or []
                preview_text = df_infos[0].get('full_preview_text') if df_infos else "(no preview available)"

                preview = QTextEdit()
                preview.setReadOnly(True)
                preview.setLineWrapMode(QTextEdit.NoWrap)
                preview.setText(preview_text)
                preview.setMinimumHeight(240)
                preview.setStyleSheet("""
                    QTextEdit {
                        background-color: rgba(0,0,0,0.05);
                        border-radius: 6px;
                        padding: 8px;
                        color: #333333;
                        font-family: Consolas, "Courier New", monospace;
                        font-size: 12px;
                    }
                """)
                file_layout.addWidget(preview)

            files_container_layout.addWidget(file_widget)

        files_scroll.setWidget(files_container)
        left_layout.addWidget(files_scroll)

        # RIGHT: CRS + vertical datum (unchanged)
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setSpacing(15)

        coord_label = QLabel("🗺️ Coordinate System:")
        coord_label.setStyleSheet("font-size: 14px; font-weight: bold; margin-bottom: 10px;")
        right_layout.addWidget(coord_label)

        # Swap X/Y checkbox above coordinate system
        self.swap_xy_checkbox = QCheckBox("🔄 Swap X/Y coordinates on import")
        self.swap_xy_checkbox.setStyleSheet("""
            QCheckBox {
                color: white;
                font-size: 12px;
                font-weight: bold;
                padding: 8px;
                margin-bottom: 5px;
            }
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border: 2px solid #4CAF50;
                border-radius: 4px;
                background-color: rgba(255, 255, 255, 0.1);
            }
            QCheckBox::indicator:checked {
                background-color: #4CAF50;
                border: 2px solid #4CAF50;
            }
            QCheckBox::indicator:checked {
                image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTIiIGhlaWdodD0iMTIiIHZpZXdCb3g9IjAgMCAxMiAxMiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTEwIDNMOCA2TDQgOCIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiLz4KPC9zdmc+);
            }
        """)
        right_layout.addWidget(self.swap_xy_checkbox)

        # Set checkbox state from previous selection
        if hasattr(self, 'last_swap_xy') and self.last_swap_xy:
            self.swap_xy_checkbox.setChecked(True)
            debug_print(f"[FILE_DIALOG] Restoring previous swap X/Y setting: {self.last_swap_xy}")

        self.coord_combo = QComboBox()
        self.coord_combo.setMinimumHeight(40)

        coord_systems = CoordinateSystemRegistry.get_coordinate_systems()
        for key, display_name in coord_systems:
            self.coord_combo.addItem(display_name, key)

        default_coord = "custom"  # Default to Custom EPSG
        if hasattr(self, 'last_coord_system') and self.last_coord_system:
            default_coord = self.last_coord_system
            debug_print(f"[FILE_DIALOG] Using previous coordinate system: {default_coord}")
        else:
            debug_print(f"[FILE_DIALOG] Using default coordinate system: {default_coord}")

        default_index = self.coord_combo.findData(default_coord)
        if default_index >= 0:
            self.coord_combo.setCurrentIndex(default_index)
        else:
            lambert_index = self.coord_combo.findData("Lambert72")
            if lambert_index >= 0:
                self.coord_combo.setCurrentIndex(lambert_index)

        # Connect signal to show/hide custom EPSG input
        self.coord_combo.currentTextChanged.connect(self._on_coord_system_changed)

        right_layout.addWidget(self.coord_combo)

        # Custom EPSG input (hidden by default)
        self.custom_epsg_widget = QWidget()
        custom_layout = QHBoxLayout(self.custom_epsg_widget)
        custom_layout.setContentsMargins(0, 5, 0, 0)  # Small top margin to separate from combo

        custom_label = QLabel("Custom EPSG Code:")
        custom_label.setStyleSheet("font-size: 12px; font-weight: bold; color: white;")
        custom_layout.addWidget(custom_label)

        self.custom_epsg_input = QLineEdit()
        self.custom_epsg_input.setPlaceholderText("e.g. 31370 for Lambert72")
        self.custom_epsg_input.setMaximumWidth(150)
        self.custom_epsg_input.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 0.9);
                border: 2px solid #4CAF50;
                border-radius: 6px;
                padding: 6px;
                font-size: 12px;
                color: #333333;
            }
        """)
        custom_layout.addWidget(self.custom_epsg_input)

        custom_layout.addStretch()
        self.custom_epsg_widget.setVisible(False)
        right_layout.addWidget(self.custom_epsg_widget)

        # Show custom EPSG input if default is custom
        if default_coord == "custom":
            self.custom_epsg_widget.setVisible(True)


        right_layout.addStretch()

        content_layout.addWidget(left_widget, 6)
        content_layout.addWidget(right_widget, 4)
        main_layout.addLayout(content_layout)

        # Bottom buttons (unchanged)
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        button_layout.addStretch()

        cancel_btn = QPushButton("❌ Cancel")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setFixedSize(120, 45)
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336; color: white; border: none; border-radius: 22px;
                font-weight: bold; font-size: 14px;
            }
            QPushButton:hover { background-color: #da190b; }
        """)
        button_layout.addWidget(cancel_btn)

        select_btn = QPushButton("✅ Select")
        select_btn.clicked.connect(self.accept_selection)
        select_btn.setFixedSize(120, 45)
        select_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50; color: white; border: none; border-radius: 22px;
                font-weight: bold; font-size: 14px;
            }
            QPushButton:hover { background-color: #45a049; }
        """)
        button_layout.addWidget(select_btn)

        button_layout.addStretch()
        main_layout.addLayout(button_layout)

    def _on_coord_system_changed(self):
        """Handle coordinate system selection change to show/hide custom EPSG input"""
        current_data = self.coord_combo.currentData()
        is_custom = current_data == "custom"

        self.custom_epsg_widget.setVisible(is_custom)
        if is_custom:
            self.custom_epsg_input.setFocus()

    def accept_selection(self):
        """Handle the accept button click"""
        try:
            # Get selected file
            selected_button_id = self.file_buttons.checkedId()
            if selected_button_id >= 0:
                selected_file_data = self.files_data[selected_button_id]
                self.selected_file = selected_file_data['path']
            
            # Get coordinate system selection
            self.selected_coordinate_system = self.coord_combo.currentData()

            # Get swap X/Y checkbox state
            self.selected_swap_xy = self.swap_xy_checkbox.isChecked()

            debug_print(f"[FILE_DIALOG] User selected coordinate system: {self.selected_coordinate_system}")
            debug_print(f"[FILE_DIALOG] Swap X/Y selected: {self.selected_swap_xy}")
            
            # Validate selections
            if not self.selected_file:
                msg_box = self._create_styled_message_box(QMessageBox.Warning, "Selection Error", "Please select a data file.")
                msg_box.exec()
                return

            if not self.selected_coordinate_system:
                msg_box = self._create_styled_message_box(QMessageBox.Warning, "Selection Error", "Please select a coordinate system.")
                msg_box.exec()
                return

            # Handle custom EPSG validation
            if self.selected_coordinate_system == "custom":
                custom_epsg_text = self.custom_epsg_input.text().strip()
                if not custom_epsg_text:
                    msg_box = self._create_styled_message_box(QMessageBox.Warning, "Input Error", "Please enter a custom EPSG code.")
                    msg_box.exec()
                    self.custom_epsg_input.setFocus()
                    return
                try:
                    self.selected_custom_epsg = int(custom_epsg_text)
                    debug_print(f"[FILE_DIALOG] User entered custom EPSG: {self.selected_custom_epsg}")
                except ValueError:
                    msg_box = self._create_styled_message_box(QMessageBox.Warning, "Input Error", "Custom EPSG code must be a valid number.")
                    msg_box.exec()
                    self.custom_epsg_input.setFocus()
                    return
            else:
                self.selected_custom_epsg = None


            
            self.accept()
            
        except Exception as e:
            msg_box = self._create_styled_message_box(QMessageBox.Warning, "Error", f"Selection failed: {str(e)}")
            msg_box.exec() 