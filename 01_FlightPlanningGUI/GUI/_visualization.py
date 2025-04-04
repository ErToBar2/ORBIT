from PySide2.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QScrollArea, QFrame
from PySide2.QtGui import QColor
from PySide2.QtCore import Qt
import pyvista as pv
from pyvistaqt import QtInteractor
from PySide2.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QScrollArea, QFrame, QSplitter
from PySide2.QtGui import QColor
from PySide2.QtCore import Qt
import pyvista as pv
from pyvistaqt import QtInteractor
import os
import sys
from PySide2.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QSplitter, QScrollArea, QPushButton, QLabel, QMenu, QAction
from PySide2.QtCore import Qt, QPoint
import pyvista as pv
from pyvistaqt import QtInteractor
import numpy as np
from PySide2.QtWidgets import QLabel, QPushButton, QMenu, QAction
from pyvistaqt import QtInteractor
import pyvista as pv
from PySide2.QtWidgets import QDialog, QListWidget, QVBoxLayout, QPushButton, QLabel
import pyvista as pv
import os


class VisualizationWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.point_picker_initialized = False
        # Main layout is now a horizontal QSplitter
        self.splitter = QSplitter(Qt.Horizontal, self)
        self.layout = QVBoxLayout(self)  # Main widget layout
        self.layout.addWidget(self.splitter)

        self.toggle_button = QPushButton("<<", self)
        self.toggle_button.setStyleSheet("""
            QPushButton {
                background-color: rgb(103, 103, 103);
                border: 2px solid green;
                border-radius: 10px;
                color: white;
                min-width: 20px;
                max-width: 20px;
                font-size: 16px;
                padding: 5px;
            }
        """)
        self.toggle_button.clicked.connect(self.toggle_side_panel)
        self.layout.addWidget(self.toggle_button, alignment=Qt.AlignTop | Qt.AlignRight)  # Position it vertically on the right

        # 3D viewer setup
        self.plotter = QtInteractor(self)
        self.splitter.addWidget(self.plotter.interactor)


        # Scroll area for buttons setup
        self.side_panel = QScrollArea()
        self.side_panel.setWidgetResizable(True)
        self.side_panel_frame = QFrame()
        self.side_panel_layout = QVBoxLayout()
        self.side_panel_layout.setAlignment(Qt.AlignTop)  # Align buttons to the top
        self.side_panel_frame.setLayout(self.side_panel_layout)
        self.side_panel.setWidget(self.side_panel_frame)
        self.splitter.addWidget(self.side_panel)

        self.plotter.enable_trackball_style()
        self.event_handler = EventHandler(self.plotter)  # Assuming EventHandler is defined elsewhere
        self.meshes = {}
        self.buttons = {}

        # Initial style for the splitter to give more space to the plotter
        self.splitter.setSizes([300, 100])

        # Picking Starting Point
        # Label to display selected point info
        self.info_label = QLabel("Selected Point Info: None", self)
        self.layout.addWidget(self.info_label)  # Add this line in the layout setup section

        self.point_picker = PointPicker(self.plotter, self)
        self.point_picker.set_info_label(self.info_label) 



    def initialize_point_picker(self):
        if not self.point_picker_initialized:
            self.point_picker = PointPicker(self.plotter, self)
            self.point_picker.set_info_label(self.info_label)
            self.point_picker_initialized = True
            print("PointPicker initialized")

    def add_mesh_with_button(self, ply_file_path, name, color=None, opacity=1.0, line_width=3, point_size=1):
        identifier = ply_file_path  # Use file path as a unique identifier
        #print("Adding mesh with identifier:", identifier)

        # Check if the mesh already exists; if so, remove the old mesh and button
        if identifier in self.meshes:
            self.plotter.remove_actor(self.meshes[identifier]['actor'])
            old_button = self.buttons.get(name)
            if old_button:
                self.side_panel_layout.removeWidget(old_button)
                old_button.deleteLater()
                del self.buttons[name]

        # Load the mesh and create/update the button
        self.set_mesh_from_ply(identifier, color=color, opacity=opacity, line_width=line_width, point_size=point_size)
        self.create_or_update_button(name, identifier, color)
    
    def set_mesh_from_ply(self, identifier, color=None, opacity=1.0, line_width=3, point_size=5):
        mesh = pv.read(identifier)  # Load the mesh file
        file_extension = os.path.splitext(identifier)[-1].lower()  # Get the file extension
        has_color = 'colors' in mesh.array_names  # Check if mesh has inherent color data

        if mesh.n_lines > 0 and file_extension == '.obj':
            # OBJ files with lines
            actor = self.plotter.add_mesh(mesh, color=color if color else None, line_width=line_width, point_size=25)
        elif mesh.n_faces > 0:
            # Mesh with faces (usually PLY)
            actor = self.plotter.add_mesh(mesh, color=color if color else None, opacity=opacity)
        else:
            # PLY point clouds, or any mesh without faces or lines specific handling
            actor = self.plotter.add_mesh(mesh, color=True)

        self.meshes[identifier] = {'mesh': mesh, 'actor': actor, 'visible': True, 'color': color}



    def toggle_side_panel(self):
        if self.side_panel.isVisible():
            self.side_panel.hide()
            self.toggle_button.setText(">>")
        else:
            self.side_panel.show()
            self.toggle_button.setText("<<")

    def apply_button_style(self, button, color, is_visible=True):
        if color and is_visible:
            qt_color = QColor(int(color[0] * 255), int(color[1] * 255), int(color[2] * 255))
            background_color = f"rgb({qt_color.red()}, {qt_color.green()}, {qt_color.blue()})"
        else:
            background_color = "transparent"  # or any default you like when not visible

        text_color = "black" if is_visible else "grey"
        button.setStyleSheet(f"""
            QPushButton {{
                background-color: {background_color};
                border: 1px solid #bfbfbf;
                border-radius: 5px;
                padding: 5px;
                text-align: center;
                color: {text_color};
            }}
            QPushButton:hover {{
                background-color: #e1e1e1;
            }}
            QPushButton:pressed {{
                background-color: #cacaca;
            }}
            QPushButton:checked {{
                background-color: #a0a0a0;
            }}
        """)
    def toggle_visibility(self, identifier, name):
        mesh_info = self.meshes[identifier]
        button = self.buttons[name]

        if mesh_info['visible']:
            self.plotter.remove_actor(mesh_info['actor'])
            mesh_info['visible'] = False
            self.apply_button_style(button, mesh_info['color'], is_visible=False)
        else:
            self.plotter.add_actor(mesh_info['actor'])
            mesh_info['visible'] = True
            self.apply_button_style(button, mesh_info['color'], is_visible=True)

        # Update visibility in the point picker without a print statement
        self.point_picker.toggle_route_visibility(name, mesh_info['visible'])

        self.plotter.render()  # Ensure the plotter is re-rendered to apply visual changes
        


    
    def create_or_update_button(self, name, identifier, color):
        button = QPushButton(f"{name}", self)
        self.apply_button_style(button, color, is_visible=True)
        button.clicked.connect(lambda: self.toggle_visibility(identifier, name))
        self.side_panel_layout.addWidget(button)
        self.buttons[name] = button

    def change_view_to_top(self):
        self.plotter.view_isometric()
        
    def generate_button_style(self, color):
        if color:
            qt_color = QColor(int(color[0] * 255), int(color[1] * 255), int(color[2] * 255))
            return f"""
                QPushButton {{
                    background-color: rgb({qt_color.red()}, {qt_color.green()}, {qt_color.blue()});
                    border: 1px solid #bfbfbf;
                    border-radius: 5px;
                    padding: 5px;
                    text-align: center;
                    color: black;  # Ensure the text color is set to black initially
                }}
                QPushButton:hover {{
                    background-color: #e1e1e1;
                }}
                QPushButton:pressed {{
                    background-color: #cacaca;
                }}
                QPushButton:checked {{
                    background-color: #a0a0a0;
                }}
            """
        else:
            return """
                QPushButton {{
                    background-color: rgb(200, 200, 200);  # Set a default background color
                    border: 1px solid #bfbfbf;
                    border-radius: 5px;
                    padding: 5px;
                    text-align: center;
                    color: black;
                }}
            """
        

############## For Point Picker #################
    def get_all_mesh_names(self):
        """Retrieve all mesh names from the stored meshes."""
        flight_route_names = []
        for identifier in self.meshes.keys():
            name = os.path.splitext(os.path.basename(identifier))[0]
            if "Photogrammetric_Flight_Route" in name or "underdeck_section_" in name:
                flight_route_names.append(name)
        return flight_route_names
    
    def get_visible_route_names(self):
        """
        Retrieve a list of names for all currently visible flight routes.
        
        Returns:
        List[str]: A list containing the names of all visible flight routes.
        """
        #print(self.meshes.items())
        visible_routes = []
        for identifier, mesh_info in self.meshes.items():
            if mesh_info['visible']:  # Check if the mesh is currently visible
                # Extract the route name from the identifier by taking the filename without extension
                name = os.path.splitext(os.path.basename(identifier))[0]
                # Append the route name to the list if it's visible
                visible_routes.append(name)
        
        return visible_routes

    def contextMenuEvent(self, event):
        if self.plotter.interactor.underMouse():
            if hasattr(self, 'point_picker'):
                

                # Initialize the context menu
                menu = QMenu(self)

                # Add trajectory point actions
                pick_trajectory_action = QAction("Pick Trajectory Points", self)
                pick_trajectory_action.triggered.connect(self.point_picker.add_trajectory_point)
                menu.addAction(pick_trajectory_action)

                delete_last_trajectory_action = QAction("Delete Last Trajectory Point", self)
                delete_last_trajectory_action.triggered.connect(self.point_picker.delete_last_trajectory_point)
                menu.addAction(delete_last_trajectory_action)

                # Add starting point actions
                pick_starting_point_action = QAction("Pick Starting Point", self)
                pick_starting_point_action.triggered.connect(lambda: self.point_picker.add_starting_point())
                menu.addAction(pick_starting_point_action)

                delete_last_starting_point_action = QAction("Delete Last Starting Point", self)
                delete_last_starting_point_action.triggered.connect(self.point_picker.delete_last_starting_point)
                menu.addAction(delete_last_starting_point_action)
                
                self.point_picker.remove_unused_starting_points()  
                self.point_picker.redraw_trajectory_points()  
                self.point_picker.redraw_starting_points()
                
                # Display the context menu
                menu.exec_(event.globalPos())
            else:
                print("point_picker not initialized")
        else:
            super().contextMenuEvent(event)  # Ensure that default parent behavior is also maintained if needed

class EventHandler:
    def __init__(self, plotter):
        self.plotter = plotter
        self.is_panning = False
        self.last_panning_position = None
        self.connect_events()

    def connect_events(self):
        interactor = self.plotter.interactor
        interactor.wheelEvent = self.handle_mouse_wheel
        interactor.mousePressEvent = self.mouse_press_event
        interactor.mouseMoveEvent = self.mouse_move_event
        interactor.mouseReleaseEvent = self.mouse_release_event

    def handle_mouse_wheel(self, event):
        zoom_factor = 1.2 if event.angleDelta().y() > 0 else 0.8
        self.plotter.camera.zoom(zoom_factor)
        self.plotter.render()
        event.accept()

    def mouse_press_event(self, event):
        if event.buttons() == Qt.RightButton or (event.buttons() == Qt.LeftButton and event.modifiers() == Qt.ShiftModifier):
            self.is_panning = True
            self.last_panning_position = (event.x(), event.y())
        else:
            super(QtInteractor, self.plotter.interactor.__class__).mousePressEvent(self.plotter.interactor, event)

    def mouse_move_event(self, event):
        if self.is_panning:
            self.perform_panning(event.x(), event.y())
        else:
            super(QtInteractor, self.plotter.interactor.__class__).mouseMoveEvent(self.plotter.interactor, event)

    def mouse_release_event(self, event):
        self.is_panning = False
        self.last_panning_position = None
        super(QtInteractor, self.plotter.interactor.__class__).mouseReleaseEvent(self.plotter.interactor, event)

    def perform_panning(self, x, y):
        dx = x - self.last_panning_position[0]
        dy = y - self.last_panning_position[1]
        self.last_panning_position = (x, y)
        self.plotter.camera.azimuth(-dx * 0.2)
        self.plotter.camera.elevation(dy * 0.2)
        self.plotter.camera.orthogonalize_view_up()
        self.plotter.render()


class PointPicker:
    def __init__(self, plotter, visualization_widget):
        self.plotter = plotter
        self.visualization_widget = visualization_widget 
        
        self.plotter = plotter
        self.picking_enabled = False
        self.selected_points = []
        self.point_actors = []
        self.starting_point_actor = None
        self.info_label = None  # 
        self.initialize_route_map()
        self.trajectory_points = []
        self.trajectory_point_actors = []
        self.starting_points = []
        self.starting_point_actors = []


    def add_trajectory_point(self):
        picked_point = self.plotter.pick_mouse_position()
        if picked_point is not None:
            radius = 1.0  # Define a suitable radius based on your model scale
            points_within_radius = self.get_points_around(picked_point, radius)
            highest_point = self.select_highest_point(points_within_radius)

            if highest_point is not None and len(highest_point) > 0:  # Check if highest_point is not None and has elements
                
                self.update_trajectory_point(highest_point)
            else:
                print("No valid points found in the selection area.")
            

    def update_trajectory_point(self, point):
        sphere = pv.Sphere(radius=0.4, center=point)
        actor = self.plotter.add_mesh(sphere, color=[229/255, 139/255, 117/255])
        self.trajectory_points.append(point)
        self.trajectory_point_actors.append(actor)
        self.plotter.render()

    def get_points_around(self, center_point, radius):
        points = []
        for identifier, mesh_info in self.visualization_widget.meshes.items():
            if '.ply' in identifier:
                mesh = mesh_info['mesh']
                query_point = np.array(center_point)
                all_points = np.array(mesh.points)
                distances = np.linalg.norm(all_points - query_point, axis=1)
                points.extend(all_points[distances <= radius])
        return points
    
    def select_highest_point(self, points):
        return max(points, key=lambda p: p[2]) if points else None

    def delete_last_trajectory_point(self):
        if self.trajectory_points:
            last_point = self.trajectory_points.pop()
            last_actor = self.trajectory_point_actors.pop()
            self.plotter.remove_actor(last_actor)
            self.plotter.render()

    def add_starting_point(self):
       
        picked_point = self.plotter.pick_mouse_position()
        if picked_point:
            sphere = pv.Sphere(radius=0.4, center=picked_point)
            actor = self.plotter.add_mesh(sphere, color='red')  # Customize color as needed
            self.starting_points.append(picked_point)
            self.starting_point_actors.append(actor)
            self.update_route_map(picked_point)
            self.plotter.render()
        
    def delete_last_starting_point(self):
        if self.starting_points:
            last_point = self.starting_points.pop()
            last_actor = self.starting_point_actors.pop()
            self.plotter.remove_actor(last_actor)
            self.plotter.render()
    
    def redraw_points(self, points, actors, color):
        """Redraw all points with given attributes."""
        # Clear existing actors
        for actor in actors:
            self.plotter.remove_actor(actor)
        actors.clear()

        # Redraw all points with the new attributes
        for point in points:
            sphere = pv.Sphere(radius=0.4, center=point)
            actor = self.plotter.add_mesh(sphere, color=color)
            actors.append(actor)
        self.plotter.render()

    def redraw_trajectory_points(self):
        """Redraw all trajectory points."""
        trajectory_color = [229/255, 139/255, 117/255]  # Custom color for trajectory points
        self.redraw_points(self.trajectory_points, self.trajectory_point_actors, trajectory_color)

    def redraw_starting_points(self):
        """Redraw all starting points."""
        starting_color = [225/255, 46/255, 87/255]  # Custom color for starting points
        self.redraw_points(self.starting_points, self.starting_point_actors, starting_color)
    
    def get_trajectory_points(self):
        """Return the current list of trajectory points."""
        return self.trajectory_points

    def initialize_route_map(self):
        
        # Fetch the names of all meshes to initialize the map
        mesh_names = self.visualization_widget.get_all_mesh_names()
        self.route_point_mapping = {name: {'visible': False, 'point': None} for name in mesh_names}
        
        for route, info in self.route_point_mapping.items():
            print(f"{route}: {info['point']}")  # Initialize print with None as the point

    def print_route_map(self):
        print("Updated map:")
        for route, info in self.route_point_mapping.items():
            point_info = "None" if info['point'] is None else f"{info['point'][0]:.2f}, {info['point'][1]:.2f}, {info['point'][2]:.2f}"
            print(f"{route}: {point_info}")

    def set_info_label(self, label):
        """Assigns a QLabel to update with point information."""
        self.info_label = label
        
    def update_route_map(self, picked_point):
        visible_routes = self.visualization_widget.get_visible_route_names()
        for route in self.route_point_mapping:
            if route in visible_routes:
                self.route_point_mapping[route]['point'] = picked_point
                self.route_point_mapping[route]['visible'] = True
        self.print_route_map()
        
    def toggle_route_visibility(self, route_name, visible):
        if route_name in self.route_point_mapping:
            self.route_point_mapping[route_name]['visible'] = visible

    def remove_unused_starting_points(self):
        """Removes starting points that are no longer associated with any visible route."""
        points_to_remove = []
        actors_to_remove = []

        # Check each point to see if it is used in any route mapping
        for i, point in enumerate(self.starting_points):
            is_used = any(np.array_equal(info['point'], point) and info['visible']
                        for route, info in self.route_point_mapping.items())
            if not is_used:
                points_to_remove.append(point)
                actors_to_remove.append(self.starting_point_actors[i])

        # Remove the points and actors that are not used
        for point in points_to_remove:
            index = self.starting_points.index(point)
            self.starting_points.pop(index)
            actor = self.starting_point_actors.pop(index)
            self.plotter.remove_actor(actor)
            self.plotter.render()

        # Optionally update the UI or print feedback
        if self.info_label:
            self.info_label.setText(f"Removed {len(points_to_remove)} unused starting points.")
        