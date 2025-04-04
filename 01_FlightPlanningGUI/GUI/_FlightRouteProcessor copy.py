from scipy.spatial import ConvexHull
from shapely.geometry import Polygon, Point
import numpy as np

class UnderdeckFlightRouteProcessor:

    def add_vertical_connections(self, route, connection_height):
        """
        Adds vertical connections at the start and the end of the route.
        This version adds checks for data types and structures.
        """
        if not route:
            print("Warning: Empty route received")
            return []

        new_route = []
        # Targets for modification are the first two and last two points
        points_to_modify = [tuple(route[0]), tuple(route[1]), tuple(route[-2]), tuple(route[-1])]
        for point in route:
            point_tuple = tuple(point[:3])  # Extract the coordinate part
            if point_tuple in points_to_modify:
                try:
                    # Ensure the z-coordinate and connection_height are of compatible types
                    new_z = point[2] + connection_height
                    modified_point = [point[0], point[1], new_z] + point[3:] if len(point) > 3 else [point[0], point[1], new_z]
                    new_route.extend([point, modified_point, point])
                except TypeError as e:
                    print(f"TypeError encountered: {e}")
                    print(f"Point data: {point}, Connection height: {connection_height}")
                    continue  # Optionally skip this point or handle the error differently
            else:
                new_route.append(point)
        return new_route

    


    def compute_average_distance(self, coords):
        if len(coords) < 2:
            return 0
        total_distance = sum(((coords[i + 1][0] - coords[i][0])**2 + (coords[i + 1][1] - coords[i][1])**2 + (coords[i + 1][2] - coords[i][2])**2)**0.5 for i in range(len(coords) - 1))
        return total_distance / (len(coords) - 1)

    def generate_back_and_forth_route(self, route_segment, num_passes):
        """
        Generate a back and forth route for surveying tasks.
        """
        full_sequence = []
        for i in range(0, len(route_segment), 2):
            left = route_segment[i]
            right = route_segment[i + 1] if i + 1 < len(route_segment) else route_segment[i]
            pair_sequence = []
            for pass_num in range(num_passes):
                pair_sequence.extend([left, right] if pass_num % 2 == 0 else [right, left])
            full_sequence.extend(pair_sequence)
        return full_sequence

    def reverse_route(self, route):
        return route[::-1]
        
    def remove_consecutive_duplicates(self, route):
        if not route:
            return []
        
        cleaned_route = [route[0]]
        for point in route[1:]:
            if point != cleaned_route[-1]:
                cleaned_route.append(point)
        
        return cleaned_route
    
    def transform_route(self, route, dx=0, dy=0, dz=0):
        return [[x + dx, y + dy, z + dz, tag] for x, y, z, tag in route]




##### Photogrammetric flights
class UASPhotogrammetricFlightPathCalculator:
    def __init__(self, trajectory, normals, flight_route_offset_H_base, flight_route_offset_V_base, standard_flight_routes, photogrammetric_flight_angle):
        self.trajectory = trajectory
        self.normals = normals
        self.flight_route_offset_H_base = flight_route_offset_H_base
        self.flight_route_offset_V_base = flight_route_offset_V_base
        self.standard_flight_routes = standard_flight_routes
        self.photo_flight_routes = []
        self.photogrammetric_flight_angle = photogrammetric_flight_angle 
        
    def process_routes(self, order, pass_underdeck, underdeck_safe_flythrough, reversed_underdeck_safe_flythrough):
        current_route = []
        right_side = []
        left_side = []

        for item in order:
            if isinstance(item, str):
                reverse = "reverse" in item
                route_id = item.replace("reverse ", "")
                tag = route_id if "underdeck" not in item else "underdeck_safe_flythrough"
                route_points = self.compute_flight_route(route_id, reverse, tag)
                if pass_underdeck:
                    current_route.extend(route_points)
                else:
                    if route_id.startswith('2'):  # Ensure left side computation only for '2xx' routes
                        left_side.extend(route_points)
                    else:
                        right_side.extend(route_points)
            elif item is underdeck_safe_flythrough:
                underdeck_points = [[pt[0], pt[1], pt[2], "underdeck_safe_flythrough"] for pt in underdeck_safe_flythrough]
                if pass_underdeck:
                    current_route.extend(underdeck_points)
                else:
                    left_side.extend(underdeck_points)  # Assuming underdeck is always left or duplicated to both sides if needed
            elif item is reversed_underdeck_safe_flythrough:
                reversed_underdeck_points = [[pt[0], pt[1], pt[2], "reversed_underdeck_safe_flythrough"] for pt in reversed_underdeck_safe_flythrough]
                if pass_underdeck:
                    current_route.extend(reversed_underdeck_points)
                else:
                    left_side.extend(reversed_underdeck_points)  # Assuming underdeck is always left or duplicated to both sides if needed

        if pass_underdeck:
            self.photo_flight_routes = current_route
        else:
            self.photo_flight_routes = [right_side, left_side]  # Separately handle right and left side lists

        return self.photo_flight_routes
    
    def compute_flight_route(self, route_id, reverse=False, tag=None):
        h_offset = self.flight_route_offset_H_base + self.standard_flight_routes.get(route_id, {}).get("distance_offset", 0)
        v_offset = self.flight_route_offset_V_base + self.standard_flight_routes.get(route_id, {}).get("vertical_offset", 0)
        angle_radians = np.radians(self.photogrammetric_flight_angle)  # Convert angle to radians
        route = []

        for point, normal in zip(self.trajectory, self.normals):
            direction_multiplier = 1 if route_id.startswith('1') else -1  # Default right for '1xx', left for '2xx'
            normal = np.array(normal) * direction_multiplier
            offset_point = point + normal * h_offset + np.array([0, 0, v_offset])
            
            # Compute the rotated normal to create the angled offset
            rotation_matrix = np.array([
                [np.cos(angle_radians), -np.sin(angle_radians), 0],
                [np.sin(angle_radians), np.cos(angle_radians), 0],
                [0, 0, 1]
            ])
            angled_normal = np.dot(rotation_matrix, normal)
            offset_point += angled_normal * h_offset

            formatted_point = [offset_point[0], offset_point[1], offset_point[2], tag]
            route.append(formatted_point)

        if reverse:
            route.reverse()

        return route
    

    def remove_consecutive_duplicates(self, route):
        if not route:
            return []
        
        cleaned_route = [route[0]]
        for point in route[1:]:
            if point != cleaned_route[-1]:
                cleaned_route.append(point)
        
        return cleaned_route
    
    def transform_route(self, route, dx=0, dy=0, dz=0):
        return [[x + dx, y + dy, z + dz, tag] for x, y, z, tag in route]
    
# FlightRouteProcessor.py
from PySide2.QtWidgets import QSlider, QLineEdit, QComboBox
from PySide2.QtCore import Slot

class TransformationController:
    def __init__(self, slider_X: QSlider, slider_Y: QSlider, slider_Z: QSlider,
                 text_X: QLineEdit, text_Y: QLineEdit, text_Z: QLineEdit, combo_box: QComboBox):
        # Store references to widgets
        self.slider_X = slider_X
        self.slider_Y = slider_Y
        self.slider_Z = slider_Z
        self.text_X = text_X
        self.text_Y = text_Y
        self.text_Z = text_Z
        self.combo_box = combo_box

        # Setup signals
        if self.combo_box is not None:
            self.combo_box.currentIndexChanged.connect(self.route_changed)
        self.slider_X.valueChanged.connect(self.update_text_X)
        self.slider_Y.valueChanged.connect(self.update_text_Y)
        self.slider_Z.valueChanged.connect(self.update_text_Z)

        self.text_X.editingFinished.connect(self.update_slider_X)
        self.text_Y.editingFinished.connect(self.update_slider_Y)
        self.text_Z.editingFinished.connect(self.update_slider_Z)

        # Initialize slider range (assuming +/- 20 units)
        self.setup_sliders()

        # Transformation values for each flight route
        self.transformations = {}
        self.current_route = None

    def setup_sliders(self):
        for slider in [self.slider_X, self.slider_Y]:
            slider.setMinimum(-200)
            slider.setMaximum(200)
            slider.setTickInterval(10)
            slider.setValue(0)
            # Set specific properties for the Z slider
            self.slider_Z.setMinimum(-30)  # Corresponds to -3.0 when divided by 10
            self.slider_Z.setMaximum(30)   # Corresponds to +3.0 when divided by 10
            self.slider_Z.setTickInterval(1)  # Smaller tick interval for finer control
            self.slider_Z.setValue(0)


    @Slot(int)
    def update_text_X(self, value: int):
        self.text_X.setText(f"{value / 10.0:.1f}")
        self.set_transformation_value('x', value / 10.0)

    @Slot(int)
    def update_text_Y(self, value: int):
        self.text_Y.setText(f"{value / 10.0:.1f}")
        self.set_transformation_value('y', value / 10.0)

    @Slot(int)
    def update_text_Z(self, value: int):
        self.text_Z.setText(f"{value / 10.0:.1f}")
        self.set_transformation_value('z', value / 10.0)

    @Slot()
    def update_slider_X(self):
        try:
            value = int(float(self.text_X.text()) * 10)
            self.slider_X.setValue(value)
        except ValueError:
            pass

    @Slot()
    def update_slider_Y(self):
        try:
            value = int(float(self.text_Y.text()) * 10)
            self.slider_Y.setValue(value)
        except ValueError:
            pass

    @Slot()
    def update_slider_Z(self):
        try:
            value = int(float(self.text_Z.text()) * 10)
            self.slider_Z.setValue(value)
        except ValueError:
            pass

    def set_transformation_value(self, axis, value):
        if self.current_route:
            if self.current_route not in self.transformations:
                self.transformations[self.current_route] = {'x': 0, 'y': 0, 'z': 0}
            self.transformations[self.current_route][axis] = value
            self.on_transformation_change(self.current_route)

    def on_transformation_change(self, route_name):
        print(f"Transformation for {route_name}: {self.transformations[route_name]}")

    @Slot()
    def route_changed(self):
        self.current_route = self.combo_box.currentText()
        if self.current_route in self.transformations:
            transformation = self.transformations[self.current_route]
            self.slider_X.setValue(int(transformation['x'] * 10))
            self.slider_Y.setValue(int(transformation['y'] * 10))
            self.slider_Z.setValue(int(transformation['z'] * 10))
        else:
            self.slider_X.setValue(0)
            self.slider_Y.setValue(0)
            self.slider_Z.setValue(0)

        self.text_X.setText(f"{self.slider_X.value() / 10.0:.1f}")
        self.text_Y.setText(f"{self.slider_Y.value() / 10.0:.1f}")
        self.text_Z.setText(f"{self.slider_Z.value() / 10.0:.1f}")

    def update_flight_route_options(self, flight_routes):
        if not self.combo_box:
            print("Error: combo_box is not set up.")
            return
        
        current_route = self.combo_box.currentText() if self.combo_box.count() > 0 else "Photogrammetric Flight"

        # Clear existing options and add "Photogrammetric Flight" as the first option
        self.combo_box.clear()
        self.combo_box.addItem("Photogrammetric Flight")

        # Add other flight routes
        for route_name in flight_routes:
            if route_name != "Photogrammetric Flight":
                self.combo_box.addItem(route_name)
            if route_name not in self.transformations:
                self.transformations[route_name] = {"x": 0, "y": 0, "z": 0}

        # Restore the previously selected route or select "Photogrammetric Flight"
        if current_route in self.transformations:
            self.combo_box.setCurrentText(current_route)
        else:
            self.combo_box.setCurrentText("Photogrammetric Flight")

        self.route_changed()

    def get_transformation_for_route(self, route_name):
        """Get the transformation values for a specific flight route."""
        return self.transformations.get(route_name, {'x': 0, 'y': 0, 'z': 0})
    
