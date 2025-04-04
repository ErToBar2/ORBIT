import math
from shapely.geometry import LineString, Point
from shapely.ops import substring
from shapely.geometry import Point, Polygon
from shapely.geometry import LineString
from PySide2.QtWidgets import QMessageBox
import math
import numpy as np
from shapely.geometry import Point, Polygon
from shapely.ops import nearest_points

class SafetyCheck:
    def __init__(self, flight_route, safety_zones, safety_zones_clearance, takeoff_altitude):
        self.flight_route_safety_check = flight_route
        self.safety_zones = safety_zones
        self.safety_zones_clearance = safety_zones_clearance
        self.takeoff_altitude = takeoff_altitude

    def interpolate_between_points(self, p1, p2, interval):
        """Generate points at a specified interval between two points."""
        x1, y1, z1, *extra = p1
        x2, y2, z2, *extra = p2
        dx, dy, dz = x2 - x1, y2 - y1, z2 - z1
        distance = math.sqrt(dx**2 + dy**2 + dz**2)
        vector = (dx / distance, dy / distance, dz / distance)
        current_distance = interval
        while current_distance < distance:
            new_point = [x1 + vector[0] * current_distance, 
                         y1 + vector[1] * current_distance, 
                         z1 + vector[2] * current_distance]  # Changed tuple to list
            yield new_point
            current_distance += interval

    def resample_route(self, flight_route, interval=0.5):
        """Resample the flight route at specified interval distances, preserving sharp corners and optionally tags."""
        has_tag = len(flight_route[0]) == 4  # Check if tags are included
        resampled_route = [flight_route[0]]  # Start with the first point

        for i in range(1, len(flight_route)):
            p1 = flight_route[i - 1]
            p2 = flight_route[i]
            if has_tag:
                tag = p1[3]  # Tag from the previous point
                additional_points = [(x, y, z, tag) for x, y, z in self.interpolate_between_points(p1[:3], p2[:3], interval)]
            else:
                additional_points = [(*coords,) for coords in self.interpolate_between_points(p1, p2, interval)]

            resampled_route.extend(additional_points)
            resampled_route.append(p2)  # Ensure each segment ends with the actual waypoint

        self.flight_route_safety_check = resampled_route
        return resampled_route


    def adjust_heights(self, safety_zones_clearance_adjust):
        adjusted_route = [list(point) for point in self.flight_route_safety_check]
        points_in_zones = self.find_points_in_all_safety_zones()
        points_to_remove = set()

        for zone_data in points_in_zones:
            zone_index, indices = zone_data
            z_min, z_max = self.safety_zones_clearance[zone_index]

            if zone_index < len(safety_zones_clearance_adjust):
                adjustment_value = safety_zones_clearance_adjust[zone_index][0]

                if adjustment_value == 0:
                    points_to_remove.update(indices)
                elif adjustment_value == -1:
                    for idx in indices:
                        if idx not in points_to_remove:
                            point = adjusted_route[idx]
                            new_points = self.shift_point_outside_zone(point, self.safety_zones[zone_index], z_min, z_max)
                            adjusted_route[idx:idx + 1] = new_points
                elif z_min < adjustment_value < z_max:
                    msg = QMessageBox()
                    msg.setIcon(QMessageBox.Critical)
                    msg.setText(f"Adjustment value {adjustment_value} falls within the unsafe bounds of the safety zone clearance {z_min} to {z_max}. Operation aborted.")
                    msg.setWindowTitle("Error: Invalid Adjustment")
                    msg.exec_()
                    return  # Exit the function as the adjustment is not valid
                else:
                    for idx in indices:
                        if idx not in points_to_remove:  # Check if index is not marked for removal
                            x, y, z, *extra = adjusted_route[idx]
                            adjusted_route[idx] = [x, y, adjustment_value + self.takeoff_altitude, *extra]

        # Remove points marked for deletion
        if points_to_remove:
            adjusted_route = [point for i, point in enumerate(adjusted_route) if i not in points_to_remove]
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Warning)
            msg.setText("Points have been removed from the flight route. Please visually inspect the route.")
            msg.setWindowTitle("Warning: Check Flight Route")
            msg.exec_()

        self.flight_route_safety_check = adjusted_route

        return adjusted_route

    def shift_point_outside_zone(self, point, zone_shape, z_min, z_max):
        """
        Redirect a point around the safety zone boundary.
        """
        point_geom = Point(point[:2])
        polygon_geom = Polygon(zone_shape)
        
        # Find the nearest point on the polygon boundary
        nearest = nearest_points(point_geom, polygon_geom.boundary)[1]
        
        # Find entry and exit points by projecting the point onto the polygon boundary
        entry_point = nearest_points(point_geom, polygon_geom.boundary)[1]
        exit_point = nearest_points(Point(polygon_geom.centroid.coords[0]), polygon_geom.boundary)[1]
        
        # Generate waypoints along the boundary to redirect the flight route
        boundary_coords = list(polygon_geom.boundary.coords)
        entry_index = boundary_coords.index(entry_point.coords[0])
        exit_index = boundary_coords.index(exit_point.coords[0])
        
        if entry_index < exit_index:
            path_around_zone = boundary_coords[entry_index:exit_index + 1]
        else:
            path_around_zone = boundary_coords[entry_index:] + boundary_coords[:exit_index + 1]

        # Convert 2D path to 3D waypoints
        new_points = [[x, y, point[2]] for x, y in path_around_zone]
        
        return new_points
    
    def find_points_in_all_safety_zones(self):
        all_indices = []
        for zone_index, (zone, clearance) in enumerate(zip(self.safety_zones, self.safety_zones_clearance)):
            z_min, z_max = clearance
            # add takeoff altitude to z_min and z_max
            z_min += self.takeoff_altitude
            z_max += self.takeoff_altitude

            zone_indices = []
            for index, point in enumerate(self.flight_route_safety_check):
                if self.is_point_in_zone(point, zone, z_min, z_max):
                    zone_indices.append(index)
            all_indices.append((zone_index, zone_indices))
        return all_indices
    
    def is_point_in_zone(self, point, polygon, z_min, z_max):
        """Check if a 3D point is within a 2D polygon and between vertical limits."""
        x, y, z, *extra = point
        if not (z_min <= z <= z_max):
            return False
        poly = Polygon(polygon)
        return poly.contains(Point(x, y))

    def angle_based_simplification(self, min_angle_change=20):
        """Simplify the route by removing points that do not contribute significant angle changes, preserving optionally tags."""
        has_tag = len(self.flight_route_safety_check[0]) == 4  # Check if tags are included
        if len(self.flight_route_safety_check) < 3:
            return self.flight_route_safety_check  # Not enough points to simplify

        simplified_route = [self.flight_route_safety_check[0]]
        for i in range(1, len(self.flight_route_safety_check) - 1):
            p1 = self.flight_route_safety_check[i - 1]
            p2 = self.flight_route_safety_check[i]
            p3 = self.flight_route_safety_check[i + 1]

            # Calculate angle changes using only coordinates
            angle_change_xy = self.calculate_angle_change(p1[:2], p2[:2], p3[:2])
            angle_change_yz = self.calculate_angle_change(p1[1:3], p2[1:3], p3[1:3])
            angle_change_xz = self.calculate_angle_change([p1[0], p1[2]], [p2[0], p2[2]], [p3[0], p3[2]])

            # Check if the angle change in any plane exceeds the minimum angle change
            if angle_change_xy > min_angle_change or angle_change_yz > min_angle_change or angle_change_xz > min_angle_change:
                simplified_route.append(p2)  # Include full point with or without tag

        simplified_route.append(self.flight_route_safety_check[-1])
        self.flight_route_safety_check = simplified_route
        return simplified_route

    def calculate_angle_change(self, p1, p2, p3):
        """Helper method to calculate the angle change between three points projected onto a plane."""
        def vector_from_points(point1, point2):
            return [point2[0] - point1[0], point2[1] - point1[1]]

        v1 = vector_from_points(p1, p2)
        v2 = vector_from_points(p2, p3)

        dot_product = v1[0] * v2[0] + v1[1] * v2[1]
        magnitude_v1 = math.sqrt(v1[0]**2 + v1[1]**2)
        magnitude_v2 = math.sqrt(v2[0]**2 + v2[1]**2)

        if magnitude_v1 == 0 or magnitude_v2 == 0:
            return 0  # Avoid computation if one of the vectors is a zero vector, angle change is undefined

        # Clamp dot product to the range of -1 to 1 to ensure the value is within the domain of acos
        cos_theta = dot_product / (magnitude_v1 * magnitude_v2)
        cos_theta = max(-1, min(1, cos_theta))  # Clamping the value to avoid math domain errors

        # Calculate angle in radians
        angle = math.acos(cos_theta)
        return abs(angle) * (180 / math.pi)  # Convert to degrees
    
#### Ensure there are no duplicates:
    def remove_consecutive_duplicates(self):
        """Remove consecutive duplicate points from the flight route, handling potential extra tags."""
        if not self.flight_route_safety_check:
            return []
        
        cleaned_route = [self.flight_route_safety_check[0]]  # Start with the first point
        for point in self.flight_route_safety_check[1:]:
            if point[:3] != cleaned_route[-1][:3] or (len(point) > 3 and point[3:] != cleaned_route[-1][3:]):
                cleaned_route.append(point)
        
        self.flight_route_safety_check = cleaned_route
        return cleaned_route
    
    def resample_flight_route(self, flight_route, min_distance=5.0):
        if not flight_route or len(flight_route) < 2:
            print("Error: The flight route must contain at least two points.")
            return flight_route
        
        def calculate_distance(p1, p2):
            return math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2 + (p2[2] - p1[2])**2)
        
        def interpolate_points(p1, p2, interval):
            x1, y1, z1, *extra = p1
            x2, y2, z2, *extra = p2
            dx, dy, dz = x2 - x1, y2 - y1, z2 - z1
            distance = calculate_distance(p1, p2)
            vector = (dx / distance, dy / distance, dz / distance)
            current_distance = interval
            while current_distance < distance:
                new_point = [x1 + vector[0] * current_distance, 
                                y1 + vector[1] * current_distance, 
                                z1 + vector[2] * current_distance]
                if extra:
                    new_point.extend(extra)
                yield new_point
                current_distance += interval

        resampled_route = [flight_route[0]]

        for i in range(1, len(flight_route)):
            p1 = flight_route[i - 1]
            p2 = flight_route[i]
            distance = calculate_distance(p1, p2)
            sampling_distance = max(min_distance, distance / math.ceil(distance / min_distance))
            additional_points = list(interpolate_points(p1, p2, sampling_distance))
            resampled_route.extend(additional_points)
            resampled_route.append(p2)

        self.flight_route_safety_check = resampled_route
        return resampled_route