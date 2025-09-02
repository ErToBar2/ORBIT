"""Simple PyVista-based 3-D viewer with a side panel of toggle buttons.
This is a pared-down copy of the original GUI/_visualization.py and only
includes the bits needed for showing bridge & pillar meshes.
Enhanced with improved navigation controls including double-click recentering.
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QScrollArea, QFrame, QPushButton, QSplitter, QLabel
from PySide6.QtCore import Qt, QTimer, QEvent
from PySide6.QtGui import QColor, QMouseEvent
import pyvista as pv
from pyvistaqt import QtInteractor
import os
import numpy as np
from typing import Optional

# Debug control functions - use the same pattern as main app
def debug_print(*args, **kwargs) -> None:
    """Print function that only outputs when DEBUG is True."""
    # Import DEBUG from main app context
    try:
        from ..data_parser import DEBUG_PRINT
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

class VisualizationWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Main layout – splitter keeps 3-D view & side panel
        splitter = QSplitter(Qt.Horizontal, self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)

        self.plotter = QtInteractor(self)
        # Compatibility: expose this widget via the legacy attribute name expected by other modules
        try:
            if parent is not None and not hasattr(parent, 'pyvista_widget'):
                setattr(parent, 'pyvista_widget', self)
        except Exception:
            # Fail silently – this is only best-effort.
            pass
        splitter.addWidget(self.plotter.interactor)
        
        

        # side panel
        self.side_panel = QScrollArea(); self.side_panel.setWidgetResizable(True)
        self.side_panel_frame = QFrame(); self.side_panel_frame.setLayout(QVBoxLayout())
        self.side_panel.setWidget(self.side_panel_frame)
        self.side_panel_frame.layout().setAlignment(Qt.AlignTop)
        splitter.addWidget(self.side_panel)
        splitter.setSizes([600, 120])

        # Enhanced navigation setup
        self._setup_enhanced_navigation()

        self._safety_zone_registry = set()   
        self._display_to_ident = {}   
        self.meshes = {}   # identifier -> dict(mesh, actor, visible, color)
        self.buttons = {}  # label -> QPushButton
        
        # Navigation enhancement variables
        self._click_timer = QTimer()
        self._click_timer.setSingleShot(True)
        self._click_timer.timeout.connect(self._handle_single_click)
        self._last_click_pos = None
        self._double_click_threshold = 500  # ms - increased from 300 for easier double-clicking

    # ------------------------------------------------------------------
    # Mesh loading helpers
    # ------------------------------------------------------------------
    def add_mesh_with_button(self, ply_path, name, color=None, opacity=1.0, is_safety_zone=False):
        """
        Add mesh from PLY and create a toggle button with a human-readable display name `name`.
        Internally, `ident` is the absolute file path (unique). We also store a mapping name->ident.
        If `is_safety_zone=True`, the display name is tracked in a registry for surgical removal later.
        """
        ident = os.path.abspath(ply_path)

        # If same file already present, replace its actor
        if ident in self.meshes:
            self._remove_mesh(ident)

        self._load_mesh(ident, color=color, opacity=opacity)

        # Display name -> ident mapping (used by remove-by-name)
        self._display_to_ident[name] = ident

        # Create a button labeled with the display name
        self._add_button(name, ident, color)

        # Register as safety-zone only if asked
        if is_safety_zone:
            self._safety_zone_registry.add(name)

    def _load_mesh(self, ident, color=None, opacity=1.0):
        mesh = pv.read(ident)

        # Decide how to colour the mesh
        add_kwargs = dict(opacity=opacity)

        if color is not None:
            # Explicit override colour supplied by caller
            add_kwargs['color'] = color
        else:
            # Try to use per-vertex RGB stored in the file
            if {'red', 'green', 'blue'}.issubset(mesh.point_data.keys()):
                rgb = np.column_stack([
                    mesh.point_data['red'].astype(np.uint8),
                    mesh.point_data['green'].astype(np.uint8),
                    mesh.point_data['blue'].astype(np.uint8)])
                add_kwargs.update({'scalars': rgb, 'rgb': True})
            elif 'RGB' in mesh.point_data and mesh.point_data['RGB'].shape[1] == 3:
                add_kwargs.update({'scalars': mesh.point_data['RGB'].astype(np.uint8), 'rgb': True})

        actor = self.plotter.add_mesh(mesh, **add_kwargs)
        self.meshes[ident] = dict(mesh=mesh, actor=actor, visible=True, color=color)

    def _remove_mesh(self, ident):
        info = self.meshes.pop(ident, None)
        if not info:
            return

        if info.get('visible'):
            self.plotter.remove_actor(info['actor'])

        # Remove any button(s) whose mapping points to this ident
        # (usually one, but we handle the general case)
        to_delete = [name for name, id2 in list(self._display_to_ident.items()) if id2 == ident]
        for name in to_delete:
            self._display_to_ident.pop(name, None)
            if name in self.buttons:
                btn = self.buttons.pop(name)
                btn.setParent(None)
                btn.deleteLater()

        # Clean possible stale registry entries
        self._safety_zone_registry.difference_update(to_delete)

    # ------------------------------------------------------------------
    def _add_button(self, label, ident, color):
        # Check if button already exists, skip creation if it does
        if label in self.buttons:
            debug_print(f"[BUTTON] Button '{label}' already exists, skipping creation")
            return
        
        btn = QPushButton(label, self)
        self._style_button(btn, color, True)
        btn.clicked.connect(lambda: self._toggle_visibility(ident, btn))
        self.side_panel_frame.layout().addWidget(btn)
        self.buttons[label] = btn

    def _style_button(self, button, color, on=True):
        if color and on:
            col = QColor(*(int(c*255) for c in color))
            bg = f"rgb({col.red()}, {col.green()}, {col.blue()})"
        else:
            bg = 'lightgrey' if on else 'transparent'
        txt = 'black' if on else 'grey'
        button.setStyleSheet(f"QPushButton{{background-color:{bg};color:{txt};padding:4px;border-radius:4px;}}");

    def _toggle_visibility(self, ident, button):
        info = self.meshes[ident]
        if info['visible']:
            self.plotter.remove_actor(info['actor'])
            info['visible'] = False
            self._style_button(button, info['color'], False)
        else:
            self.plotter.add_actor(info['actor'])
            info['visible'] = True
            self._style_button(button, info['color'], True)
        self.plotter.render() 

    # ------------------------------------------------------------------
    # Enhanced Navigation Controls
    # ------------------------------------------------------------------
    def _setup_enhanced_navigation(self):
        """Setup enhanced navigation including double-click recentering and improved trackball."""
        try:
            # Improve camera and interaction settings
            self.plotter.camera.SetParallelProjection(False)  # Use perspective projection
            
            # Setup better trackball behavior
            interactor = self.plotter.iren
            
            if hasattr(interactor, 'SetInteractorStyle'):
                # Get the current interactor style
                style = interactor.GetInteractorStyle()
                if style:
                    # Improve rotation sensitivity
                    if hasattr(style, 'SetMotionFactor'):
                        style.SetMotionFactor(10.0)  # Default is usually 1.0
                    if hasattr(style, 'SetMouseWheelMotionFactor'):
                        style.SetMouseWheelMotionFactor(1.0)
            
            # Alternative approach - use Qt event handling instead of VTK observer
            self.plotter.interactor.installEventFilter(self)
            
            # Also try VTK observer as backup
            try:
                self.plotter.iren.AddObserver('LeftButtonPressEvent', self._on_left_click)
            except Exception as e:
                pass  # Silent fallback
            
            debug_print("[NAVIGATION] Enhanced navigation controls initialized")
            debug_print("[NAVIGATION] - Double-click to recenter on point")
            debug_print("[NAVIGATION] - Improved rotation sensitivity")
            debug_print("[NAVIGATION] - Better trackball behavior")
            
        except Exception as e:
            debug_print(f"[NAVIGATION] Warning: Could not setup enhanced navigation: {e}")

    def _on_left_click(self, obj, event):
        """Handle left mouse clicks for double-click detection."""
        try:
            # Get click position
            click_pos = self.plotter.iren.GetEventPosition()
            
            if self._click_timer.isActive():
                # This is a potential double-click
                self._click_timer.stop()
                self._handle_double_click(click_pos)
            else:
                # Start timer for single click
                self._last_click_pos = click_pos
                self._click_timer.start(self._double_click_threshold)
                
        except Exception as e:
            error_debug_print(f"[NAVIGATION] Error in click handling: {e}")

    def eventFilter(self, obj, event):
        """Qt event filter to handle mouse events."""
        try:
            # Handle native Qt double-click events (more reliable)
            if event.type() == QEvent.MouseButtonDblClick:
                if event.button() == Qt.LeftButton:
                    click_pos = (event.pos().x(), event.pos().y())
                    self._handle_double_click_qt(click_pos, event)
                    return True  # Consume the event
            
            # Also handle single clicks for manual double-click detection (backup)
            elif event.type() == QEvent.MouseButtonPress:
                if event.button() == Qt.LeftButton:
                    click_pos = (event.pos().x(), event.pos().y())
                    
                    if self._click_timer.isActive():
                        self._click_timer.stop()
                        self._handle_double_click_qt(click_pos, event)
                        return True  # Consume the event
                    else:
                        self._last_click_pos = click_pos
                        self._click_timer.start(self._double_click_threshold)
                        
        except Exception as e:
            error_debug_print(f"[NAVIGATION] Error in Qt event filter: {e}")
            
        return super().eventFilter(obj, event)

    def _handle_double_click_qt(self, click_pos, event):
        """Handle double-click through Qt event system."""
        try:
            # Convert Qt coordinates to VTK coordinates if needed
            # Qt coordinates might be different from VTK picking coordinates
            widget_height = self.plotter.interactor.height()
            vtk_y = widget_height - click_pos[1]  # VTK uses bottom-left origin, Qt uses top-left
            vtk_pos = (click_pos[0], vtk_y)
            
            # Now use the VTK picking system
            self._perform_picking_and_recenter(vtk_pos)
            
        except Exception as e:
            error_debug_print(f"[NAVIGATION] Error in Qt double-click handling: {e}")

    def _perform_picking_and_recenter(self, click_pos):
        """Perform VTK picking and recenter camera."""
        try:
            # Use PyVista's built-in picking method instead of direct VTK access
            try:
                # PyVista has a built-in method for picking at screen coordinates
                picked_point = self.plotter.pick_click(click_pos[0], click_pos[1])
                
                if picked_point is not None and len(picked_point) == 3:
                    self._recenter_camera_on_point(picked_point)
                else:
                    self._try_alternative_picking(click_pos)
                    
            except Exception as e:
                self._try_alternative_picking(click_pos)
                
        except Exception as e:
            debug_print(f"[NAVIGATION] Error in picking: {e}")

    def _try_alternative_picking(self, click_pos):
        """Try alternative picking methods if PyVista pick_click fails."""
        try:
            # Method 1: Try to create our own picker
            try:
                import vtk
                picker = vtk.vtkCellPicker()
                picker.SetTolerance(0.005)  # 0.5% tolerance
                
                # Pick at the click position
                result = picker.Pick(click_pos[0], click_pos[1], 0, self.plotter.renderer)
                
                if result:
                    picked_point = picker.GetPickPosition()
                    if picked_point and any(picked_point):
                        self._recenter_camera_on_point(picked_point)
                        return
                        
            except Exception as e:
                pass  # Silent fallback
            
            # Method 2: Try using renderer picker
            try:
                renderer = self.plotter.renderer
                if hasattr(renderer, 'GetPicker'):
                    picker = renderer.GetPicker()
                    if picker:
                        result = picker.Pick(click_pos[0], click_pos[1], 0, renderer)
                        if result:
                            picked_point = picker.GetPickPosition()
                            if picked_point and any(picked_point):
                                self._recenter_camera_on_point(picked_point)
                                return
                                
            except Exception as e:
                pass  # Silent fallback
            
            # Method 3: Fallback to mesh center
            self._recenter_on_closest_mesh_point(click_pos)
            
        except Exception as e:
            # Final fallback
            self._recenter_on_closest_mesh_point(click_pos)

    def _handle_single_click(self):
        """Handle single click (currently does nothing special)."""
        pass  # Single clicks are handled by default PyVista behavior

    def _handle_double_click(self, click_pos):
        """Handle double-click to recenter camera on the clicked point."""
        try:
            # Perform picking to find the 3D point
            picker = self.plotter.iren.GetPicker()
            
            if picker:
                # Pick at the click position
                result = picker.Pick(click_pos[0], click_pos[1], 0, self.plotter.renderer)
                
                picked_point = picker.GetPickPosition()
                
                if picked_point and any(picked_point):  # Check if we got a valid point
                    self._recenter_camera_on_point(picked_point)
                else:
                    # If no surface was picked, try to find closest mesh point
                    self._recenter_on_closest_mesh_point(click_pos)
            else:
                self._recenter_on_closest_mesh_point(click_pos)
                
        except Exception as e:
            debug_print(f"[NAVIGATION] Error in double-click handling: {e}")

    def _recenter_camera_on_point(self, point):
        """Recenter the camera to look at the specified 3D point."""
        try:
            # Set new focal point
            self.plotter.camera.SetFocalPoint(point)
            
            # Optionally adjust camera position to maintain good viewing angle
            current_pos = self.plotter.camera.GetPosition()
            focal_point = np.array(point)
            camera_pos = np.array(current_pos)
            
            # Calculate direction from focal point to camera
            direction = camera_pos - focal_point
            distance = np.linalg.norm(direction)
            
            # Maintain the same viewing direction but adjust distance if needed
            if distance < 1.0:  # Too close
                direction = direction / np.linalg.norm(direction) * 10.0
                new_camera_pos = focal_point + direction
                self.plotter.camera.SetPosition(new_camera_pos)
            
            # Reset camera up vector if needed
            self.plotter.camera.SetViewUp(0, 0, 1)  # Z-up orientation
            
            # Update the view
            self.plotter.reset_camera_clipping_range()
            self.plotter.render()
            
        except Exception as e:
            debug_print(f"[NAVIGATION] Error recentering camera: {e}")

    def _recenter_on_closest_mesh_point(self, click_pos):
        """Find the closest mesh point to the click and recenter on it."""
        try:
            # Convert screen coordinates to world coordinates
            # This is a fallback when surface picking fails
            
            # Get all visible meshes and find their center
            visible_meshes = [info['mesh'] for info in self.meshes.values() if info['visible']]
            
            if visible_meshes:
                # Calculate combined center of all visible meshes
                all_centers = []
                for mesh in visible_meshes:
                    center = mesh.center
                    all_centers.append(center)
                
                if all_centers:
                    # Use average center as fallback recenter point
                    avg_center = np.mean(all_centers, axis=0)
                    debug_print(f"[NAVIGATION] Using average mesh center as fallback: {avg_center}")
                    self._recenter_camera_on_point(avg_center)
                else:
                    debug_print("[NAVIGATION] No mesh centers available")
            else:
                debug_print("[NAVIGATION] No visible meshes to recenter on")
                
        except Exception as e:
            debug_print(f"[NAVIGATION] Error finding closest mesh point: {e}")

    def remove_mesh_by_name(self, name):
        """Remove a mesh by its display name (the label shown on the button)."""
        try:
            ident = self._display_to_ident.get(name)
            if not ident:
                debug_print(f"[CLEANUP] No mapping for display name '{name}'")
                return
            self._remove_mesh(ident)
            self.plotter.render()
        except Exception as e:
            debug_print(f"[CLEANUP] Error removing '{name}': {e}")

    def remove_all_safety_zones(self):
        """Remove only safety-zone meshes and their buttons, using the registry."""
        try:
            names = list(self._safety_zone_registry)
            debug_print(f"[CLEANUP] Removing {len(names)} safety zone(s) via registry…")
            removed = 0
            for name in names:
                try:
                    self.remove_mesh_by_name(name)
                    removed += 1
                except Exception as e:
                    debug_print(f"[CLEANUP] Warning: Failed to remove '{name}': {e}")

            # Clear registry after attempted removal
            self._safety_zone_registry.clear()

            if hasattr(self, 'plotter'):
                self.plotter.render()
                debug_print("[CLEANUP] Forced render after safety zone removal")

            debug_print(f"[CLEANUP] Successfully removed {removed}/{len(names)} safety zone(s)")
        except Exception as e:
            debug_print(f"[CLEANUP] Error removing safety zones: {e}")
            import traceback; traceback.print_exc()






    def add_polyline(self, name, points, color=(1.0, 0.0, 0.0), line_width=3, tube_radius=0.4,
                     save_obj_path: Optional[str] = None):
        """Add or replace a poly-line (flight route) in the scene.

        Parameters
        ----------
        name : str
            Display name (and unique identifier) for the line.
        points : Sequence of (x, y, z)
            Waypoints in local metric coordinates.
        color : tuple | list
            RGB triple in range 0-1.
        line_width : int
            Screen-space line width (only used when *tube_radius* is 0).
        tube_radius : float
            If >0 a physical tube is generated for thickness independent of zoom.
            Otherwise a flat PolyLine is rendered with *line_width*.
        save_obj_path : str | None
            If given the generated mesh is also saved to the specified *.obj* file.
        """
        import numpy as np
        import pyvista as pv

        # ------------------------------------------------------------------
        # 1. Remove existing actor/button with same name (duplicate-prevention)
        # ------------------------------------------------------------------
        if name in self.meshes:
            self._remove_mesh(name)
            if name in self.buttons:
                btn = self.buttons.pop(name)
                btn.setParent(None)
                btn.deleteLater()

        # ------------------------------------------------------------------
        # 2. Build PolyData for the line or tube
        # ------------------------------------------------------------------
        # Support extra (non-numeric) fields like route tags by slicing to first 3 columns
        pts = np.asarray([p[:3] for p in points], dtype=float)
        if pts.ndim != 2 or pts.shape[1] != 3 or len(pts) < 2:
            raise ValueError("add_polyline expects an Nx3 array of points ≥ 2 waypoints")

        poly = pv.PolyData(pts)
        # lines array = [nPointsSubLine, id0, id1, nPointsSubLine, ...]
        poly.lines = np.hstack([[2, i, i + 1] for i in range(len(pts) - 1)])

        # Generate geometry
        using_tube = tube_radius and tube_radius > 0
        mesh = poly.tube(radius=tube_radius, n_sides=8) if using_tube else poly

        # ------------------------------------------------------------------
        # 3. Add mesh to the scene & side panel
        # ------------------------------------------------------------------
        # Only pass valid PyVista parameters
        if using_tube:
            # Tube mesh doesn't need special parameters
            actor = self.plotter.add_mesh(
                mesh,
                name=name,
                color=color,
                opacity=1.0
            )
        else:
            # Line mesh uses line_width
            actor = self.plotter.add_mesh(
                mesh,
                name=name,
                color=color,
                line_width=line_width
            )

        self.meshes[name] = dict(mesh=mesh, actor=actor, visible=True, color=color)
        self._add_button(name, name, color)
        self.plotter.render()

        # ------------------------------------------------------------------
        # 4. Optional save to OBJ
        # ------------------------------------------------------------------
        if save_obj_path:
            try:
                mesh.save(save_obj_path)
                debug_print(f"[VIS] 💾 Saved polyline as OBJ → {save_obj_path}")
            except Exception as obj_e:
                debug_print(f"[VIS] ⚠️ Could not save OBJ: {obj_e}")