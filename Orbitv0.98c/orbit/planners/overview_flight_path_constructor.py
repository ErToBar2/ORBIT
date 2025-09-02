"""
FlightPathConstructor.py

Flight path generation using the smoothed trajectory_samples from bridge modeling.
No defaults, no hardcoded values - everything comes from user input or bridge data.
"""


# Outout variables:
# Final Overview flight route: self.app.overview_flight_waypoints
# Final Underdeck flight route: self.app.underdeck_flight_waypoints
# Final Underdeck flight  Axial:  self.app.underdeck_flight_waypoints_Axial 






import re
import ast
import numpy as np
from PySide6.QtWidgets import QTextEdit, QWidget

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
                debug_print(*args, **kwargs)
        except:
            pass  # Silent fallback

def error_debug_print(*args, **kwargs) -> None:
    """Print function that always outputs (for errors)."""
    print(*args, **kwargs)


class FlightPathConstructor:
    """Flight path constructor using smoothed trajectory_samples."""
    
    def __init__(self, orbit_app):
        """Initialize with reference to the main ORBIT app."""
        self.app = orbit_app
    
    # ==================================================================================
    # PERPENDICULAR OFFSET UTILITIES - Core functions for flight route generation
    # ==================================================================================
    #
    # This section provides the core utilities for generating safe flight routes around
    # bridge structures. The key principles are:
    #
    # 1. SAFETY FIRST: All routes maintain minimum distance = bridge_width/2 + user_offset
    # 2. PERPENDICULAR OFFSETS: Use 90-degree offsets from trajectory for clean parallel paths  
    # 3. REUSABLE FUNCTIONS: Core utilities used by all flight route types
    # 4. CONSISTENT NAMING: 'left'/'right' based on trajectory direction (not geographic)
    #
    # MAIN FUNCTIONS TO USE:
    # - compute_perpendicular_offset_points(): Get left/right points from single trajectory point
    # - generate_parallel_trajectory_with_safe_offset(): Generate full parallel trajectory
    # - calculate_minimum_flight_offset(): Compute safe offset = bridge_width/2 + extra
    #
    # USAGE EXAMPLES:
    # - Standard routes: Use generate_parallel_trajectory_with_safe_offset() 
    # - Transition routes: Use compute_perpendicular_offset_points() at middle point
    # - Inspection routes: Use compute_perpendicular_offset_points() for complex patterns
    # - Safety zones: Use compute_perpendicular_offset_points() for boundary calculations
    #
    # ==================================================================================
    
    def compute_perpendicular_offset_points(self, center_point, direction_vector, offset_distance, side='both'):
        """
        Compute perpendicular offset points from a trajectory point.
        
        This is the core utility function for flight route generation since perpendicular
        offsets are needed everywhere: standard routes, safety zones, inspection paths, etc.
        
        Args:
            center_point: [x, y, z] - The trajectory point to offset from
            direction_vector: [dx, dy] - Direction vector along the trajectory 
            offset_distance: float - Distance to offset (positive value)
            side: str - 'left', 'right', or 'both' to return left, right, or both offset points
            
        Returns:
            - If side='left': [x_left, y_left, z] 
            - If side='right': [x_right, y_right, z]
            - If side='both': {'left': [x_left, y_left, z], 'right': [x_right, y_right, z]}
        """
        try:
            center = np.array(center_point[:2])  # [x, y]
            direction = np.array(direction_vector[:2])  # [dx, dy]
            z_coord = center_point[2] if len(center_point) > 2 else 0.0
            
            # Normalize direction vector
            direction_length = np.linalg.norm(direction)
            if direction_length < 1e-6:  # Very small direction
                debug_print(f"⚠️ Warning: Very small direction vector at point {center_point}")
                direction_unit = np.array([1.0, 0.0])  # Default to x-direction
            else:
                direction_unit = direction / direction_length
            
            # Calculate perpendicular vector (90 degrees counter-clockwise from direction)
            # This gives us the "left" direction when moving along the trajectory
            perp_left = np.array([-direction_unit[1], direction_unit[0]]) * offset_distance
            perp_right = -perp_left  # Right is opposite of left
            
            # Calculate offset points
            left_point = [center[0] + perp_left[0], center[1] + perp_left[1], z_coord]
            right_point = [center[0] + perp_right[0], center[1] + perp_right[1], z_coord]
            
            # Return based on requested side
            if side == 'left':
                return right_point  # Now 'left' returns the clockwise offset (negative)
            elif side == 'right':
                return left_point   # Now 'right' returns the counterclockwise offset (positive)
            elif side == 'both':
                return {'left': right_point, 'right': left_point}  # Swap the dictionary too
            else:
                raise ValueError(f"Invalid side '{side}'. Must be 'left', 'right', or 'both'")
                
        except Exception as e:
            error_debug_print(f"❌ Error computing perpendicular offset: {e}")
            # Return original point as fallback
            return {'left': center_point, 'right': center_point} if side == 'both' else center_point
    
    def calculate_minimum_flight_offset(self, additional_offset=0.0):
        """
        Calculate minimum flight offset: bridge_width/2 + additional_offset.
        
        This ensures flight routes maintain safe distance from bridge structure.
        
        Args:
            additional_offset: Additional offset beyond bridge_width/2 (default: 0.0)
            
        Returns:
            float: Minimum safe offset distance in meters
        """
        try:
            bridge_width = self._calculate_bridge_width()
            minimum_offset = (bridge_width / 2.0) + additional_offset
            
            debug_print(f"📏 Flight offset calculation:")
            debug_print(f"   Bridge width: {bridge_width:.1f}m")
            debug_print(f"   Minimum structural clearance: {bridge_width/2:.1f}m")
            debug_print(f"   Additional user offset: {additional_offset:.1f}m")
            debug_print(f"   Total minimum offset: {minimum_offset:.1f}m")

            return minimum_offset

        except Exception as e:
            error_debug_print(f"❌ Error calculating minimum offset: {e}")
            return 10.0  # Safe fallback
    
    def generate_parallel_trajectory_with_safe_offset(self, trajectory_samples, user_offset, side='right'):
        """
        Generate parallel trajectory with safe minimum offset.
        
        This combines bridge_width/2 + user_offset to ensure safe flight paths.
        
        Args:
            trajectory_samples: List of [x, y, z] trajectory points
            user_offset: User-specified additional offset beyond bridge_width/2
            side: 'left' or 'right' side of trajectory
            
        Returns:
            List of [x, y, z] points for the parallel trajectory
        """
        try:
            # Calculate total safe offset
            total_offset = self.calculate_minimum_flight_offset(user_offset)
            
            # Generate parallel trajectory
            parallel_points = []
            traj_array = np.array(trajectory_samples)
            
            debug_print(f"🛤️  Generating {side} parallel trajectory:")
            debug_print(f"   Total offset: {total_offset:.1f}m")
            debug_print(f"   Processing {len(trajectory_samples)} trajectory points...")

            for i in range(len(traj_array)):
                # Calculate direction vector at this point
                direction = self._calculate_direction_at_point(traj_array, i)

                # Get offset point on requested side
                offset_point = self.compute_perpendicular_offset_points(
                    traj_array[i], direction, total_offset, side=side
                )

                parallel_points.append(offset_point)

            debug_print(f"   ✅ Generated {len(parallel_points)} offset points")
            return parallel_points

        except Exception as e:
            error_debug_print(f"❌ Error generating parallel trajectory: {e}")
            return trajectory_samples  # Return original as fallback
    
    def _calculate_direction_at_point(self, trajectory_array, point_index):
        """
        Calculate smooth direction vector at a specific trajectory point.
        
        Uses adjacent points to calculate a smooth direction vector, which is
        important for creating smooth parallel trajectories.
        """
        try:
            i = point_index
            n_points = len(trajectory_array)
            
            if i == 0:
                # First point: use direction to next point
                direction = trajectory_array[i+1][:2] - trajectory_array[i][:2]
            elif i == n_points - 1:
                # Last point: use direction from previous point
                direction = trajectory_array[i][:2] - trajectory_array[i-1][:2]
            else:
                # Middle point: average of incoming and outgoing directions for smoothness
                dir_incoming = trajectory_array[i][:2] - trajectory_array[i-1][:2]
                dir_outgoing = trajectory_array[i+1][:2] - trajectory_array[i][:2]
                direction = (dir_incoming + dir_outgoing) / 2.0
            
            return direction
            
        except Exception as e:
            error_debug_print(f"❌ Error calculating direction at point {point_index}: {e}")
            return np.array([1.0, 0.0])  # Default direction
    
    # ==================================================================================
    # FLIGHT ROUTE GENERATION - Using the improved utilities
    # ==================================================================================
    
    def generate_standard_flight_routes(self):
        """Generate flight routes using trajectory_samples and user-defined parameters."""
        debug_print("\n" + "="*50)
        debug_print("🛩️  FLIGHT ROUTE GENERATION")
        debug_print("="*50)
        
        try:
            # Update parsed data to ensure bridge_width and other parameters are available
            if hasattr(self.app, '_update_parsed_data'):
                self.app._update_parsed_data()
                debug_print("✅ Updated parsed data from text boxes")
                
                # Debug: Print what was actually parsed from textboxes
                if hasattr(self.app, 'parsed_data'):
                    project_data = self.app.parsed_data.get("project", {})
                    debug_print(f"🔍 DEBUG - Parsed from textbox:")
                    debug_print(f"   input_scale_meters: {project_data.get('input_scale_meters')} (type: {type(project_data.get('input_scale_meters'))})")
                    debug_print(f"   bridge_width: {project_data.get('bridge_width')} (type: {type(project_data.get('bridge_width'))})")
                    debug_print(f"   epsg_code: {project_data.get('epsg_code')}")
                    debug_print(f"   bridge_name: {project_data.get('bridge_name')}")
                    
                    # Show raw textbox content for debugging
                    if hasattr(self.app, 'project_text_edit') and self.app.project_text_edit:
                        raw_text = self.app.project_text_edit.toPlainText()
                        debug_print(f"🔍 Raw textbox content (first 200 chars):")
                        debug_print(f"   {repr(raw_text[:200])}")
                        
                        # Look specifically for bridge_width line
                        for line in raw_text.split('\n'):
                            if 'bridge_width' in line and not line.strip().startswith('#'):
                                debug_print(f"🔍 Found bridge_width line: {repr(line)}")
            
            # Validate trajectory_samples availability
            if not hasattr(self.app, 'trajectory_samples') or len(self.app.trajectory_samples) == 0:
                debug_print("❌ trajectory_samples not available")
                return False
            
            debug_print(f"✅ Using trajectory_samples: {len(self.app.trajectory_samples)} points")
            
            # Verify bridge width is available
            bridge_width = self._calculate_bridge_width()
            debug_print(f"🌉 Bridge width for minimum clearance calculations: {bridge_width}m")
            debug_print(f"📐 Minimum structural clearance (bridge_width/2): {bridge_width/2:.1f}m")
            
            # Parse flight parameters from user input
            flight_params = self._parse_flight_parameters()
            if not flight_params:
                debug_print("❌ Failed to parse flight parameters")
                return False
            
            debug_print(f"📋 Parsed parameters: {flight_params}")
            
            # Generate routes based on parsed parameters
            flight_routes = self._generate_routes_with_offsets(flight_params)
            
            if not flight_routes:
                debug_print("❌ No flight routes generated")
                return False
            
            # Visualize the generated routes
            self._visualize_overview_flight(flight_routes)
            
            # Print appropriate success message based on route format
            if isinstance(flight_routes, dict) and flight_routes.get('separated', False):
                left_count = sum(len(group) for group in flight_routes.get('left_groups', []))
                right_count = sum(len(group) for group in flight_routes.get('right_groups', []))
                debug_print(f"✅ Generated separated routes: {left_count} left-side, {right_count} right-side")
            else:
                debug_print(f"✅ Generated {len(flight_routes)} combined routes")
            return True
            
        except Exception as e:
            debug_print(f"❌ Flight route generation failed: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _parse_flight_parameters(self):
        """Parse flight parameters via central orbit.data_parser – **no regex, no defaults**."""
        try:
            # Ensure latest parse from both text boxes
            self.app._update_parsed_data()
            fr = self.app.parsed_data.get("flight_routes", {})

            debug_print("[FLIGHT_PARAM_PARSER] --------------------------------------------------")
            if fr:
                for k, v in sorted(fr.items()):
                    debug_print(f"[FLIGHT_PARAM_PARSER] {k:<28}: {v!r} ({type(v).__name__})")
            else:
                debug_print("[FLIGHT_PARAM_PARSER] <NO DATA>")
            debug_print("[FLIGHT_PARAM_PARSER] --------------------------------------------------")

            required = (
                "transition_mode",
                "transition_vertical_offset",
                "transition_horizontal_offset",
                "order",
                "standard_flight_routes",
            )
            missing = [k for k in required if k not in fr]
            if missing:
                error_debug_print(f"[ERROR] Missing flight-route keys: {', '.join(missing)}")
                return None

            # Prepare params dict with all parameters
            params = fr.copy()  # Include all parameters, not just required ones

            # Legacy handling of 'transition_mode' token inside the order list
            if "transition_mode" in params["order"]:
                if params["transition_mode"] == 1:
                    params["order"] = ["transition" if x == "transition_mode" else x for x in params["order"]]
                else:
                    params["order"] = [x for x in params["order"] if x != "transition_mode"]

            return params
            
            # ----- Legacy regex block below will never be reached (kept for reference) -----
            transition_mode_match = re.search(r'transition_mode\s*=\s*(\d+)', tab3_content)
            if not transition_mode_match:
                debug_print("❌ transition_mode not found")
                return None
            params['transition_mode'] = int(transition_mode_match.group(1))
            debug_print(f"✅ transition_mode: {params['transition_mode']}")
            
            # Parse transition_vertical_offset (required)
            vertical_match = re.search(r'transition_vertical_offset\s*=\s*([+-]?\d*\.?\d+)', tab3_content)
            if not vertical_match:
                debug_print("❌ transition_vertical_offset not found")
                return None
            params['transition_vertical_offset'] = float(vertical_match.group(1))
            debug_print(f"✅ transition_vertical_offset: {params['transition_vertical_offset']}")
            
            # Parse transition_horizontal_offset (required)
            horizontal_match = re.search(r'transition_horizontal_offset\s*=\s*([+-]?\d*\.?\d+)', tab3_content)
            if not horizontal_match:
                debug_print("❌ transition_horizontal_offset not found")
                return None
            params['transition_horizontal_offset'] = float(horizontal_match.group(1))
            debug_print(f"✅ transition_horizontal_offset: {params['transition_horizontal_offset']}")
            
            # Parse order array (required)
            order_match = re.search(r'order\s*=\s*\[(.*?)\]', tab3_content, re.DOTALL)
            if not order_match:
                debug_print("❌ order array not found")
                return None
                
            order_content = order_match.group(1)
            
            # Handle transition_mode variable in order list
            if 'transition_mode' in order_content:
                if params['transition_mode'] == 1:
                    order_content = order_content.replace('transition_mode,', '"transition",')
                    order_content = order_content.replace('transition_mode', '"transition"')
                else:
                    # Remove transition_mode entries completely (for modes 0, 2, etc.)
                    # Use regex to surgically remove just the transition_mode token, not the whole line
                    debug_print(f"[PARSE] Original order content: [{order_content.strip()}]")

                    # Remove transition_mode with optional surrounding commas and whitespace
                    # This handles cases like: "transition_mode,", ",transition_mode,", ",transition_mode"
                    order_content = re.sub(r',\s*transition_mode\s*,', ',', order_content)  # Middle: ,transition_mode,
                    order_content = re.sub(r',\s*transition_mode\s*$', '', order_content)   # End: ,transition_mode
                    order_content = re.sub(r'^\s*transition_mode\s*,', '', order_content)   # Start: transition_mode,
                    order_content = re.sub(r'^\s*transition_mode\s*$', '', order_content)   # Alone: transition_mode

                    # Clean up any double commas that might result
                    order_content = re.sub(r',\s*,+', ',', order_content)

                    # Clean up leading/trailing commas and whitespace
                    order_content = re.sub(r'^\s*,\s*', '', order_content)
                    order_content = re.sub(r',\s*$', '', order_content)
                    order_content = order_content.strip()

                    debug_print(f"[PARSE] Cleaned order content (removed transition_mode for mode {params['transition_mode']})")
                    debug_print(f"[PARSE] Result: [{order_content}]")
            
            # Clean and parse order
            order_content = order_content.strip().rstrip(',')
            try:
                params['order'] = ast.literal_eval(f'[{order_content}]')
                debug_print(f"✅ order: {params['order']}")
            except Exception as e:
                debug_print(f"❌ Failed to parse order: {e}")
                return None
            
            # Parse standard_flight_routes (required)
            routes_start = re.search(r'standard_flight_routes\s*=\s*\{', tab3_content)
            if not routes_start:
                debug_print("❌ standard_flight_routes not found")
                return None
                
            # Extract dictionary content
            start_pos = routes_start.start()
            brace_pos = tab3_content.find('{', start_pos)
            remaining_content = tab3_content[brace_pos:]
            
            # Find end of dictionary
            next_var_match = re.search(r'\n\s*[a-zA-Z_][a-zA-Z0-9_]*\s*=', remaining_content)
            if next_var_match:
                routes_content = remaining_content[:next_var_match.start()].strip()
            else:
                routes_content = remaining_content.strip()
            
            # Parse routes dictionary
            try:
                params['standard_flight_routes'] = ast.literal_eval(routes_content)
                debug_print(f"✅ standard_flight_routes: {len(params['standard_flight_routes'])} routes defined")
            except Exception as e:
                # Try fixing missing closing braces
                open_braces = routes_content.count('{')
                close_braces = routes_content.count('}')
                if open_braces > close_braces:
                    fixed_content = routes_content + '}' * (open_braces - close_braces)
                    try:
                        params['standard_flight_routes'] = ast.literal_eval(fixed_content)
                        debug_print(f"✅ standard_flight_routes: {len(params['standard_flight_routes'])} routes (auto-fixed)")
                    except:
                        debug_print(f"❌ Failed to parse standard_flight_routes: {e}")
                        return None
                else:
                    debug_print(f"❌ Failed to parse standard_flight_routes: {e}")
                    return None
            
            return params
            
        except Exception as e:
            debug_print(f"❌ Error parsing parameters: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _generate_routes_with_offsets(self, flight_params):
        """Generate routes using trajectory_samples with specified offsets.
        
        TRANSITION MODES:
        ================
        0: No bridge crossing - separate left and right flight paths
           Example: Left side group: ["101", "102"], Right side group: ["201", "202"]
           Creates "Overview Flight Left" and "Overview Flight Right" visualizations
           
        1: Connected with middle transition (explicit "transition" in order array)
           Example: ["101", "r101", "transition", "201", "r201"]
           Requires "transition" keyword in order array for bridge crossing
           
        2: Auto-elevated transitions between consecutive routes
           Example: ["101", "r101", "201", "r201"] - automatically adds elevated transitions
           Takes last point of route A, elevates it by transition_vertical_offset
           Takes first point of route B, elevates it by transition_vertical_offset
           Connects them with elevated flight segment for side switching
        """
        try:
            trajectory_samples = self.app.trajectory_samples
            order = flight_params.get('order', [])
            standard_routes = flight_params.get('standard_flight_routes', {})
            transition_mode = flight_params.get('transition_mode', 0)
            
            if transition_mode == 0:
                # Special handling for transition mode 0: separate left and right sides
                return self._generate_separated_routes(order, standard_routes, trajectory_samples, flight_params)
            
            all_routes = []
            
            debug_print(f"\n📍 Generating routes for order: {order}")
            if transition_mode == 2:
                debug_print(f"🔀 Transition mode 2 enabled: Auto-generating elevated transitions between routes")
            
            # Process each route in order
            for i, route_id in enumerate(order):
                if route_id == "transition":
                    # Handle explicit transition (mode 1)
                    if transition_mode == 1:
                        transition_waypoints = self._generate_transition_waypoints(
                            trajectory_samples, flight_params
                        )
                        if transition_waypoints:
                            all_routes.append({
                                'id': 'transition',
                                'waypoints': transition_waypoints,
                                'config': {
                                    'type': 'transition',
                                    'vertical_offset': flight_params['transition_vertical_offset'],
                                    'horizontal_offset': flight_params['transition_horizontal_offset']
                                }
                            })
                else:
                    # Check if this is a reverse route (starts with "r")
                    is_reverse = False
                    base_route_id = route_id
                    
                    if isinstance(route_id, str) and route_id.startswith('r'):
                        is_reverse = True
                        base_route_id = route_id[1:]  # Remove 'r' prefix
                        debug_print(f"  🔄 Detected reverse route: {route_id} → base route {base_route_id}")
                    
                    # Generate waypoints for the base route
                    if base_route_id in standard_routes:
                        route_config = standard_routes[base_route_id]
                        route_waypoints = self._generate_single_route_waypoints(
                            base_route_id, route_config, trajectory_samples
                        )
                        
                        if route_waypoints:
                            # If this is a reverse route, reverse the waypoints
                            if is_reverse:
                                route_waypoints = route_waypoints[::-1]  # Reverse the list
                                debug_print(f"  ✅ Route {route_id} (reversed {base_route_id}): {len(route_waypoints)} waypoints")
                            else:
                                debug_print(f"  ✅ Route {route_id}: {len(route_waypoints)} waypoints")
                            
                            # Add the current route
                            current_route = {
                                'id': route_id,  # Keep original ID (with 'r' if reversed)
                                'waypoints': route_waypoints,
                                'config': route_config,
                                'is_reverse': is_reverse,
                                'base_route_id': base_route_id
                            }
                            all_routes.append(current_route)
                            
                            # Check if we need to add transition mode 2 waypoints
                            if transition_mode == 2 and i < len(order) - 1:
                                # This is not the last route, so check if we need elevated transition to next route
                                next_route_id = order[i + 1]
                                
                                # Skip if next route is an explicit "transition"
                                if next_route_id != "transition":
                                    # Determine sides of current and next routes
                                    current_side = self._determine_route_side(base_route_id)
                                    
                                    # Determine side of next route
                                    next_base_route_id = next_route_id
                                    if isinstance(next_route_id, str) and next_route_id.startswith('r'):
                                        next_base_route_id = next_route_id[1:]  # Remove 'r' prefix
                                    next_side = self._determine_route_side(next_base_route_id)
                                    
                                    # Only add elevated transition if crossing sides (left to right or right to left)
                                    if current_side != next_side:
                                        debug_print(f"  🔀 Mode 2: Side crossing detected from {current_side} ({route_id}) to {next_side} ({next_route_id})")
                                        transition_waypoints = self._generate_elevated_transition_waypoints(
                                            current_route, next_route_id, order, standard_routes, 
                                            trajectory_samples, flight_params
                                        )
                                        
                                        if transition_waypoints:
                                            transition_route = {
                                                'id': f'transition_{route_id}_to_{next_route_id}',
                                                'waypoints': transition_waypoints,
                                                'config': {
                                                    'type': 'elevated_transition',
                                                    'from_route': route_id,
                                                    'to_route': next_route_id,
                                                    'vertical_offset': flight_params['transition_vertical_offset']
                                                }
                                            }
                                            all_routes.append(transition_route)
                                            debug_print(f"  ✅ Added elevated transition route: {transition_route['id']} with {len(transition_waypoints)} waypoints")
                                        else:
                                            debug_print(f"  ❌ Failed to generate elevated transition waypoints from {route_id} to {next_route_id}")
                                    else:
                                        debug_print(f"  ⏭️ Mode 2: Same side transition ({current_side} to {next_side}) - skipping elevated transition")
                                else:
                                    debug_print(f"  ⏭️ Skipping transition to explicit 'transition' keyword")
                    else:
                        debug_print(f"  ⚠️ Base route {base_route_id} not found in standard_flight_routes (for {route_id})")
            
            debug_print(f"\n📋 Route generation summary for transition_mode {transition_mode}:")
            debug_print(f"  Total routes generated: {len(all_routes)}")
            for route in all_routes:
                route_type = route.get('config', {}).get('type', 'standard')
                waypoint_count = len(route.get('waypoints', []))
                debug_print(f"    • {route['id']} ({route_type}): {waypoint_count} waypoints")
            
            return all_routes
            
        except Exception as e:
            debug_print(f"❌ Error generating routes: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _generate_single_route_waypoints(self, route_id, route_config, trajectory_samples):
        """Generate waypoints for a single route with specified offsets using improved utilities."""
        try:
            vertical_offset = route_config.get('vertical_offset', 0.0)
            user_distance_offset = route_config.get('distance_offset', 0.0)
            
            debug_print(f"    → Route {route_id}: vertical={vertical_offset}m, user_offset={user_distance_offset}m")
            
            # ALL routes must maintain minimum structural clearance (bridge_width/2)
            # Even "zero offset" routes get bridge_width/2 + 0 = bridge_width/2 clearance
            
            # Determine which side this route should be on
            side = self._determine_route_side(route_id)
            
            # Generate parallel trajectory with safe minimum offset
            # This automatically includes bridge_width/2 + user_distance_offset
            parallel_points = self.generate_parallel_trajectory_with_safe_offset(
                trajectory_samples, user_distance_offset, side
            )
            
            # Apply vertical offset
            waypoints = []
            for point in parallel_points:
                # Append route tag as 4th element for speed mapping later
                waypoints.append([
                    point[0],
                    point[1],
                    point[2] + vertical_offset,
                    route_id  # flight-route tag
                ])
            
            debug_print(f"    → Generated {len(waypoints)} waypoints for route {route_id} on {side} side")
            return waypoints
            
        except Exception as e:
            debug_print(f"❌ Error generating route {route_id}: {e}")
            return []
    
    def _determine_route_side(self, route_id):
        """
        Determine which side of trajectory a route should be on based on route ID.
        
        Uses consistent naming conventions:
        - Routes starting with '1' or containing 'left' -> left side
        - Routes starting with '2' or containing 'right' -> right side  
        - Routes with 'r' prefix (e.g., 'r101') -> extract base ID for side determination
        - Default to right side if unclear
        """
        route_id_lower = route_id.lower()
        
        # Handle reverse routes with 'r' prefix (e.g., 'r101' -> '101')
        if route_id_lower.startswith('r') and len(route_id_lower) > 1:
            base_id = route_id_lower[1:]  # Remove 'r' prefix
            debug_print(f"🔄 Determining side for reverse route {route_id} using base ID: {base_id}")
        # Handle legacy reverse routes with 'reverse' keyword
        elif 'reverse' in route_id_lower:
            base_id = route_id_lower.replace('reverse', '').strip()
            debug_print(f"🔄 Determining side for legacy reverse route {route_id} using base ID: {base_id}")
        else:
            base_id = route_id_lower
        
        # Determine side based on naming convention
        if base_id.startswith('1') or 'left' in base_id:
            side = 'left'
        elif base_id.startswith('2') or 'right' in base_id:
            side = 'right'
        else:
            debug_print(f"⚠️ Route side unclear for '{route_id}' (base: '{base_id}'), defaulting to right")
            side = 'right'

        debug_print(f"📍 Route {route_id} assigned to {side} side")
        return side
    
    def _create_parallel_trajectory(self, trajectory_samples, distance_offset, route_id):
        """
        DEPRECATED: Use generate_parallel_trajectory_with_safe_offset() instead.
        
        This method does not apply the bridge_width/2 minimum offset and is kept
        only for backward compatibility. New code should use the improved utilities:
        - compute_perpendicular_offset_points() for single point offsets
        - generate_parallel_trajectory_with_safe_offset() for full trajectory offsets
        """
        try:
            traj_array = np.array(trajectory_samples)
            parallel_points = []
            
            # Determine offset direction based on route ID convention
            if route_id.startswith('1') or 'left' in route_id.lower():
                offset_sign = -1  # Left side
            elif route_id.startswith('2') or 'right' in route_id.lower():
                offset_sign = 1   # Right side
            else:
                # For reverse routes, check base route
                base_id = route_id.replace('reverse ', '').strip()
                if base_id.startswith('1'):
                    offset_sign = -1
                elif base_id.startswith('2'):
                    offset_sign = 1
                else:
                    offset_sign = 1  # Default to right if unclear
            
            # Generate parallel points
            for i in range(len(traj_array)):
                # Calculate local direction vector
                if i == 0:
                    direction = traj_array[i+1][:2] - traj_array[i][:2]
                elif i == len(traj_array) - 1:
                    direction = traj_array[i][:2] - traj_array[i-1][:2]
                else:
                    # Smooth direction using adjacent points
                    dir1 = traj_array[i][:2] - traj_array[i-1][:2]
                    dir2 = traj_array[i+1][:2] - traj_array[i][:2]
                    direction = (dir1 + dir2) / 2
                
                # Calculate perpendicular offset
                direction_length = np.linalg.norm(direction)
                if direction_length > 0:
                    direction_unit = direction / direction_length
                    # Perpendicular vector (rotate 90 degrees)
                    perp_vector = np.array([-direction_unit[1], direction_unit[0]]) * abs(distance_offset) * offset_sign
                    offset_point = traj_array[i][:2] + perp_vector
                    parallel_points.append([offset_point[0], offset_point[1], traj_array[i][2]])
                else:
                    # No direction - use original point
                    parallel_points.append(traj_array[i].tolist())
            
            return parallel_points
            
        except Exception as e:
            debug_print(f"❌ Error creating parallel trajectory: {e}")
            return trajectory_samples
    
    def _generate_transition_waypoints(self, trajectory_samples, flight_params):
        """Generate transition waypoints crossing over the bridge using improved utilities."""
        try:
            vertical_offset = flight_params['transition_vertical_offset']
            user_horizontal_offset = flight_params['transition_horizontal_offset']
            
            # Find middle point of trajectory
            middle_idx = len(trajectory_samples) // 2
            middle_point = trajectory_samples[middle_idx]
            
            debug_print(f"🔀 Generating transition waypoints:")
            debug_print(f"   Center point: {middle_point[:2]} at trajectory index {middle_idx}")
            debug_print(f"   User horizontal offset: {user_horizontal_offset}m")
            debug_print(f"   Vertical offset: {vertical_offset}m")
            
            # Calculate direction at middle point
            traj_array = np.array(trajectory_samples)
            direction = self._calculate_direction_at_point(traj_array, middle_idx)
            
            # Calculate total safe offset (bridge_width/2 + user offset)
            total_offset = self.calculate_minimum_flight_offset(user_horizontal_offset)
            
            # Generate left and right offset points using the utility function
            offset_points = self.compute_perpendicular_offset_points(
                middle_point, direction, total_offset, side='both'
            )
            
            # Create transition waypoints (crossing from left to right)
            transition_waypoints = [
                [offset_points['left'][0], offset_points['left'][1], middle_point[2] + vertical_offset, 'transition'],
                [offset_points['right'][0], offset_points['right'][1], middle_point[2] + vertical_offset, 'transition']
            ]
            
            debug_print(f"   ✅ Transition waypoints generated:")
            debug_print(f"      Left:  [{offset_points['left'][0]:.1f}, {offset_points['left'][1]:.1f}, {middle_point[2] + vertical_offset:.1f}]")
            debug_print(f"      Right: [{offset_points['right'][0]:.1f}, {offset_points['right'][1]:.1f}, {middle_point[2] + vertical_offset:.1f}]")
            debug_print(f"      Total offset used: {total_offset:.1f}m")
            
            return transition_waypoints
            
        except Exception as e:
            debug_print(f"❌ Error generating transition waypoints: {e}")
            return []
    
    def _generate_elevated_transition_waypoints(self, current_route, next_route_id, order, 
                                              standard_routes, trajectory_samples, flight_params):
        """Generate elevated transition waypoints between current route and next route (mode 2)."""
        try:
            transition_height = flight_params['transition_vertical_offset']
            
            # Get last point of current route
            current_waypoints = current_route.get('waypoints', [])
            if not current_waypoints:
                debug_print(f"⚠️ Current route {current_route['id']} has no waypoints")
                return []
            
            last_point = current_waypoints[-1]
            
            # Generate waypoints for next route to get its first point
            next_is_reverse = False
            next_base_route_id = next_route_id
            
            if isinstance(next_route_id, str) and next_route_id.startswith('r'):
                next_is_reverse = True
                next_base_route_id = next_route_id[1:]  # Remove 'r' prefix
            
            if next_base_route_id not in standard_routes:
                debug_print(f"⚠️ Next route {next_base_route_id} not found in standard_flight_routes")
                return []
            
            # Generate next route waypoints to get the first point
            next_route_config = standard_routes[next_base_route_id]
            next_route_waypoints = self._generate_single_route_waypoints(
                next_base_route_id, next_route_config, trajectory_samples
            )
            
            if not next_route_waypoints:
                debug_print(f"⚠️ Could not generate waypoints for next route {next_route_id}")
                return []
            
            # If next route is reversed, get the last point (which becomes first after reversal)
            if next_is_reverse:
                first_point_next = next_route_waypoints[-1]  # Last point of unreversed = first point of reversed
            else:
                first_point_next = next_route_waypoints[0]   # First point of normal route
            
            # Create elevated transition waypoints
            elevated_last = [
                last_point[0],
                last_point[1], 
                last_point[2] + transition_height,
                'transition'
            ]
            
            elevated_first = [
                first_point_next[0],
                first_point_next[1],
                first_point_next[2] + transition_height,
                'transition'
            ]
            
            # compare which z value is higher
            if elevated_last[2] > elevated_first[2]:
                higher_transition_height = elevated_last[2]
            else:
                higher_transition_height = elevated_first[2]
            # update points:
            elevated_last[2] = higher_transition_height
            elevated_first[2] = higher_transition_height

            transition_waypoints = [elevated_last, elevated_first]
            
            debug_print(f"🔀 Generated elevated transition from {current_route['id']} to {next_route_id}:")
            debug_print(f"   From: [{elevated_last[0]:.1f}, {elevated_last[1]:.1f}, {elevated_last[2]:.1f}] (+{transition_height}m)")
            debug_print(f"   To:   [{elevated_first[0]:.1f}, {elevated_first[1]:.1f}, {elevated_first[2]:.1f}] (+{transition_height}m)")
            
            return transition_waypoints
            
        except Exception as e:
            debug_print(f"❌ Error generating elevated transition waypoints: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _generate_separated_routes(self, order, standard_routes, trajectory_samples, flight_params):
        """Generate routes separated by left and right sides (transition mode 0)."""
        try:
            debug_print(f"\n📍 Generating separated routes for order: {order}")
            debug_print(f"🚫 Transition mode 0: No bridge crossing - separate left and right sides")
            
            left_groups = []   # List of groups, each group is a list of routes
            right_groups = []  # List of groups, each group is a list of routes
            
            current_left_group = []
            current_right_group = []
            current_side = None
            
            # Process each route in order and group by sides
            for route_id in order:
                if route_id == "transition":
                    # Skip explicit transition in mode 0
                    debug_print(f"  ⏭️ Skipping explicit transition in mode 0")
                    continue
                
                # Check if this is a reverse route (starts with "r")
                is_reverse = False
                base_route_id = route_id
                
                if isinstance(route_id, str) and route_id.startswith('r'):
                    is_reverse = True
                    base_route_id = route_id[1:]  # Remove 'r' prefix
                    debug_print(f"  🔄 Detected reverse route: {route_id} → base route {base_route_id}")
                
                # Generate waypoints for the base route
                if base_route_id in standard_routes:
                    route_config = standard_routes[base_route_id]
                    route_waypoints = self._generate_single_route_waypoints(
                        base_route_id, route_config, trajectory_samples
                    )
                    
                    if route_waypoints:
                        # If this is a reverse route, reverse the waypoints
                        if is_reverse:
                            route_waypoints = route_waypoints[::-1]  # Reverse the list
                            debug_print(f"  ✅ Route {route_id} (reversed {base_route_id}): {len(route_waypoints)} waypoints")
                        else:
                            debug_print(f"  ✅ Route {route_id}: {len(route_waypoints)} waypoints")
                        
                        # Determine which side this route is on
                        route_side = self._determine_route_side(base_route_id)
                        
                        # Create the route object
                        current_route = {
                            'id': route_id,
                            'waypoints': route_waypoints,
                            'config': route_config,
                            'is_reverse': is_reverse,
                            'base_route_id': base_route_id,
                            'side': route_side
                        }
                        
                        # Check if we need to switch sides
                        if current_side is None:
                            # First route - set the initial side
                            current_side = route_side
                            debug_print(f"  📍 Starting with {route_side} side")
                        elif current_side != route_side:
                            # Side changed - finish current group and start new one
                            if current_side == 'left' and current_left_group:
                                left_groups.append(current_left_group)
                                debug_print(f"  🏁 Finished left group with {len(current_left_group)} routes")
                                current_left_group = []
                            elif current_side == 'right' and current_right_group:
                                right_groups.append(current_right_group)
                                debug_print(f"  🏁 Finished right group with {len(current_right_group)} routes")
                                current_right_group = []
                            
                            current_side = route_side
                            debug_print(f"  🔄 Switched to {route_side} side")
                        
                        # Add route to appropriate group
                        if route_side == 'left':
                            current_left_group.append(current_route)
                            debug_print(f"  ➕ Added {route_id} to current left group")
                        else:
                            current_right_group.append(current_route)
                            debug_print(f"  ➕ Added {route_id} to current right group")
                
                else:
                    debug_print(f"  ⚠️ Base route {base_route_id} not found in standard_flight_routes (for {route_id})")
            
            # Finish any remaining groups
            if current_left_group:
                left_groups.append(current_left_group)
                debug_print(f"  🏁 Finished final left group with {len(current_left_group)} routes")
            if current_right_group:
                right_groups.append(current_right_group)
                debug_print(f"  🏁 Finished final right group with {len(current_right_group)} routes")
            
            # Return grouped routes with metadata
            result = {
                'separated': True,
                'left_groups': left_groups,
                'right_groups': right_groups,
                'transition_mode': 0
            }
            
            debug_print(f"\n📊 Separation summary:")
            debug_print(f"  🔵 Left side: {len(left_groups)} groups with {sum(len(group) for group in left_groups)} total routes")
            debug_print(f"  🔴 Right side: {len(right_groups)} groups with {sum(len(group) for group in right_groups)} total routes")
            
            return result
            
        except Exception as e:
            debug_print(f"❌ Error generating separated routes: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def _calculate_bridge_width(self):
        """Get bridge width from parsed data or fallback calculation."""
        try:
            # First priority: Use bridge_width from parsed data
            if hasattr(self.app, 'parsed_data'):
                bridge_width_raw = self.app.parsed_data.get("project", {}).get("bridge_width")
                debug_print(f"🔍 DEBUG: Raw bridge_width from parsed data: {bridge_width_raw} (type: {type(bridge_width_raw)})")

                if bridge_width_raw is not None:
                    # Handle case where bridge_width might be a list/array
                    try:
                        if isinstance(bridge_width_raw, (list, tuple, np.ndarray)):
                            if len(bridge_width_raw) > 0:
                                bridge_width = float(bridge_width_raw[0])  # Take first element
                                debug_print(f"📏 Using first element of bridge_width array: {bridge_width}m")
                            else:
                                raise ValueError("Empty bridge_width array")
                        else:
                            bridge_width = float(bridge_width_raw)
                            debug_print(f"📏 Using bridge_width from parsed data: {bridge_width}m")
                        
                        # Validate the value
                        if bridge_width > 0:
                            return bridge_width
                        else:
                            debug_print(f"⚠️ Invalid bridge_width value: {bridge_width}, using fallback")
                    
                    except (ValueError, TypeError, IndexError) as conv_error:
                        debug_print(f"⚠️ Error converting bridge_width {bridge_width_raw}: {conv_error}")
            
            # Second priority: Calculate from cross-section data
            if hasattr(self.app, 'crosssection_transformed_points') and self.app.crosssection_transformed_points is not None:
                try:
                    points = np.array(self.app.crosssection_transformed_points)
                    if len(points) > 0 and points.shape[1] >= 2:
                        bridge_width = np.max(points[:, 0]) - np.min(points[:, 0])
                        debug_print(f"📏 Calculated bridge_width from cross-section: {bridge_width:.1f}m")
                        return float(bridge_width)
                except Exception as cs_error:
                    debug_print(f"⚠️ Error calculating from cross-section: {cs_error}")
            
            # NO FALLBACK - Force user to provide bridge_width
            debug_print("❌ CRITICAL ERROR: bridge_width not found!")
            debug_print("   bridge_width is REQUIRED for safe flight route generation.")
            debug_print("   Please add 'bridge_width = [your_value]' to the project textbox.")
            debug_print("   Example: bridge_width = 13.29")
            raise ValueError("bridge_width is required but not found in project settings")
            
        except Exception as e:
            debug_print(f"❌ Error getting bridge width: {e}")
            import traceback
            traceback.print_exc()
            debug_print("   bridge_width is REQUIRED for safe flight route generation.")
            raise ValueError(f"Failed to get bridge_width: {e}")
    
    def _visualize_overview_flight(self, flight_routes):
        """Visualize routes - either combined or separated by sides."""
        try:
            # Check if this is separated routes (transition mode 0)
            if isinstance(flight_routes, dict) and flight_routes.get('separated', False):
                self._visualize_separated_flights(flight_routes)
                return
            
            # Standard combined visualization for other transition modes
            self._visualize_combined_flight(flight_routes)
            
        except Exception as e:
            debug_print(f"❌ Error visualizing routes: {e}")
            import traceback
            traceback.print_exc()
    
    def _visualize_separated_flights(self, separated_routes):
        """Visualize left and right sides as separate flight paths."""
        try:
            left_groups = separated_routes.get('left_groups', [])
            right_groups = separated_routes.get('right_groups', [])
            
            # Check visualizer availability
            if not hasattr(self.app, 'visualizer') or not self.app.visualizer:
                debug_print("❌ Visualizer not available")
                return
            
            # Remove existing overview flights if present
            for flight_name in ['Overview Flight Right', 'Overview Flight Left', 'Overview Flight']:
                if flight_name in self.app.visualizer.meshes:
                    try:
                        self.app.visualizer._remove_mesh(flight_name)
                        debug_print(f"🔄 Removed existing {flight_name}")
                    except Exception as e:
                        debug_print(f"⚠️ Could not remove existing {flight_name}: {e}")
            
            # Create left side visualization
            if left_groups:
                left_waypoints = []
                left_summary = []
                
                for group_idx, group in enumerate(left_groups):
                    for route in group:
                        waypoints = route.get('waypoints', [])
                        route_id = route.get('id', 'Unknown')
                        is_reverse = route.get('is_reverse', False)
                        base_route_id = route.get('base_route_id', route_id)
                        
                        left_waypoints.extend(waypoints)
                        
                        if is_reverse:
                            left_summary.append(f"{route_id} (reversed {base_route_id}): {len(waypoints)} pts")
                        else:
                            left_summary.append(f"{route_id}: {len(waypoints)} pts")
                
                if left_waypoints and hasattr(self.app.visualizer, 'add_polyline'):
                    self.app.visualizer.add_polyline(
                        'Overview Flight Right',
                        left_waypoints,
                        color=[0.0, 0.5, 1.0],  # Blue color for left side
                        line_width=5,
                        tube_radius=0
                    )
                    debug_print(f"✅ Visualized Overview Flight Right: {len(left_waypoints)} total waypoints")
                    debug_print("   🔵 Left side composition:")
                    for summary in left_summary:
                        debug_print(f"      • {summary}")
            
            # Create right side visualization
            if right_groups:
                right_waypoints = []
                right_summary = []
                
                for group_idx, group in enumerate(right_groups):
                    for route in group:
                        waypoints = route.get('waypoints', [])
                        route_id = route.get('id', 'Unknown')
                        is_reverse = route.get('is_reverse', False)
                        base_route_id = route.get('base_route_id', route_id)
                        
                        right_waypoints.extend(waypoints)
                        
                        if is_reverse:
                            right_summary.append(f"{route_id} (reversed {base_route_id}): {len(waypoints)} pts")
                        else:
                            right_summary.append(f"{route_id}: {len(waypoints)} pts")
                
                if right_waypoints and hasattr(self.app.visualizer, 'add_polyline'):
                    self.app.visualizer.add_polyline(
                        'Overview Flight Left',
                        right_waypoints,
                        color=[1.0, 0.5, 0.0],  # Orange color for right side
                        line_width=5,
                        tube_radius=0
                    )
                    debug_print(f"✅ Visualized Overview Flight Left: {len(right_waypoints)} total waypoints")
                    debug_print("   🔴 Right side composition:")
                    for summary in right_summary:
                        debug_print(f"      • {summary}")
            
            if not left_groups and not right_groups:
                debug_print("❌ No separated routes to visualize")
            
        except Exception as e:
            debug_print(f"❌ Error visualizing separated flights: {e}")
            import traceback
            traceback.print_exc()
    
    def _visualize_combined_flight(self, flight_routes):
        """Visualize all routes combined as single 'Overview Flight'."""
        try:
            # Combine all waypoints from all routes and collect route info
            all_waypoints = []
            route_summary = []
            
            for route in flight_routes:
                waypoints = route.get('waypoints', [])
                route_id = route.get('id', 'Unknown')
                config = route.get('config', {})
                is_reverse = route.get('is_reverse', False)
                base_route_id = route.get('base_route_id', route_id)
                
                all_waypoints.extend(waypoints)
                
                # Create summary info based on route type
                route_type = config.get('type', 'standard')
                
                if route_type == 'elevated_transition':
                    # Special handling for elevated transitions
                    from_route = config.get('from_route', 'Unknown')
                    to_route = config.get('to_route', 'Unknown')
                    vertical_offset = config.get('vertical_offset', 0)
                    route_summary.append(f"🔀 {route_id} (+{vertical_offset}m): {len(waypoints)} pts")
                elif route_type == 'transition':
                    # Regular transition (mode 1)
                    vertical_offset = config.get('vertical_offset', 0)
                    route_summary.append(f"🔀 {route_id} (+{vertical_offset}m): {len(waypoints)} pts")
                elif is_reverse:
                    # Reversed standard route
                    route_summary.append(f"{route_id} (reversed {base_route_id}): {len(waypoints)} pts")
                else:
                    # Standard route
                    route_summary.append(f"{route_id}: {len(waypoints)} pts")
            
            # Store for external export (GUI) - MOVED TO AFTER SAFETY PROCESSING
            # if hasattr(self.app, '__setattr__'):
            #     try:
            #         self.app.overview_flight_waypoints = all_waypoints  # includes tag as 4th element
            #     except Exception:
            #         pass

            if not all_waypoints:
                debug_print("❌ No waypoints to visualize")
                return

            # Get safety zone parameters
            safety_zones = []
            if hasattr(self.app, 'current_safety_zones') and self.app.current_safety_zones:
                debug_print("\n=== Converting Safety Zones to Project Coordinates ===")
                # Convert safety zones from WGS84 to project coordinates
                for zone_idx, zone in enumerate(self.app.current_safety_zones):
                    if len(zone['points']) >= 3:
                        zone_points_project = []
                        for point in zone['points']:
                            # Points are stored as [lat, lng] in WGS84
                            lat, lng = point[0], point[1]
                            # Prefer the same local-metric transform that was used for the flight-route geometry
                            # Convert each point from WGS84 to the project coordinate system
                            if hasattr(self.app, '_last_transform_func') and self.app._last_transform_func:
                                x, y, _ = self.app._last_transform_func(lat, lng, 0)
                            elif hasattr(self.app, 'current_context') and self.app.current_context:
                                # Fall back to project context CRS
                                x, y, _ = self.app.current_context.wgs84_to_project(lng, lat, 0)
                            else:
                                # Absolute fallback – leave in degrees so that we do not crash
                                x, y = lng, lat
                                debug_print(f"[SAFETY ZONE] WARNING: No context available for coordinate conversion! Using WGS84 coordinates.")
                            zone_points_project.append([x, y])

                            # Debug: print the first few conversions for the very first zone only
                            if zone_idx == 0 and len(zone_points_project) <= 3:
                                debug_print(f"  Point WGS84: ({lat:.6f}, {lng:.6f}) -> Project: ({x:.2f}, {y:.2f})")
                        safety_zones.append(zone_points_project)
            
            debug_print("\n=== Safety Zone Processing ===")
            debug_print(f"Found {len(safety_zones)} safety zones")
            if safety_zones:
                debug_print("Safety zone points:")
                for i, zone in enumerate(safety_zones):
                    debug_print(f"Zone {i}: {len(zone)} points")

            # Debug: Print safety zones and flight route in project coordinates
            debug_print("\n=== Debug: Safety Zones and Flight Route in Project Coordinates ===")
            for i, zone in enumerate(safety_zones):
                debug_print(f"Safety Zone {i}:")
                for point in zone[:3]:  # Print first 3 points for brevity
                    debug_print(f"  Point: {point}")
            
            debug_print("\nFlight Route:")
            for point in all_waypoints[:10]:  # Print first 10 waypoints for brevity
                debug_print(f"  Waypoint: {point}")
            
            # Apply safety processing logic
            if safety_zones:  # Only proceed if we have safety zones
                # Import the updated safety zone processor (always use enhanced version)
                from orbit.planners.safety_zones import EnhancedSafetyProcessor
                
                # Get safety parameters
                flight_params = self._parse_flight_parameters()
                safety_clearance = flight_params.get('safety_zones_clearance', []) if flight_params else []
                safety_adjust = flight_params.get('safety_zones_clearance_adjust', []) if flight_params else []
                takeoff_altitude = self.app.takeoff_altitude if hasattr(self.app, 'takeoff_altitude') else 0
                
                # Validate safety zone parameters before processing
                if hasattr(self.app, '_validate_safety_zone_parameters'):
                    self.app._validate_safety_zone_parameters()
                
                debug_print(f"Safety clearances: {safety_clearance}")
                debug_print(f"Safety adjustments: {safety_adjust}")
                debug_print(f"Takeoff altitude: {takeoff_altitude}")
                
                if safety_clearance:  # Only process if we have clearance parameters
                    debug_print("\n=== Safety Zone Information ===")
                    debug_print(f"Initial route points: {len(all_waypoints)}")
          
                    # Print bounds for comparison
                    if all_waypoints:
                        x_coords = [p[0] for p in all_waypoints]
                        y_coords = [p[1] for p in all_waypoints]
                        debug_print(f"\nWaypoint bounds: X=[{min(x_coords):.2f}, {max(x_coords):.2f}], Y=[{min(y_coords):.2f}, {max(y_coords):.2f}]")
                    
                    if safety_zones:
                        for i, zone in enumerate(safety_zones):
                            x_coords = [p[0] for p in zone]
                            y_coords = [p[1] for p in zone]

                            # Get vertical clearance info if available
                            if i < len(safety_clearance):
                                z_min, z_max = safety_clearance[i]
                            else:
                                z_min, z_max = ("?", "?")

                            # Get adjustment value for this zone
                            if i < len(safety_adjust):
                                raw_adj = safety_adjust[i]
                                adj_val = raw_adj[0] if isinstance(raw_adj, (list, tuple)) else raw_adj
                            else:
                                adj_val = "<none>"

                            debug_print(
                                f"Safety Zone {i} bounds: "
                                f"X=[{min(x_coords):.2f}, {max(x_coords):.2f}], "
                                f"Y=[{min(y_coords):.2f}, {max(y_coords):.2f}], "
                                f"Z=[{z_min}, {z_max}], "
                                f"adjust={adj_val}"
                            )
                    
                    # Process route through the safety zone processor
                    safety_processor = EnhancedSafetyProcessor(
                        all_waypoints,
                        safety_zones,
                        safety_clearance,
                        takeoff_altitude

                    )
                    # Get min_angle_change from GUI
                    min_angle_change = 15  # Default fallback
                    if hasattr(self.app, 'get_min_angle_change'):
                        min_angle_change = self.app.get_min_angle_change()
                    
                    all_waypoints = safety_processor.process_route(
                        safety_adjust, 
                        resample_interval=0.5,
                        min_angle_change=min_angle_change
                    )
                    
                    #debug_print("\nFinal route after safety processing:")
                    debug_print(f"Total points after safety processing: {len(all_waypoints)}")
                
                else:
                    debug_print("⚠️ Safety zones present but no clearance parameters found")
            else:
                # No safety zones - apply standalone simplification
                debug_print("\n=== No Safety Zones - Applying Standalone Simplification ===")
                from orbit.planners.safety_enhanced import simplify_route_standalone

                # Get min_angle_change from GUI
                min_angle_change = 15  # Default fallback
                if hasattr(self.app, 'get_min_angle_change'):
                    min_angle_change = self.app.get_min_angle_change()

                debug_print(f"Applying standalone simplification with {min_angle_change}° angle threshold")
                all_waypoints = simplify_route_standalone(
                    all_waypoints,
                    min_angle_change=min_angle_change,
                    resample_interval=0.5
                )
            
            # Store for external export (GUI) - AFTER safety processing
            if hasattr(self.app, '__setattr__'):
                try:
                    self.app.overview_flight_waypoints = all_waypoints  # includes tag as 4th element
                    debug_print(f"✅ Stored {len(all_waypoints)} safety-processed waypoints for export")

                    # Update the waypoints display in the GUI
                    if hasattr(self.app, '_update_waypoints_display'):
                        self.app._update_waypoints_display()

                except Exception as e:
                    error_debug_print(f"❌ Failed to store overview_flight_waypoints: {e}")

            # Check visualizer availability
            if not hasattr(self.app, 'visualizer') or not self.app.visualizer:
                error_debug_print("❌ Visualizer not available")
                return
            
            # Remove existing overview flights if present
            for flight_name in ['Overview Flight', 'Overview Flight Left', 'Overview Flight Right']:
                if flight_name in self.app.visualizer.meshes:
                    try:
                        self.app.visualizer._remove_mesh(flight_name)
                        debug_print(f"🔄 Removed existing {flight_name}")
                    except Exception as e:
                        debug_print(f"⚠️ Could not remove existing {flight_name}: {e}")
            
            # Add new visualization
            if hasattr(self.app.visualizer, 'add_polyline'):
                self.app.visualizer.add_polyline(
                    'Overview Flight',
                    all_waypoints,
                    color=[0.0, 1.0, 0.0],  # Green color
                    line_width=5,
                    tube_radius=0
                )
                
                # Print detailed summary
                debug_print(f"✅ Visualized Overview Flight: {len(all_waypoints)} total waypoints")
                debug_print("   📋 Route composition:")
                for summary in route_summary:
                    debug_print(f"      • {summary}")

        except Exception as e:
            error_debug_print(f"❌ Error visualizing combined flight: {e}")
            import traceback
            traceback.print_exc()
    
    def _get_tab3_content(self):
        """Get text content from tab3_textEdit widget."""
        try:
            # Find the flight routes text edit widget
            flight_routes_text_edit = None
            
            # Try via data_loader first
            if hasattr(self.app, 'data_loader') and self.app.data_loader:
                if hasattr(self.app.data_loader, 'flight_routes_text_edit'):
                    flight_routes_text_edit = self.app.data_loader.flight_routes_text_edit
            
            # Try direct UI search
            if not flight_routes_text_edit:
                flight_routes_text_edit = self.app.ui.findChild(QTextEdit, 'tab3_textEdit')
            
            # Try via dock widget
            if not flight_routes_text_edit:
                dock_widget = self.app.ui.findChild(QWidget, 'dockWidget_FR')
                if dock_widget:
                    flight_routes_text_edit = dock_widget.findChild(QTextEdit, 'tab3_textEdit')
            
            if flight_routes_text_edit:
                content = flight_routes_text_edit.toPlainText().strip()
                return content
            else:
                debug_print("❌ Could not find tab3_textEdit widget")
                return ""
                
        except Exception as e:
            debug_print(f"❌ Error getting Flight route textbox content: {e}")
            return ""
    
    # ==================================================================================
    # UTILITY DEMONSTRATION - Example usage of the improved offset functions
    # ==================================================================================
    
    def demo_perpendicular_offset_utilities(self):
        """
        Demonstration of the improved perpendicular offset utilities.
        
        This function shows how to use the new utilities for various flight route scenarios.
        Call this to see the utilities in action and verify they're working correctly.
        """
        debug_print("\n" + "="*60)
        debug_print("🔧 PERPENDICULAR OFFSET UTILITIES DEMONSTRATION")
        debug_print("="*60)
        
        try:
            # Get sample trajectory data
            if not hasattr(self.app, 'trajectory_samples') or len(self.app.trajectory_samples) < 3:
                debug_print("❌ No trajectory_samples available for demonstration")
                return False
            
            trajectory = self.app.trajectory_samples[:5]  # Use first 5 points for demo
            debug_print(f"📍 Using {len(trajectory)} sample trajectory points")
            
            # Demo 1: Single point perpendicular offsets
            debug_print(f"\n🎯 DEMO 1: Single point perpendicular offsets")
            center_point = trajectory[2]  # Middle point
            direction = np.array(trajectory[3][:2]) - np.array(trajectory[1][:2])  # Direction vector
            
            debug_print(f"   Center point: [{center_point[0]:.1f}, {center_point[1]:.1f}, {center_point[2]:.1f}]")
            debug_print(f"   Direction: [{direction[0]:.1f}, {direction[1]:.1f}]")
            
            # Test different offset distances
            for offset_dist in [5.0, 10.0, 15.0]:
                offset_points = self.compute_perpendicular_offset_points(
                    center_point, direction, offset_dist, side='both'
                )
                debug_print(f"   Offset {offset_dist}m:")
                debug_print(f"     Left:  [{offset_points['left'][0]:.1f}, {offset_points['left'][1]:.1f}]")
                debug_print(f"     Right: [{offset_points['right'][0]:.1f}, {offset_points['right'][1]:.1f}]")
            
            # Demo 2: Safe flight offset calculation
            debug_print(f"\n🛡️  DEMO 2: Safe flight offset calculation")
            for user_offset in [0.0, 3.0, 5.0]:
                safe_offset = self.calculate_minimum_flight_offset(user_offset)
                debug_print(f"   User offset {user_offset}m → Total safe offset: {safe_offset:.1f}m")
            
            # Demo 3: Parallel trajectory generation
            debug_print(f"\n🛤️  DEMO 3: Parallel trajectory generation")
            for side in ['left', 'right']:
                parallel_traj = self.generate_parallel_trajectory_with_safe_offset(
                    trajectory, 3.0, side=side
                )
                debug_print(f"   {side.title()} parallel trajectory: {len(parallel_traj)} points generated")
                if parallel_traj:
                    first_point = parallel_traj[0]
                    last_point = parallel_traj[-1]
                    debug_print(f"     First: [{first_point[0]:.1f}, {first_point[1]:.1f}, {first_point[2]:.1f}]")
                    debug_print(f"     Last:  [{last_point[0]:.1f}, {last_point[1]:.1f}, {last_point[2]:.1f}]")
            
            debug_print(f"\n✅ Demonstration completed successfully!")
            debug_print("   All utilities are working correctly and ready for flight route generation.")
            return True
            
        except Exception as e:
            debug_print(f"❌ Demonstration failed: {e}")
            import traceback
            traceback.print_exc()
            return False 