"""
Enhanced safety processor for flight routes with improved safety zone handling.

This module provides advanced functionality to check and adjust flight routes for safety
around defined safety zones. It handles:
- Resampling routes for more detailed processing
- Height adjustments based on safety zone clearances
- Lateral avoidance for safety zones (finding closest exit points)
- Point deletion for zones marked with 0
- Enhanced route simplification based on angle changes
- Duplicate point removal
"""

import numpy as np
from shapely.geometry import Point, Polygon, LineString
from shapely.ops import nearest_points
from typing import List, Union, Tuple, Dict, Set
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

def error_debug_print(*args, **kwargs) -> None:
    """Print function that always outputs (for errors)."""
    print(*args, **kwargs)


def simplify_route_standalone(flight_route, min_angle_change=15, resample_interval=0.5):
    """
    Standalone route simplification function that can be used independently of safety zones.
    
    Args:
        flight_route (list): List of [x, y, z] coordinates defining the flight route
        min_angle_change (float): Minimum angle change for simplification (degrees)
        resample_interval (float): Interval for resampling before simplification
        
    Returns:
        list: Simplified flight route
    """
    if not flight_route or len(flight_route) < 3:
        return flight_route
    
    debug_print(f"\n=== Standalone Route Simplification ===")
    debug_print(f"Initial route points: {len(flight_route)}")
    
    # Create a temporary processor for simplification only
    temp_processor = EnhancedSafetyProcessor(
        flight_route, 
        safety_zones=[],  # Empty safety zones
        safety_zones_clearance=[],
        takeoff_altitude=0
    )
    
    # Step 1: Resample route for consistent spacing
    temp_processor.resample_route(resample_interval)
    debug_print(f"After resampling: {len(temp_processor.flight_route)} points")
    
    # Step 2: Simplify route based on angle changes
    temp_processor.enhanced_angle_based_simplification(min_angle_change=min_angle_change)
    debug_print(f"After simplification: {len(temp_processor.flight_route)} points")
    
    # Step 3: Remove duplicates
    temp_processor.remove_consecutive_duplicates()
    debug_print(f"After duplicate removal: {len(temp_processor.flight_route)} points")
    
    debug_print(f"✅ Simplified route from {len(flight_route)} to {len(temp_processor.flight_route)} points")
    
    return temp_processor.flight_route


class EnhancedSafetyProcessor:
    """Enhanced processor for flight routes to ensure they meet safety requirements."""

    def __init__(self, flight_route, safety_zones, safety_zones_clearance, takeoff_altitude=0, verbose=False):
        """
        Initialize the enhanced safety processor.

        Args:
            flight_route (list): List of [x, y, z] coordinates defining the flight route
            safety_zones (list): List of safety zone polygons, each defined by list of [x, y] or [x, y, z] coordinates
            safety_zones_clearance (list): List of [min_height, max_height] for each safety zone
            takeoff_altitude (float, optional): Base altitude for takeoff. Defaults to 0.
        """
        self.flight_route = flight_route
        self.safety_zones = safety_zones
        self.safety_zones_clearance = safety_zones_clearance
        self.takeoff_altitude = takeoff_altitude
        self.verbose = verbose
        
        # Initialize zone_polygons
        self.zone_polygons = self._create_zone_polygons()
        
        self._validate_inputs()

    def _validate_inputs(self):
        """Validate input data formats and consistency."""
        if not self.flight_route or not isinstance(self.flight_route[0], (list, tuple)):
            raise ValueError("Flight route must be a non-empty list of coordinates")
        
        if not self.safety_zones:
            debug_print("Warning: No safety zones provided")
            self.safety_zones = []
            
        # Basic info
        
        debug_print(f"Number of safety zones: {len(self.safety_zones)}")
        # defer detailed checks until after resampling in process_route()"

    def _create_zone_polygons(self):
        """Create Shapely polygons from safety zones for efficient spatial operations."""
        polygons = []
        for i, zone in enumerate(self.safety_zones):
            if len(zone) < 3:
                debug_print(f"Warning: Safety zone {i} has less than 3 points, skipping")
                polygons.append(None)
                continue
            
            try:
                # Extract 2D coordinates for polygon
                zone_2d = [(p[0], p[1]) for p in zone]
                # Ensure polygon is closed
                if zone_2d[0] != zone_2d[-1]:
                    zone_2d.append(zone_2d[0])
                polygon = Polygon(zone_2d[:-1])  # Remove duplicate last point for Shapely
                
                if not polygon.is_valid:
                    debug_print(f"Warning: Safety zone {i} creates invalid polygon, attempting to fix")
                    polygon = polygon.buffer(0)  # Attempt to fix self-intersections
                    
                polygons.append(polygon)
            except Exception as e:
                debug_print(f"Error creating polygon for safety zone {i}: {e}")
                polygons.append(None)
                
        return polygons

    def resample_route(self, interval=0.5):
        """
        Resample the flight route to ensure consistent point spacing.

        Args:
            interval (float, optional): Desired spacing between points. Defaults to 0.5.

        Returns:
            list: Resampled flight route
        """
        
        
        if len(self.flight_route) < 2:
            return self.flight_route

        resampled_route = [list(self.flight_route[0])]
        
        for i in range(1, len(self.flight_route)):
            p1 = np.array(self.flight_route[i - 1][:3], dtype=float)
            p2 = np.array(self.flight_route[i][:3], dtype=float)
            
            distance = np.linalg.norm(p2 - p1)
            
            if distance > interval:
                num_points = int(distance / interval)
                for j in range(1, num_points + 1):
                    t = j / (num_points + 1)
                    interpolated = p1 + t * (p2 - p1)
                    interp_list = interpolated.tolist()
                    # Preserve tag from first point if available
                    if len(self.flight_route[i - 1]) > 3:
                        interp_list.append(self.flight_route[i - 1][3])
                    resampled_route.append(interp_list)
            
            resampled_route.append(list(self.flight_route[i]))

        debug_print(f"Route resampled from {len(self.flight_route)} to {len(resampled_route)} points")
        self.flight_route = resampled_route
        return resampled_route

    def check_points_in_zones(self):
        """Return dict mapping point-index → list of zone-indices the point is inside (XY and Z)."""
        points_in_zones = {}
        for zone_idx, polygon in enumerate(self.zone_polygons):
            if polygon is None:
                continue
            # vertical limits for this zone (add take-off altitude so that clearances remain relative)
            if zone_idx < len(self.safety_zones_clearance):
                z_min, z_max = self.safety_zones_clearance[zone_idx]
                z_min += self.takeoff_altitude
                z_max += self.takeoff_altitude
            else:
                z_min, z_max = None, None
            pts = []
            for idx, pt in enumerate(self.flight_route):
                inside_xy = self._is_point_in_polygon(pt[:2], polygon)
                inside_z = True
                if z_min is not None and z_max is not None:
                    inside_z = z_min <= pt[2] <= z_max
                if inside_xy and inside_z:
                    pts.append(idx)
                    points_in_zones.setdefault(idx, []).append(zone_idx)
            # overview print – will be called from process_route after resampling
            if self.verbose:
                debug_print(f"Zone {zone_idx}: {len(pts)} pts inside of {len(self.flight_route)}")
        return points_in_zones
    def adjust_route_for_safety(self, safety_zones_clearance_adjust):
        """
        Adjust flight route based on safety zone clearances with enhanced logic.

        Args:
            safety_zones_clearance_adjust (list): Adjustment values for each safety zone
                - Positive value: Adjust Z height to this value
                - 0: Delete points in this zone
                - -1: Find closest exit in XY plane (lateral avoidance)

        Returns:
            list: Adjusted flight route
        """
        
        
        # First, check which points are in zones
        points_in_zones = self.check_points_in_zones()
        
        if not points_in_zones:
            debug_print("No points in safety zones, returning original route")
            return self.flight_route
        
        # Process adjustments
        adjusted_route = []
        points_to_skip = set()
        # statistics per zone
        stats = {idx: {'deleted':0,'height':0,'lateral':0} for idx in range(len(self.safety_zones))}
        
        for point_idx, point in enumerate(self.flight_route):
            if point_idx in points_to_skip:
                continue
                
            if point_idx in points_in_zones:
                # Point is in one or more safety zones
                zone_indices = points_in_zones[point_idx]
                
                # NEW: Handle overlapping zones by prioritizing the highest adjustment value
                if len(zone_indices) > 1:
                    if self.verbose:
                        debug_print(f"Point {point_idx} in multiple zones: {zone_indices}")
                    
                    # Find the zone with the highest adjustment value
                    best_zone_idx = None
                    best_adjustment = -float('inf')
                    
                    for zone_idx in zone_indices:
                        if zone_idx >= len(safety_zones_clearance_adjust):
                            continue
                        raw_adj = safety_zones_clearance_adjust[zone_idx]
                        adjustment_value = raw_adj[0] if isinstance(raw_adj, (list, tuple)) else raw_adj
                        
                        if self.verbose:
                            debug_print(f"  Zone {zone_idx}: adjustment = {adjustment_value}")
                        
                        # Prioritize higher adjustment values
                        if adjustment_value > best_adjustment:
                            best_adjustment = adjustment_value
                            best_zone_idx = zone_idx
                    
                    if best_zone_idx is not None:
                        zone_idx = best_zone_idx
                        adjustment_value = best_adjustment
                        if self.verbose:
                            debug_print(f"  Selected zone {zone_idx} with adjustment {adjustment_value}")
                    else:
                        # Fallback to first zone if no valid adjustments found
                        zone_idx = zone_indices[0]
                        if zone_idx >= len(safety_zones_clearance_adjust):
                            debug_print(f"[WARNING] No adjustment value provided for safety zone {zone_idx}; skipping point")
                            continue
                        raw_adj = safety_zones_clearance_adjust[zone_idx]
                        adjustment_value = raw_adj[0] if isinstance(raw_adj, (list, tuple)) else raw_adj
                else:
                    # Single zone case - use existing logic
                    zone_idx = zone_indices[0]
                    
                    if zone_idx >= len(safety_zones_clearance_adjust):
                        debug_print(f"[WARNING] No adjustment value provided for safety zone {zone_idx}; skipping point")
                        continue
                    raw_adj = safety_zones_clearance_adjust[zone_idx]
                    # allow scalar or list/tuple
                    if isinstance(raw_adj, (list, tuple)):
                        adjustment_value = raw_adj[0]
                    else:
                        adjustment_value = raw_adj
                    
                if self.verbose:
                    debug_print(f"Point {point_idx} in zone {zone_idx}, adjustment: {adjustment_value}")
                
                if adjustment_value == 0:
                    # Delete point
                    if self.verbose:
                        debug_print("  Action: Delete point")
                    points_to_skip.add(point_idx)
                    stats[zone_idx]['deleted'] += 1
                    continue
                    
                elif adjustment_value == -1:
                    # Lateral avoidance – build a detour around the polygon
                    if self.verbose:
                        debug_print("  Action: Lateral avoidance (detour)")

                    entry_idx = point_idx  # first point inside

                    # Find the index of the first point after we leave this zone
                    exit_idx = entry_idx
                    while exit_idx < len(self.flight_route) and \
                          self._is_point_in_polygon(self.flight_route[exit_idx][:2], self.zone_polygons[zone_idx]):
                        exit_idx += 1

                    if exit_idx >= len(self.flight_route):
                        # Could not find an exit – delete remaining in-zone points as fallback
                        points_to_skip.update(range(entry_idx, len(self.flight_route)))
                        stats[zone_idx]['deleted'] += len(range(entry_idx, len(self.flight_route)))
                        break

                    # Generate detour path hugging the polygon boundary
                    exit_points = self._find_lateral_exit_path(entry_idx, exit_idx, zone_idx)
                    if exit_points:
                        adjusted_route.extend(exit_points)
                        # Skip the original in-zone segment so it is removed from the route
                        points_to_skip.update(range(entry_idx, exit_idx))
                        stats[zone_idx]['lateral'] += len(exit_points)
                    else:
                        # Fallback: delete the in-zone segment
                        points_to_skip.update(range(entry_idx, exit_idx))
                        stats[zone_idx]['deleted'] += len(range(entry_idx, exit_idx))

                        
                elif adjustment_value > 0:
                    # Adjust Z height
                    z_min, z_max = self.safety_zones_clearance[zone_idx]
                    new_height = adjustment_value + self.takeoff_altitude
                    if z_min <= adjustment_value <= z_max:
                        debug_print(f"  Warning: Adjustment {adjustment_value} within unsafe range [{z_min}, {z_max}]") 
                        
                    if self.verbose:
                        debug_print(f"  Action: Adjust height to {new_height}")
                    adjusted_point = list(point)
                    adjusted_point[2] = new_height
                    adjusted_route.append(adjusted_point)
                    stats[zone_idx]['height'] += 1
                    
            else:
                # Point not in any safety zone
                adjusted_route.append(list(point))
        
        if self.verbose:
            total_before = len(self.flight_route)
            total_after = len(adjusted_route)
            debug_print(f"Route adjusted: {total_before} → {total_after} points")
            for z_idx, info in stats.items():
                if any(info.values()):
                    debug_print(f"  Zone {z_idx}: deleted {info['deleted']}, height_adj {info['height']}, lateral_pts {info['lateral']}")
        self.flight_route = adjusted_route
        return adjusted_route

    def _is_point_in_polygon(self, point_2d, polygon):
        """Check if a 2D point is inside a polygon using Shapely."""
        try:
            point = Point(point_2d[0], point_2d[1])
            return polygon.contains(point) or polygon.touches(point)
        except Exception as e:
            debug_print(f"Error checking point in polygon: {e}")
            return False

    def _find_lateral_exit_path(self, entry_idx, exit_idx, zone_idx):
        """
        Return a detour that skirts the polygon along the shorter boundary arc.
        entry_idx:  index of first point inside
        exit_idx :  index of first point outside after inside segment
        """
        polygon  = self.zone_polygons[zone_idx]
        boundary = polygon.exterior
        L        = boundary.length
        STEP     = 1.0       # m between samples
        CLR      = 0.0       # no outward clearance; points lie on polygon boundary

        cur_pt   = self.flight_route[entry_idx-1]   # last outside pt (entry segment)
        next_pt  = self.flight_route[exit_idx]      # first outside pt (exit segment)

        # project on boundary
        p_entry  = nearest_points(Point(cur_pt[0],  cur_pt[1]),  boundary)[1]
        p_exit   = nearest_points(Point(next_pt[0], next_pt[1]), boundary)[1]
        s1       = boundary.project(p_entry)
        s2       = boundary.project(p_exit)

        fwd  = (s2 - s1) % L          # CCW
        back = (s1 - s2) % L          # CW
        ccw  = fwd <= back            # choose shorter direction
        dist = fwd if ccw else back

        # helper to push a point CLR metres outward
        cen = np.array([polygon.centroid.x, polygon.centroid.y])
        def _outward(pt):
            v = np.array([pt.x, pt.y]) - cen
            if np.linalg.norm(v) == 0:               # shouldn't happen
                v = np.array([1.0, 0.0])
            v = v / np.linalg.norm(v)
            return [pt.x + v[0]*CLR, pt.y + v[1]*CLR]

        # build detour
        steps   = int(dist // STEP) + 1
        arc_pts = []
        for k in range(1, steps+1):
            ds = k * STEP
            s  = (s1 + ds) % L if ccw else (s1 - ds) % L
            arc_pts.append(_outward(boundary.interpolate(s)))

        # assemble: entry_projection, arc, exit_projection
        detour  = [_outward(p_entry)] + arc_pts + [_outward(p_exit)]

        # copy altitude of entry point
        for p in detour:
            p.append(cur_pt[2])

        return detour

    def _get_points_to_skip_in_zone(self, start_idx, zone_idx):
        """Get indices of subsequent points that are in the same safety zone."""
        polygon = self.zone_polygons[zone_idx]
        if polygon is None:
            return set()
            
        skip_indices = set()
        for idx in range(start_idx + 1, len(self.flight_route)):
            if self._is_point_in_polygon(self.flight_route[idx][:2], polygon):
                skip_indices.add(idx)
            else:
                break  # Stop when we exit the zone
                
        return skip_indices

    def enhanced_angle_based_simplification(self, min_angle_change=15, 
                                          preserve_critical_points=True):
        """
        Enhanced route simplification using angle-based criteria only.
        
        After resampling creates dense point cloud for safety zone handling,
        this step reduces points to minimum necessary based on direction changes.
        
        Args:
            min_angle_change (float): Minimum angle change to keep a point (degrees)
            preserve_critical_points (bool): Whether to preserve entry/exit points of safety zones
            
        Returns:
            list: Simplified flight route
        """
        
        
        if len(self.flight_route) < 3:
            return self.flight_route
            
        # Identify critical points (safety zone boundaries)
        critical_points = set()
        if preserve_critical_points:
            critical_points = self._identify_critical_points()
            
        simplified_route = [self.flight_route[0]]
        last_kept_idx = 0
        
        for i in range(1, len(self.flight_route) - 1):
            # Always keep critical points
            if i in critical_points:
                simplified_route.append(self.flight_route[i])
                last_kept_idx = i
                continue
                
            # Check angle change only
            p1 = self.flight_route[last_kept_idx]
            p2 = self.flight_route[i]
            p3 = self.flight_route[i + 1]
            
            angle = self._calculate_angle_change(p1, p2, p3)
            
            # Keep point if significant angle change (direction change)
            if abs(angle) > min_angle_change:
                simplified_route.append(p2)
                last_kept_idx = i
        
        # Always keep last point
        simplified_route.append(self.flight_route[-1])
        
        debug_print(f"Simplified from {len(self.flight_route)} to {len(simplified_route)} points")
        debug_print(f"Preserved {len(critical_points)} critical points")
        
        self.flight_route = simplified_route
        return simplified_route

    def _identify_critical_points(self):
        """Identify critical points such as safety zone entry/exit points."""
        critical = set()
        
        for i in range(len(self.flight_route)):
            point = self.flight_route[i]
            in_any_zone = False
            
            for polygon in self.zone_polygons:
                if polygon and self._is_point_in_polygon(point[:2], polygon):
                    in_any_zone = True
                    break
                    
            # Check if this is a transition point
            if i > 0:
                prev_in_zone = False
                for polygon in self.zone_polygons:
                    if polygon and self._is_point_in_polygon(self.flight_route[i-1][:2], polygon):
                        prev_in_zone = True
                        break
                        
                if in_any_zone != prev_in_zone:
                    # This is a transition point
                    critical.add(i)
                    if i > 0:
                        critical.add(i - 1)
                        
        return critical

    def _calculate_angle_change(self, p1, p2, p3):
        """Calculate the angle change between three consecutive points."""
        v1 = np.array(p2[:3], dtype=float) - np.array(p1[:3], dtype=float)
        v2 = np.array(p3[:3], dtype=float) - np.array(p2[:3], dtype=float)
        
        # Normalize vectors
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        
        if norm1 == 0 or norm2 == 0:
            return 0
            
        v1_norm = v1 / norm1
        v2_norm = v2 / norm2
        
        # Calculate angle
        dot_product = np.clip(np.dot(v1_norm, v2_norm), -1, 1)
        angle_rad = np.arccos(dot_product)
        
        return np.degrees(angle_rad)

    def remove_consecutive_duplicates(self, tolerance=0.001):
        """
        Remove consecutive duplicate points from the flight route.
        
        Args:
            tolerance (float): Distance tolerance for considering points as duplicates
            
        Returns:
            list: Flight route with duplicates removed
        """
        if not self.flight_route:
            return self.flight_route
            
        unique_route = [self.flight_route[0]]
        
        for point in self.flight_route[1:]:
            distance = np.linalg.norm(np.array(point[:3], dtype=float) - np.array(unique_route[-1][:3], dtype=float))
            if distance > tolerance:
                unique_route.append(point)
                
        if self.verbose:
            debug_print(f"Removed {len(self.flight_route) - len(unique_route)} duplicate points")
        self.flight_route = unique_route
        return unique_route

    def process_route(self, safety_zones_clearance_adjust, resample_interval=0.5, min_angle_change=15):
        """
        Complete route processing pipeline.
        
        Args:
            safety_zones_clearance_adjust (list): Adjustment values for each safety zone
            resample_interval (float): Interval for resampling
            min_angle_change (float): Minimum angle change for simplification (degrees)
            
        Returns:
            list: Fully processed and optimized route
        """

        
        # Step 1: Resample route
        self.resample_route(resample_interval)

        # Calculate number of inlier points for each safety zone
        points_in_zones = self.check_points_in_zones()
        inliers_per_zone = [0] * len(self.safety_zones)
        for _, zone_indices in points_in_zones.items():
            for z in zone_indices:
                if z < len(inliers_per_zone):
                    inliers_per_zone[z] += 1

        # Overview print of safety zones with adjustment values
        for idx, zone in enumerate(self.safety_zones):
            if len(zone) == 0:
                continue
            try:
                raw_adj = safety_zones_clearance_adjust[idx]
                adj_val = raw_adj[0] if isinstance(raw_adj, (list, tuple)) else raw_adj
            except IndexError:
                adj_val = "<none>"
            debug_print(f"Safety Zone {idx}: {inliers_per_zone[idx]} points adjusting to {adj_val}")

        # Step 2: Adjust for safety zones

        # Step 2: Adjust for safety zones
        self.adjust_route_for_safety(safety_zones_clearance_adjust)
        
        # Step 3: Simplify route with custom angle threshold
        self.enhanced_angle_based_simplification(min_angle_change=min_angle_change)
        
        # Step 4: Remove duplicates
        self.remove_consecutive_duplicates()
        
        debug_print(f"\nFinal route: {len(self.flight_route)} points (using {min_angle_change}° angle threshold)")
        
        return self.flight_route