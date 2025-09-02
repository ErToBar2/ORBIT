from __future__ import annotations

"""Enhanced Photogrammetric flight-path planner for ORBIT.

This planner generates sophisticated flight routes based on bridge trajectory
with support for transition modes, bridge-width-based offsets, and comprehensive
parameter parsing from tab3_textEdit configuration.
"""

import numpy as np
import re
import ast
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional, Any, Union
from pathlib import Path

from ..io.models import Bridge, FlightRoute
from ..io.context import ProjectContext
from .safety import filter_route_outside_zones

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


@dataclass
class EnhancedPhotoParameters:
    """Enhanced parameters for photogrammetric flight planning."""
    # New transition parameters
    transition_mode: int = 1  # 0 = separate sides, 1 = pass middle
    transition_vertical_offset: float = 50.0  # Vertical offset for transition
    transition_horizontal_offset: float = 5.0  # Horizontal offset for transition
    
    # Standard flight route configurations
    standard_flight_routes: Dict[str, Dict[str, float]] = None
    order: List[str] = None
    flight_speed_map: Dict[str, Dict[str, str]] = None
    
    # Other flight parameters (removed outdated ones)
    connection_height: float = 20.0
    num_passes: int = 2
    safety_check_photo: int = 1
    general_height_offset: float = 1.0
    
    def __post_init__(self):
        """Set default values for complex parameters."""
        if self.standard_flight_routes is None:
            self.standard_flight_routes = {
                "101": {"vertical_offset": 8, "distance_offset": 5},
                "102": {"vertical_offset": 3, "distance_offset": 2},
                "201": {"vertical_offset": 8, "distance_offset": 5},
                "202": {"vertical_offset": 3, "distance_offset": 2}
            }
        
        if self.order is None:
            self.order = ["101", "reverse 101", "102", "reverse 102", 
                         "underdeck_safe_flythrough", "201", "reverse 201", "202", "reverse 202"]
        
        if self.flight_speed_map is None:
            self.flight_speed_map = {
                "101": {"speed": "6"}, "102": {"speed": "4"},
                "201": {"speed": "6"}, "202": {"speed": "4"},
                "underdeck_safe_flythrough": {"speed": "2"}
            }


class EnhancedPhotogrammetricPlanner:
    """Enhanced photogrammetric flight planner with transition modes and bridge-width-based offsets."""

    def __init__(self, ctx: ProjectContext, params: EnhancedPhotoParameters | None = None):
        self.ctx = ctx
        self.params = params or EnhancedPhotoParameters()

    def plan(self, bridge: Bridge, bridge_width: float = 20.0, 
             tab3_text_content: str = "") -> List[FlightRoute]:
        """Generate enhanced photogrammetric flight routes.
        
        Args:
            bridge: Bridge model with trajectory
            bridge_width: Width of the bridge in meters
            tab3_text_content: Content from tab3_textEdit for parameter parsing
            
        Returns:
            List of FlightRoute objects
        """
        debug_print("[ENHANCED_PHOTO] 🛩️ Starting enhanced photogrammetric planning...")
        
        if bridge.trajectory.points.size == 0:
            raise ValueError("Bridge trajectory is empty – user must sketch a line first")

        # Parse parameters from tab3_textEdit if provided
        if tab3_text_content.strip():
            parsed_params = self._parse_tab3_parameters(tab3_text_content)
            self._update_params_from_parsed(parsed_params)

        # Get trajectory points
        trajectory = bridge.trajectory.points
        debug_print(f"[ENHANCED_PHOTO] 📍 Trajectory: {len(trajectory)} points")
        debug_print(f"[ENHANCED_PHOTO] 📏 Bridge width: {bridge_width}m")
        debug_print(f"[ENHANCED_PHOTO] 🔄 Transition mode: {self.params.transition_mode}")
        debug_print(f"[ENHANCED_PHOTO] 📋 Route order: {self.params.order}")

        # First, generate all individual route segments
        route_segments = {}
        
        for route_id in self.params.order:
            if route_id == 'transition_mode':
                # Skip transition_mode marker - it's handled separately
                continue
                
            if route_id.startswith('reverse '):
                # Handle reverse routes
                base_route_id = route_id.replace('reverse ', '')
                if base_route_id in self.params.standard_flight_routes:
                    route = self._generate_standard_route(
                        base_route_id, trajectory, bridge_width, reverse=True
                    )
                    if route:
                        route_segments[route_id] = route
            elif route_id == 'underdeck_safe_flythrough':
                # Skip - handled separately in transition logic
                continue
            elif route_id in self.params.standard_flight_routes:
                # Handle standard routes
                route = self._generate_standard_route(
                    route_id, trajectory, bridge_width, reverse=False
                )
                if route:
                    route_segments[route_id] = route

        debug_print(f"[ENHANCED_PHOTO] 📦 Generated {len(route_segments)} route segments")

        # Now connect routes according to order and transition mode
        connected_routes = self._connect_routes_by_order(route_segments, trajectory, bridge_width)
        
        debug_print(f"[ENHANCED_PHOTO] ✅ Created {len(connected_routes)} connected flight paths")
        
        # Apply safety zone filtering if zones exist
        if bridge.safety_zones:
            debug_print(f"[ENHANCED_PHOTO] 🛡️ Applying safety zone filtering...")
            filtered_routes = []
            for route in connected_routes:
                filtered_points = filter_route_outside_zones(route.points, bridge.safety_zones)
                if len(filtered_points) > 0:
                    filtered_route = FlightRoute(
                        points=filtered_points,
                        tags=route.tags[:len(filtered_points)]
                    )
                    filtered_routes.append(filtered_route)
            connected_routes = filtered_routes
            debug_print(f"[ENHANCED_PHOTO] 🛡️ Filtered to {len(connected_routes)} safe routes")

        return connected_routes

    def _generate_standard_route(self, route_id: str, trajectory: np.ndarray, 
                                bridge_width: float, reverse: bool = False) -> FlightRoute | None:
        """Generate a standard photogrammetric route."""
        try:
            print(f"[ROUTE_{route_id}] 🛩️ Generating {'reverse ' if reverse else ''}{route_id}...")
            
            # Get route configuration
            route_config = self.params.standard_flight_routes[route_id]
            vertical_offset = route_config['vertical_offset']
            distance_offset = route_config['distance_offset']
            
            # Calculate offset direction based on route ID
            # Routes starting with '1' (101, 102) -> left side (negative offset)
            # Routes starting with '2' (201, 202) -> right side (positive offset)
            offset_sign = -1 if route_id.startswith('1') else 1
            side_name = "left" if offset_sign == -1 else "right"
            
            print(f"[ROUTE_{route_id}] 📍 {side_name} side, offset={distance_offset}m + {bridge_width/2}m bridge half-width")
            
            # Calculate total horizontal offset: bridge_width/2 + distance_offset
            total_horizontal_offset = (bridge_width / 2) + distance_offset
            
            # Generate offset trajectory
            offset_points = self._create_offset_trajectory(
                trajectory, total_horizontal_offset * offset_sign
            )
            
            # Add vertical offset
            final_points = []
            for x, y, base_z in offset_points:
                final_z = base_z + vertical_offset
                final_points.append([x, y, final_z])
            
            # Reverse if needed
            if reverse:
                final_points.reverse()
                print(f"[ROUTE_{route_id}] 🔄 Reversed waypoint order")
            
            # Create FlightRoute
            route = FlightRoute(
                points=np.array(final_points),
                tags=[f"{route_id}{'_rev' if reverse else ''}" for _ in final_points]
            )
            
            print(f"[ROUTE_{route_id}] ✅ Generated {len(final_points)} waypoints")
            return route
            
        except Exception as e:
            print(f"[ROUTE_{route_id}] ❌ Generation failed: {e}")
            return None

    def _generate_flythrough_route(self, trajectory: np.ndarray, 
                                  bridge_width: float) -> List[FlightRoute]:
        """Generate flythrough route with transition mode logic."""
        try:
            print(f"[FLYTHROUGH] 🛩️ Generating flythrough with transition_mode={self.params.transition_mode}")
            
            routes = []
            
            if self.params.transition_mode == 0:
                # Separate right and left sides
                print("[FLYTHROUGH] 📍 Mode 0: Separate right and left sides")
                
                # Right side route
                right_points = self._create_offset_trajectory(
                    trajectory, (bridge_width / 2) + self.params.transition_horizontal_offset
                )
                right_route = self._create_flythrough_route_points(right_points, "right")
                if right_route:
                    routes.append(right_route)
                
                # Left side route  
                left_points = self._create_offset_trajectory(
                    trajectory, -((bridge_width / 2) + self.params.transition_horizontal_offset)
                )
                left_route = self._create_flythrough_route_points(left_points, "left")
                if left_route:
                    routes.append(left_route)
                    
            else:
                # Mode 1: Pass through middle with transition points
                print("[FLYTHROUGH] 📍 Mode 1: Pass through middle with transition")
                
                # Find middle point of trajectory
                mid_idx = len(trajectory) // 2
                mid_point = trajectory[mid_idx]
                
                # Calculate transition points perpendicular to middle point
                transition_distance = (bridge_width / 2) + self.params.transition_horizontal_offset
                
                # Get direction vector at middle point
                if mid_idx > 0 and mid_idx < len(trajectory) - 1:
                    # Use average direction
                    dir1 = trajectory[mid_idx] - trajectory[mid_idx - 1]
                    dir2 = trajectory[mid_idx + 1] - trajectory[mid_idx]
                    direction = (dir1[:2] + dir2[:2]) / 2
                else:
                    # Use available direction
                    if mid_idx == 0:
                        direction = trajectory[1][:2] - trajectory[0][:2]
                    else:
                        direction = trajectory[-1][:2] - trajectory[-2][:2]
                
                # Normalize and get perpendicular
                direction_norm = np.linalg.norm(direction)
                if direction_norm > 0:
                    direction_unit = direction / direction_norm
                    perp_vector = np.array([-direction_unit[1], direction_unit[0]])
                    
                    # Calculate transition points
                    right_transition = mid_point[:2] + perp_vector * transition_distance
                    left_transition = mid_point[:2] - perp_vector * transition_distance
                    
                    # Create complete route: right side -> right transition -> left transition -> left side
                    complete_points = []
                    
                    # Right side part (start to middle)
                    right_traj = trajectory[:mid_idx+1]
                    right_offset_points = self._create_offset_trajectory(
                        right_traj, (bridge_width / 2) + self.params.transition_horizontal_offset
                    )
                    complete_points.extend(right_offset_points)
                    
                    # Add transition points
                    transition_z = mid_point[2] + self.params.transition_vertical_offset
                    complete_points.append([right_transition[0], right_transition[1], transition_z])
                    complete_points.append([left_transition[0], left_transition[1], transition_z])
                    
                    # Left side part (middle to end) 
                    left_traj = trajectory[mid_idx:]
                    left_offset_points = self._create_offset_trajectory(
                        left_traj, -((bridge_width / 2) + self.params.transition_horizontal_offset)
                    )
                    complete_points.extend(left_offset_points)
                    
                    # Create single continuous route
                    flythrough_route = self._create_flythrough_route_points(complete_points, "transition")
                    if flythrough_route:
                        routes.append(flythrough_route)
                        
                    print(f"[FLYTHROUGH] ✅ Generated transition route with {len(complete_points)} waypoints")
            
            return routes
            
        except Exception as e:
            print(f"[FLYTHROUGH] ❌ Generation failed: {e}")
            return []

    def _create_flythrough_route_points(self, points: List[List[float]], 
                                       side_name: str) -> FlightRoute | None:
        """Create a flythrough route from points."""
        try:
            if not points:
                return None
                
            # Add vertical offset to all points
            final_points = []
            for x, y, base_z in points:
                final_z = base_z + self.params.transition_vertical_offset
                final_points.append([x, y, final_z])
            
            # Use consistent "transition" tag for all transition waypoints
            route = FlightRoute(
                points=np.array(final_points),
                tags=["transition" for _ in final_points]
            )
            
            return route
            
        except Exception as e:
            print(f"[FLYTHROUGH_POINTS] ❌ Failed to create {side_name} route: {e}")
            return None

    def _create_offset_trajectory(self, trajectory: np.ndarray, 
                                 offset_distance: float) -> List[List[float]]:
        """Create an offset trajectory parallel to the main trajectory."""
        try:
            if len(trajectory) < 2:
                return []
            
            offset_points = []
            
            for i in range(len(trajectory)):
                if i == 0:
                    # First point: use direction to next point
                    direction = trajectory[i+1][:2] - trajectory[i][:2]
                elif i == len(trajectory) - 1:
                    # Last point: use direction from previous point
                    direction = trajectory[i][:2] - trajectory[i-1][:2]
                else:
                    # Middle points: use average direction
                    dir1 = trajectory[i][:2] - trajectory[i-1][:2]
                    dir2 = trajectory[i+1][:2] - trajectory[i][:2]
                    direction = (dir1 + dir2) / 2
                
                # Normalize direction and get perpendicular
                direction_norm = np.linalg.norm(direction)
                if direction_norm > 0:
                    direction_unit = direction / direction_norm
                    perp_vector = np.array([-direction_unit[1], direction_unit[0]]) * offset_distance
                    
                    # Create offset point
                    offset_point = trajectory[i][:2] + perp_vector
                    offset_points.append([offset_point[0], offset_point[1], trajectory[i][2]])
                else:
                    # Fallback: use original point
                    offset_points.append(trajectory[i].tolist())
            
            return offset_points
            
        except Exception as e:
            print(f"[OFFSET_TRAJ] ❌ Failed to create offset trajectory: {e}")
            return []

    def _parse_tab3_parameters(self, text_content: str) -> Dict[str, Any]:
        """Parse parameters from tab3_textEdit content."""
        try:
            print("[PARSE_TAB3] 📖 Parsing tab3_textEdit parameters...")
            
            parsed_params = {}
            
            # Define parameter patterns
            patterns = {
                # New transition parameters
                "transition_mode": (r"transition_mode\s*=\s*(\d+)", int),
                "transition_vertical_offset": (r"transition_vertical_offset\s*=\s*([+-]?\d*\.?\d+)", float),
                "transition_horizontal_offset": (r"transition_horizontal_offset\s*=\s*([+-]?\d*\.?\d+)", float),
                
                # Complex parameters
                "standard_flight_routes": (r"standard_flight_routes\s*=\s*({(?:[^{}]|{[^{}]*})*})", ast.literal_eval),
                "order": (r"order\s*=\s*(\[(?:[^\[\]]|\[[^\[\]]*\])*\])", self._safe_parse_order),
                "flight_speed_map": (r"flight_speed_map\s*=\s*({(?:[^{}]|{[^{}]*})*})", ast.literal_eval),
                
                # Other parameters (removed outdated flythrough_underdeck_PF, passover_height_PF, nsamplePointsTrajectory)
                "connection_height": (r"connection_height\s*=\s*([+-]?\d*\.?\d+)", float),
                "num_passes": (r"num_passes\s*=\s*(\d+)", int),
                "safety_check_photo": (r"safety_check_photo\s*=\s*(\d+)", int),
                "general_height_offset": (r"general_height_offset\s*=\s*([+-]?\d*\.?\d+)", float),
            }
            
            for param_name, (pattern, converter) in patterns.items():
                try:
                    match = re.search(pattern, text_content, re.DOTALL | re.MULTILINE)
                    if match:
                        raw_value = match.group(1)
                        parsed_value = converter(raw_value)
                        parsed_params[param_name] = parsed_value
                        print(f"[PARSE_TAB3] ✅ {param_name} = {parsed_value}")
                    else:
                        print(f"[PARSE_TAB3] ⚠️ {param_name} not found")
                except Exception as e:
                    print(f"[PARSE_TAB3] ❌ Failed to parse {param_name}: {e}")
            
            print(f"[PARSE_TAB3] ✅ Parsed {len(parsed_params)} parameters")
            return parsed_params
            
        except Exception as e:
            print(f"[PARSE_TAB3] ❌ Parsing failed: {e}")
            return {}

    def _parse_boolean(self, value: str) -> bool:
        """Parse boolean values from text."""
        if isinstance(value, str):
            return value.lower() in ['true', '1', 'yes', 'on']
        return bool(value)

    def _update_params_from_parsed(self, parsed_params: Dict[str, Any]):
        """Update planner parameters from parsed values."""
        for key, value in parsed_params.items():
            if hasattr(self.params, key):
                setattr(self.params, key, value)
                print(f"[UPDATE_PARAMS] ✅ Updated {key} = {value}") 

    def _safe_parse_order(self, value: str) -> List[str]:
        """Safe parse order from text, handling variable references."""
        try:
            # Attempt strict Python literal evaluation first
            return ast.literal_eval(value)
        except Exception as primary_exc:
            print(f"[PARSE_TAB3] ❌ Failed to parse order with ast: {primary_exc}")
            # ------------------------------------------------------------------
            # Fallback: attempt a lenient comma-separated parse, stripping brackets
    # ------------------------------------------------------------------
            try:
                cleaned = value.strip()
                if cleaned.startswith('[') and cleaned.endswith(']'):
                    cleaned = cleaned[1:-1]  # drop surrounding brackets
                parts = [p.strip().strip('"\'') for p in cleaned.split(',') if p.strip()]
                if parts:
                    print(f"[PARSE_TAB3] ⚠️ Using fallback order parse -> {parts}")
                    return parts
            except Exception as secondary_exc:
                print(f"[PARSE_TAB3] ⚠️ Secondary parse of order failed: {secondary_exc}")
            # Final fallback to default order
            print(f"[PARSE_TAB3] ⚠️ Reverting to default order list")
            return [
                "101", "reverse 101", "102", "reverse 102",
                "underdeck_safe_flythrough", "201", "reverse 201", "202", "reverse 202"
            ]

    def _connect_routes_by_order(self, route_segments: Dict[str, FlightRoute], 
                                 trajectory: np.ndarray, bridge_width: float) -> List[FlightRoute]:
        """Connect routes according to the order specification and transition mode."""
        print(f"[CONNECT_ROUTES] 🔗 Connecting routes with transition_mode={self.params.transition_mode}")
        
        if self.params.transition_mode == 0:
            # Mode 0: Separate left and right sides
            return self._connect_routes_separate_sides(route_segments, trajectory, bridge_width)
        else:
            # Mode 1: Connected with middle transition
            return self._connect_routes_with_transition(route_segments, trajectory, bridge_width)
    
    def _connect_routes_separate_sides(self, route_segments: Dict[str, FlightRoute], 
                                      trajectory: np.ndarray, bridge_width: float) -> List[FlightRoute]:
        """Connect routes as separate left and right side paths (transition_mode=0)."""
        print("[CONNECT_ROUTES] 📍 Mode 0: Creating separate left and right paths")
        
        left_points = []
        left_tags = []
        right_points = []
        right_tags = []
        
        for route_id in self.params.order:
            if route_id == 'transition_mode':
                continue
            
            if route_id in route_segments:
                route = route_segments[route_id]
                # Routes starting with '1' go to left side
                if route_id.startswith('1') or route_id.startswith('reverse 1'):
                    if left_points and len(route.points) > 0:
                        # Add connection between routes
                        connection = self._create_connection(left_points[-1], route.points[0])
                        left_points.extend(connection)
                        left_tags.extend(['connection'] * len(connection))
                    left_points.extend(route.points)
                    left_tags.extend(route.tags)
                # Routes starting with '2' go to right side
                elif route_id.startswith('2') or route_id.startswith('reverse 2'):
                    if right_points and len(route.points) > 0:
                        # Add connection between routes
                        connection = self._create_connection(right_points[-1], route.points[0])
                        right_points.extend(connection)
                        right_tags.extend(['connection'] * len(connection))
                    right_points.extend(route.points)
                    right_tags.extend(route.tags)
        
        routes = []
        if left_points:
            routes.append(FlightRoute(
                points=np.array(left_points),
                tags=left_tags
            ))
            print(f"[CONNECT_ROUTES] ✅ Left side path: {len(left_points)} waypoints")
        
        if right_points:
            routes.append(FlightRoute(
                points=np.array(right_points),
                tags=right_tags
            ))
            print(f"[CONNECT_ROUTES] ✅ Right side path: {len(right_points)} waypoints")
        
        return routes
    
    def _connect_routes_with_transition(self, route_segments: Dict[str, FlightRoute], 
                                       trajectory: np.ndarray, bridge_width: float) -> List[FlightRoute]:
        """Connect all routes with middle transition (transition_mode=1)."""
        print("[CONNECT_ROUTES] 📍 Mode 1: Creating connected path with middle transition")
        
        all_points = []
        all_tags = []
        transition_added = False
        
        # Find the position of 'transition_mode' in order to know when to add transition
        transition_index = -1
        if 'transition_mode' in self.params.order:
            transition_index = self.params.order.index('transition_mode')
        
        for i, route_id in enumerate(self.params.order):
            if route_id == 'transition_mode':
                # Add transition points here
                if not transition_added and all_points:
                    transition_points = self._create_middle_transition(
                        all_points[-1], trajectory, bridge_width, 
                        going_to_right=(i < len(self.params.order) - 1 and 
                                      self.params.order[i+1].startswith('2'))
                    )
                    all_points.extend(transition_points)
                    all_tags.extend(['transition'] * len(transition_points))
                    transition_added = True
                    print(f"[CONNECT_ROUTES] 🔄 Added middle transition: {len(transition_points)} waypoints")
                continue
            
            if route_id in route_segments:
                route = route_segments[route_id]
                if all_points and len(route.points) > 0:
                    # Add connection between routes
                    connection = self._create_connection(all_points[-1], route.points[0])
                    all_points.extend(connection)
                    all_tags.extend(['connection'] * len(connection))
                all_points.extend(route.points)
                all_tags.extend(route.tags)
        
        if all_points:
            connected_route = FlightRoute(
                points=np.array(all_points),
                tags=all_tags
            )
            print(f"[CONNECT_ROUTES] ✅ Connected path: {len(all_points)} waypoints")
            return [connected_route]
        
        return []
    
    def _create_connection(self, point1: np.ndarray, point2: np.ndarray) -> List[np.ndarray]:
        """Create a smooth connection between two points."""
        # Simple linear connection with intermediate point at connection height
        if np.array_equal(point1, point2):
            return []
        
        # Create intermediate point at connection height
        mid_x = (point1[0] + point2[0]) / 2
        mid_y = (point1[1] + point2[1]) / 2
        mid_z = max(point1[2], point2[2]) + self.params.connection_height
        
        return [[mid_x, mid_y, mid_z]]
    
    def _create_middle_transition(self, last_point: np.ndarray, trajectory: np.ndarray, 
                                 bridge_width: float, going_to_right: bool) -> List[List[float]]:
        """Create transition points through the middle of the bridge."""
        # Find the closest point on the trajectory
        distances = [np.linalg.norm(last_point[:2] - traj_pt[:2]) for traj_pt in trajectory]
        closest_idx = np.argmin(distances)
        closest_point = trajectory[closest_idx]
        
        # Get perpendicular direction at this point
        if closest_idx == 0:
            direction = trajectory[1][:2] - trajectory[0][:2]
        elif closest_idx == len(trajectory) - 1:
            direction = trajectory[-1][:2] - trajectory[-2][:2]
        else:
            dir1 = trajectory[closest_idx][:2] - trajectory[closest_idx-1][:2]
            dir2 = trajectory[closest_idx+1][:2] - trajectory[closest_idx][:2]
            direction = (dir1 + dir2) / 2
        
        # Normalize and get perpendicular
        direction_norm = np.linalg.norm(direction)
        if direction_norm > 0:
            direction_unit = direction / direction_norm
            perp_vector = np.array([-direction_unit[1], direction_unit[0]])
            
            # Calculate transition points
            transition_distance = (bridge_width / 2) + self.params.transition_horizontal_offset
            transition_z = closest_point[2] + self.params.transition_vertical_offset
            
            # Current side transition point
            current_side = -1 if not going_to_right else 1
            current_transition = closest_point[:2] + current_side * perp_vector * transition_distance
            
            # Opposite side transition point
            opposite_transition = closest_point[:2] - current_side * perp_vector * transition_distance
            
            return [
                [current_transition[0], current_transition[1], transition_z],
                [opposite_transition[0], opposite_transition[1], transition_z]
            ]
        
        return []

# Keep backward compatibility with original planner
class PhotogrammetricPlanner(EnhancedPhotogrammetricPlanner):
    """Backward compatibility wrapper for the original PhotogrammetricPlanner."""
    
    def __init__(self, ctx: ProjectContext, params=None):
        # Convert old parameters to new format if needed
        enhanced_params = EnhancedPhotoParameters()
        if params:
            # Map old parameters to new ones where possible
            if hasattr(params, 'side_offset'):
                enhanced_params.transition_horizontal_offset = params.side_offset
            if hasattr(params, 'altitude_agl'):
                enhanced_params.passover_height_PF = params.altitude_agl
                
        super().__init__(ctx, enhanced_params)
    
    def plan(self, bridge: Bridge) -> List[FlightRoute]:
        """Maintain original interface for backward compatibility."""
        return super().plan(bridge, bridge_width=20.0, tab3_text_content="")


@dataclass
class PhotoPlanParameters:
    """Backward compatibility wrapper for original PhotoPlanParameters."""
    side_offset: float = 8.0          # metres left/right of trajectory
    altitude_agl: float = 30.0        # metres above ground (AGL) if AGL vertical ref
    line_spacing: float = 15.0        # metres vertical spacing for multi-alt runs (not used yet) 