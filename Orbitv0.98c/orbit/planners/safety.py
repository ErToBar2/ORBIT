"""
Safety processor for flight routes.

This module provides functionality to check and adjust flight routes for safety
around defined safety zones. It handles:
- Resampling routes for more detailed processing
- Height adjustments based on safety zone clearances
- Route simplification based on angle changes
- Duplicate point removal
- Filtering routes to avoid safety zones
"""

import numpy as np
from shapely.geometry import Point, Polygon, LineString
from shapely.ops import nearest_points
from typing import List, Union, Tuple
import math

# Debug control functions - use the same pattern as main app
def debug_print(*args, **kwargs) -> None:
    """Print function that only outputs when DEBUG is True."""
    # Import DEBUG from main app context
    try:
        from ..io.data_parser import DEBUG_PRINT
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

def error_print(*args, **kwargs) -> None:
    """Print function that always outputs (for errors)."""
    print(*args, **kwargs)

def filter_route_outside_zones(route_points: np.ndarray, safety_zones: List[Tuple[List[float], List[float]]]) -> np.ndarray:
    """
    Filter flight route points to avoid safety zones.

    Args:
        route_points (np.ndarray): Array of [x, y, z] coordinates defining the flight route
        safety_zones (List[Tuple[List[float], List[float]]]): List of safety zones, each defined by min/max points

    Returns:
        np.ndarray: Filtered route points that avoid safety zones
    """
    if len(route_points) == 0 or len(safety_zones) == 0:
        return route_points

    filtered_points = []
    
    # Convert safety zones to Shapely polygons
    zone_polygons = []
    for zone in safety_zones:
        if len(zone) < 3:  # Need at least 3 points for a polygon
            continue
        try:
            # Extract x, y coordinates for the polygon
            polygon_points = [(p[0], p[1]) for p in zone]
            if polygon_points[0] != polygon_points[-1]:  # Close the polygon if needed
                polygon_points.append(polygon_points[0])
            zone_polygons.append(Polygon(polygon_points))
        except Exception as e:
            debug_print(f"Warning: Could not create polygon from zone: {e}")
            continue

    if not zone_polygons:
        return route_points

    # Process each route segment
    for i in range(len(route_points) - 1):
        p1 = route_points[i]
        p2 = route_points[i + 1]
        
        # Create line segment
        line = LineString([(p1[0], p1[1]), (p2[0], p2[1])])
        
        # Check if line intersects any safety zone
        intersects_zone = False
        for polygon in zone_polygons:
            if line.intersects(polygon):
                intersects_zone = True
                break
        
        # If segment doesn't intersect any zone, keep both points
        if not intersects_zone:
            if not filtered_points or not np.array_equal(filtered_points[-1], p1):
                filtered_points.append(p1)
            if i == len(route_points) - 2:  # Add final point of last safe segment
                filtered_points.append(p2)

    # If no safe points found, return empty array with same shape
    if not filtered_points:
        return np.empty((0, route_points.shape[1]))

    return np.array(filtered_points)

class SafetyProcessor:
    """Processes flight routes to ensure they meet safety requirements."""

    def __init__(self, flight_route, safety_zones, safety_zones_clearance, takeoff_altitude=0):
        """
        Initialize the safety processor.

        Args:
            flight_route (list): List of [x, y, z] coordinates defining the flight route
            safety_zones (list): List of safety zone polygons, each defined by list of [x, y] coordinates
            safety_zones_clearance (list): List of [min_height, max_height] for each safety zone
            takeoff_altitude (float, optional): Base altitude for takeoff. Defaults to 0.
        """
        self.flight_route = flight_route
        self.safety_zones = safety_zones
        self.safety_zones_clearance = safety_zones_clearance
        self.takeoff_altitude = takeoff_altitude
        self._validate_inputs()

    def _validate_inputs(self):
        """Validate input data formats and consistency."""
        if not self.flight_route or not isinstance(self.flight_route[0], (list, tuple)):
            raise ValueError("Flight route must be a non-empty list of coordinates")
        
        if not self.safety_zones or not isinstance(self.safety_zones[0], (list, tuple)):
            raise ValueError("Safety zones must be a non-empty list of polygons")
            
        # Print safety zone information
        debug_print("\n=== Safety Zone Information ===")
        debug_print(f"Number of safety zones: {len(self.safety_zones)}")
        for i, zone in enumerate(self.safety_zones):
            debug_print(f"Safety Zone {i}: {len(zone)} points")

    def resample_route(self, flight_route, interval=0.5):
        """
        Resample the flight route at regular intervals for more detailed processing.

        Args:
            flight_route (list): List of [x, y, z] coordinates
            interval (float, optional): Distance between resampled points in meters. Defaults to 0.5.

        Returns:
            list: Resampled flight route
        """
        resampled_route = []
        
        for i in range(len(flight_route) - 1):
            p1 = flight_route[i]
            p2 = flight_route[i + 1]
            
            # Add the first point
            resampled_route.append(p1)
            
            # Calculate distance between points
            dx = p2[0] - p1[0]
            dy = p2[1] - p1[1]
            dz = p2[2] - p1[2]
            distance = math.sqrt(dx*dx + dy*dy + dz*dz)
            
            if distance > interval:
                # Number of segments needed
                num_segments = int(distance / interval)
                
                for j in range(1, num_segments):
                    t = j / num_segments
                    x = p1[0] + dx * t
                    y = p1[1] + dy * t
                    z = p1[2] + dz * t
                    resampled_route.append([x, y, z])
        
        # Add the last point
        resampled_route.append(flight_route[-1])
        return resampled_route

    def adjust_heights(self, safety_zones_clearance_adjust):
        """
        Adjust flight route heights based on safety zone clearances.

        Args:
            safety_zones_clearance_adjust (list): Additional height adjustments for each safety zone

        Returns:
            list: Adjusted flight route with modified heights or redirected paths
        """
        debug_print("\n=== Flight Route Safety Analysis ===")
        debug_print(f"Total route points: {len(self.flight_route)}")

        # First find all points in safety zones
        points_in_zones = []  # List of (point_idx, zone_idx) tuples
        for zone_idx, zone in enumerate(self.safety_zones):
            debug_print(f"\nAnalyzing Safety Zone {zone_idx}:")
            zone_points = []
            for point_idx, point in enumerate(self.flight_route):
                if self._is_point_in_zone(point[:2], zone):
                    zone_points.append(point_idx)
                    points_in_zones.append((point_idx, zone_idx))
            debug_print(f"Found {len(zone_points)} points in zone {zone_idx}")
            if zone_points:
                debug_print("First 5 points in this zone:")
                for i, idx in enumerate(zone_points[:5]):
                    debug_print(f"  Point {idx}: {self.flight_route[idx]}")

        debug_print(f"\nTotal points in safety zones: {len(points_in_zones)}")
        if not points_in_zones:
            debug_print("No points to adjust!")
            return self.flight_route

        # Group points by point_idx to handle overlapping zones
        points_by_idx = {}
        for point_idx, zone_idx in points_in_zones:
            if point_idx not in points_by_idx:
                points_by_idx[point_idx] = []
            points_by_idx[point_idx].append(zone_idx)

        # Convert points to list for modification
        adjusted_route = [list(point) for point in self.flight_route]
        points_to_remove = set()

        print("\n=== Applying Safety Zone Adjustments ===")
        # Process each point that's in one or more safety zones
        for point_idx, zone_indices in points_by_idx.items():
            if point_idx in points_to_remove:
                continue

            # NEW: Handle overlapping zones by prioritizing the highest adjustment value
            if len(zone_indices) > 1:
                print(f"\nPoint {point_idx} in multiple zones: {zone_indices}")
                
                # Find the zone with the highest adjustment value
                best_zone_idx = None
                best_adjustment = -float('inf')
                
                for zone_idx in zone_indices:
                    if zone_idx >= len(safety_zones_clearance_adjust):
                        continue
                    adjustment_value = safety_zones_clearance_adjust[zone_idx][0] if zone_idx < len(safety_zones_clearance_adjust) else 0
                    print(f"  Zone {zone_idx}: adjustment = {adjustment_value}")
                    
                    # Prioritize higher adjustment values
                    if adjustment_value > best_adjustment:
                        best_adjustment = adjustment_value
                        best_zone_idx = zone_idx
                
                if best_zone_idx is not None:
                    zone_idx = best_zone_idx
                    adjustment_value = best_adjustment
                    print(f"  Selected zone {zone_idx} with adjustment {adjustment_value}")
                else:
                    # Fallback to first zone if no valid adjustments found
                    zone_idx = zone_indices[0]
                    adjustment_value = safety_zones_clearance_adjust[zone_idx][0] if zone_idx < len(safety_zones_clearance_adjust) else 0
            else:
                # Single zone case
                zone_idx = zone_indices[0]
                adjustment_value = safety_zones_clearance_adjust[zone_idx][0] if zone_idx < len(safety_zones_clearance_adjust) else 0

            z_min, z_max = self.safety_zones_clearance[zone_idx]

            print(f"\nProcessing point {point_idx} in zone {zone_idx}:")
            print(f"Original point: {self.flight_route[point_idx]}")
            print(f"Zone clearance: min={z_min}, max={z_max}")
            print(f"Adjustment value: {adjustment_value}")

            if adjustment_value == 0:
                print("Action: Remove point")
                points_to_remove.add(point_idx)
            elif adjustment_value == -1:
                print("Action: Redirect around zone")
                new_points = self._shift_point_outside_zone(adjusted_route[point_idx], self.safety_zones[zone_idx], z_min, z_max)
                if new_points:
                    print(f"Added {len(new_points)} redirect points")
                    adjusted_route[point_idx:point_idx + 1] = new_points
                    print(f"First redirect point: {new_points[0]}")
            elif z_min < adjustment_value < z_max:
                print(f"Warning: Adjustment {adjustment_value} within unsafe bounds [{z_min}, {z_max}]")
                new_height = z_max + self.takeoff_altitude
                print(f"Action: Using maximum safe height {new_height}")
                adjusted_route[point_idx][2] = new_height
            else:
                new_height = adjustment_value + self.takeoff_altitude
                print(f"Action: Adjust height to {new_height}")
                adjusted_route[point_idx][2] = new_height

        # Remove marked points
        if points_to_remove:
            adjusted_route = [point for i, point in enumerate(adjusted_route) if i not in points_to_remove]
            print(f"\nRemoved {len(points_to_remove)} points marked for deletion")

        print(f"\nRoute points after adjustment: {len(adjusted_route)}")
        print("First 5 adjusted points that were in safety zones:")
        points_shown = 0
        for i, point in enumerate(adjusted_route):
            if points_shown >= 5:
                break
            if any(i == idx for idx, _ in points_in_zones if idx not in points_to_remove):
                print(f"Point {i}: {point}")
                points_shown += 1

        return adjusted_route

    def _shift_point_outside_zone(self, point, zone, z_min, z_max):
        """
        Redirect a point around the safety zone boundary.

        Args:
            point (list): Point to redirect [x, y, z]
            zone (list): Safety zone polygon points
            z_min (float): Minimum safe height for zone
            z_max (float): Maximum safe height for zone

        Returns:
            list: List of new points forming a path around the zone
        """
        try:
            point_geom = Point(point[0], point[1])
            zone_points = [(p[0], p[1]) for p in zone]
            if zone_points[0] != zone_points[-1]:
                zone_points.append(zone_points[0])
            polygon = Polygon(zone_points)

            # Find nearest point on zone boundary
            nearest_boundary = nearest_points(point_geom, polygon.boundary)[1]
            
            # Get boundary coordinates
            boundary_coords = list(polygon.boundary.coords)
            
            # Find entry point index
            entry_point = nearest_boundary.coords[0]
            entry_idx = None
            min_dist = float('inf')
            
            for i, coord in enumerate(boundary_coords):
                dist = ((coord[0] - entry_point[0])**2 + (coord[1] - entry_point[1])**2)**0.5
                if dist < min_dist:
                    min_dist = dist
                    entry_idx = i

            if entry_idx is None:
                return None

            # Create path along boundary
            num_points = len(boundary_coords)
            path_points = []
            
            # Add points along boundary, starting from entry point
            for i in range(num_points):
                idx = (entry_idx + i) % num_points
                x, y = boundary_coords[idx]
                # Use maximum of current height and zone minimum height
                z = max(point[2], z_max + self.takeoff_altitude)
                path_points.append([x, y, z])

            return path_points

        except Exception as e:
            print(f"Warning: Failed to redirect point around safety zone: {e}")
            return None

    def angle_based_simplification(self, min_angle_change=20):
        """
        Simplify the route by removing points that don't significantly change direction.

        Args:
            min_angle_change (float, optional): Minimum angle change to keep a point. Defaults to 20.

        Returns:
            list: Simplified flight route
        """
        if len(self.flight_route) < 3:
            return self.flight_route

        simplified_route = [self.flight_route[0]]
        
        for i in range(1, len(self.flight_route) - 1):
            p1 = self.flight_route[i - 1]
            p2 = self.flight_route[i]
            p3 = self.flight_route[i + 1]
            
            angle = self._calculate_angle_change(p1, p2, p3)
            
            if abs(angle) > min_angle_change:
                simplified_route.append(p2)
        
        simplified_route.append(self.flight_route[-1])
        return simplified_route

    def remove_consecutive_duplicates(self):
        """
        Remove consecutive duplicate points from the flight route.

        Returns:
            list: Flight route with duplicates removed
        """
        if not self.flight_route:
            return self.flight_route

        unique_route = [self.flight_route[0]]
        
        for point in self.flight_route[1:]:
            if not self._is_same_point(point, unique_route[-1]):
                unique_route.append(point)
        
        return unique_route

    def _is_point_in_zone(self, point, zone):
        """Check if a 2D point is inside a safety zone polygon."""
        try:
            point = Point(point[0], point[1])
            polygon = Polygon(zone)
            return polygon.contains(point)
        except Exception:
            return False

    def _calculate_angle_change(self, p1, p2, p3):
        """Calculate the angle change between three consecutive points."""
        def vector_from_points(point1, point2):
            return [
                point2[0] - point1[0],
                point2[1] - point1[1],
                point2[2] - point1[2]
            ]

        v1 = vector_from_points(p1, p2)
        v2 = vector_from_points(p2, p3)
        
        # Calculate dot product
        dot_product = sum(a * b for a, b in zip(v1, v2))
        
        # Calculate magnitudes
        mag1 = math.sqrt(sum(x * x for x in v1))
        mag2 = math.sqrt(sum(x * x for x in v2))
        
        # Avoid division by zero
        if mag1 == 0 or mag2 == 0:
            return 0
        
        # Calculate angle in degrees
        cos_angle = dot_product / (mag1 * mag2)
        cos_angle = max(min(cos_angle, 1), -1)  # Clamp to [-1, 1]
        angle_rad = math.acos(cos_angle)
        return math.degrees(angle_rad)

    def _is_same_point(self, p1, p2, tolerance=1e-10):
        """Check if two points are the same within a tolerance."""
        return all(abs(a - b) < tolerance for a, b in zip(p1, p2))