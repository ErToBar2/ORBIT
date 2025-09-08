"""UnderdeckRouteGenerator
========================
Generate under-deck inspection routes using the COMPLETE original v0.71 logic.

This implements the full underdeck flight pattern from the legacy code including:
1. Base points computation with thresholds_zones (pillar avoidance)
2. Custom zone angles support
3. Multi-pass back-and-forth patterns (num_passes)
4. Vertical connection flights (connection_height)
5. Proper span-based processing with variable height offsets

The original pattern creates sophisticated underdeck inspection routes that follow
the bridge structure closely with multiple passes and proper pillar avoidance.
"""
from __future__ import annotations

from typing import List, Dict, Any, Tuple, List, Any
import numpy as np
from .safety_enhanced import EnhancedSafetyProcessor

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

def generate_underdeck_routes(app) -> List[Dict[str, Any]]:
    """Generate under-deck Pinspection routes using the complete original v0.71 logic.

    This implements the exact same algorithm as the legacy code including all
    missing features: thresholds_zones, custom_zone_angles, num_passes, connection_height.

    Parameters
    ----------
    app : OrbitMainApp
        The running GUI instance with trajectory_samples and parsed data

    Returns
    -------
    List[Dict[str, Any]]
        List of route dictionaries with 'points' and 'tags' for visualization
    """
    
    
    debug_print("\n" + "="*60)
    debug_print("🛠  UNDER-DECK INSPECTION ROUTE GENERATION")
    debug_print("="*60)
    
    try:
        # Step 1: Update parsed data
        if hasattr(app, '_update_parsed_data'):
            app._update_parsed_data()
            debug_print("✅ Updated parsed data from text boxes")
        
        # Step 2: Validate trajectory_samples availability
        if not hasattr(app, 'trajectory_samples') or len(getattr(app, 'trajectory_samples', [])) == 0:
            debug_print("❌ trajectory_samples not available")
            return []
        
        debug_print(f"✅ Using trajectory_samples: {len(app.trajectory_samples)} points")
        
        # Step 3: Parse parameters from text boxes
        params = _parse_underdeck_parameters(app)
        if not params:
            debug_print("❌ Failed to parse underdeck parameters")
            return []
        
        debug_print(f"✅ Parsed underdeck parameters")
        _print_parameters(params)
        
        # Step 4: Generate underdeck routes using complete original logic
        underdeck_routes = _generate_underdeck_routes_complete_logic(app.trajectory_samples, params, app)
        
        if not underdeck_routes:
            debug_print("❌ No underdeck routes generated")
            return []
        
        debug_print(f"✅ Generated {len(underdeck_routes)} underdeck routes")
        
        # Step 5: Apply safety checks and create combined routes if needed
        final_routes = _apply_safety_checks_to_underdeck_routes(underdeck_routes, params, app.trajectory_samples, app)

        # Step 5.5: Fix connection speed tags for consistent vertical flight speeds
        final_routes = _fix_connection_speed_tags(final_routes)

        # Step 6: Visualize routes
        _visualize_underdeck_routes(app, final_routes)
        
        # Step 7: Store routes for export
        app.underdeck_flight_routes = final_routes  # type: ignore[attr-defined]
        
        # Step 8: Store tagged waypoints for export (same format as overview flights)
        underdeck_flight_waypoints = []
        for route in final_routes:
            route_points = route.get('points', [])
            for point in route_points:
                if len(point) >= 4:
                    # Point format: [x, y, z, tag]
                    underdeck_flight_waypoints.append([point[0], point[1], point[2], point[3]])
                elif len(point) >= 3:
                    # Fallback: use route ID as tag
                    underdeck_flight_waypoints.append([point[0], point[1], point[2], route.get('id', 'underdeck')])
        
        app.underdeck_flight_waypoints = underdeck_flight_waypoints  # type: ignore[attr-defined]
        debug_print(f"✅ Stored {len(underdeck_flight_waypoints)} tagged waypoints for export")



        return final_routes
        
    except Exception as e:
        error_debug_print(f"❌ Under-deck route generation failed: {e}")
        import traceback
        traceback.print_exc()
        return []


def _parse_underdeck_parameters(app) -> Dict[str, Any]:
    """Parse underdeck parameters from text boxes."""
    
    if not hasattr(app, 'parsed_data'):
        return {}
    
    flight_data = app.parsed_data.get("flight_routes", {})
    project_data = app.parsed_data.get("project", {})
    
    params = {
        # Core parameters
        'horizontal_offsets_underdeck': flight_data.get('horizontal_offsets_underdeck', [13, 13, 13]),
        'height_offsets_underdeck': flight_data.get('height_offsets_underdeck', [[5.25, 5.5, 6], [6, 5.5, 5.25, 5, 5.25, 5.5, 6], [6, 5.55, 5.2]]),
        'num_points': flight_data.get('num_points', [3, 7, 3]),
        'general_height_offset': flight_data.get('general_height_offset', 1.0),
        'bridge_width': project_data.get('bridge_width', 13.29),
        
        # NEW: Missing parameters from original
        'thresholds_zones': flight_data.get('thresholds_zones', [(10, 5), (7, 7), (5, 10)]),
        'custom_zone_angles': flight_data.get('custom_zone_angles', []),
        'num_passes': flight_data.get('num_passes', 2),
        'connection_height': flight_data.get('connection_height', 20.0),
        
        # NEW: Additional parameters for improved functionality  
        'underdeck_split': flight_data.get('underdeck_split', 1),
        'safety_check_underdeck': flight_data.get('safety_check_underdeck', [[0], [0], [0]]),
        'underdeck_axial': flight_data.get('underdeck_axial', 0),
        'n_girders': flight_data.get('n_girders', 5),
        
        # Derived values
        'num_spans': len(flight_data.get('horizontal_offsets_underdeck', [13, 13, 13]))
    }
    
    # Add bridge_width/2 to horizontal offsets (as per original logic)
    params['horizontal_offsets_underdeck'] = [x + (params['bridge_width']/2) for x in params['horizontal_offsets_underdeck']]
    
    return params


def _print_parameters(params: Dict[str, Any]):
    """Print parameters for debugging."""
    debug_print("🔧 Complete underdeck parameters:")
    debug_print(f"   num_spans: {params['num_spans']}")
    debug_print(f"   horizontal_offsets_underdeck: {params['horizontal_offsets_underdeck']}")
    debug_print(f"   height_offsets_underdeck: {params['height_offsets_underdeck']}")
    debug_print(f"   num_points: {params['num_points']}")
    debug_print(f"   thresholds_zones: {params['thresholds_zones']}")
    debug_print(f"   custom_zone_angles: {params['custom_zone_angles']}")
    debug_print(f"   num_passes: {params['num_passes']}")
    debug_print(f"   connection_height: {params['connection_height']}")
    debug_print(f"   bridge_width: {params['bridge_width']}")
    debug_print(f"   underdeck_split: {params['underdeck_split']}")
    debug_print(f"   safety_check_underdeck: {params['safety_check_underdeck']}")
    debug_print(f"   underdeck_axial: {params['underdeck_axial']}")
    debug_print(f"   n_girders: {params['n_girders']}")


def _generate_underdeck_routes_complete_logic(trajectory_samples: List, params: Dict[str, Any], app=None) -> List[Dict[str, Any]]:
    # NEW: sections + pillar-derived default angles
    distances_pillars, default_angles = _derive_sections_and_angles_from_pillars(trajectory_samples, app)
    debug_print(f"🏗️  Calculated pillar-based sections: {distances_pillars}")
    

    def _angles_missing(val) -> bool:
        """True if custom_zone_angles are effectively empty / unspecified."""
        if val is None:
            return True
        if isinstance(val, str):
            s = val.strip().lower()
            return s in ("", "none", "non", "null", "[]")
        if isinstance(val, (list, tuple)):
            return len(val) == 0
        return False

    def _maybe_autofill_custom_angles(app, default_angles: list, params: dict, textbox_name: str):
        """If the user didn't provide custom_zone_angles, write pillar-derived angles to the UI and parsed_data."""
        try:
            if not hasattr(app, 'parsed_data'):
                return
            flight = app.parsed_data.get('flight_routes', {})
            existing = flight.get('custom_zone_angles')

            if _angles_missing(existing):
                pretty = [round(float(a), 2) for a in (default_angles or [])]

                # 1) Update the visible textbox
                if hasattr(app, 'update_textbox_variables'):
                    app.update_textbox_variables(
                        textbox_name,
                        {"custom_zone_angles": pretty}
                    )

                # 2) Persist in parsed_data and local params
                flight['custom_zone_angles'] = pretty
                app.parsed_data['flight_routes'] = flight
                params['custom_zone_angles'] = pretty

                debug_print(f"🖊️ Autofilled custom_zone_angles from pillars → {pretty}")
            else:
                debug_print("ℹ️ custom_zone_angles provided by user; not overwriting.")
        except Exception as e:
            debug_print(f"⚠️ Could not autofill custom_zone_angles: {e}")
    # Update textbox with calculated default angles if app has the update function
    if app is not None:
        _maybe_autofill_custom_angles(
            app,
            default_angles,
            params,
            textbox_name="tab3_textEdit"  # <-- set this to your actual textbox name
        )

    # Base points with thresholds (buffers from section boundaries)
    base_points = _compute_base_points_with_thresholds(
        trajectory_samples, distances_pillars, params['thresholds_zones'], params['num_points']
    )
    debug_print(f"🎯 Computed base points with thresholds for {len(base_points)} spans")

    # OPTIONAL OVERRIDE: if a span's custom angle is "00", build base points from
    # pillar-parallel baselines rather than the trajectory normal.
    override_spans = set()
    try:
        custom_angles_raw = params.get('custom_zone_angles', [])
        override_spans = _spans_with_pillar_parallel_override(custom_angles_raw)
        if override_spans:
            debug_print(f"🟢 '00' override activated for spans: {sorted(list(override_spans))}")
            pairs_sorted, centers_chain = _get_pillar_pairs_sorted_by_chain(app, np.asarray(trajectory_samples, dtype=float))
            per_pair_angles: Dict[int, List[float]] = {}
            per_pair_crossings: Dict[int, List[List[float]]] = {}
            for span_idx in sorted(override_spans):
                # Only inner spans are bounded by two pillars: 1..len(pairs_sorted)-1
                if span_idx <= 0 or span_idx >= len(pairs_sorted):
                    debug_print(f"   ⚠️ Span {span_idx+1}: cannot apply pillar-parallel override (missing bounding pillars)")
                    continue
                mids, angles_deg, crossings = _compute_pillar_parallel_pairs_and_midpoints_for_span(
                    span_idx,
                    pairs_sorted,
                    np.asarray(trajectory_samples, dtype=float),
                    params.get('num_points', []),
                    params.get('thresholds_zones', [])
                )
                if mids:
                    base_points[span_idx] = mids
                    per_pair_angles[span_idx] = angles_deg
                    per_pair_crossings[span_idx] = crossings
            debug_print(f"🪄 Applied pillar-parallel base points override for spans: {sorted(list(override_spans))}")
            # stash crossings for optional downstream use/debug
            params['_pillar_parallel_crossings'] = per_pair_crossings
    except Exception as e:
        debug_print(f"⚠️ Pillar-parallel override not applied: {e}")

    # Normals along the path
    normals = _compute_normals_for_base_points(base_points)
    debug_print(f"📐 Computed normals for trajectory")

    # Heights
    adjusted_height_offsets = _adjust_height_offsets(
        params['height_offsets_underdeck'], params['num_points'], params['general_height_offset']
    )
    debug_print(f"📏 Adjusted height offsets")

    # FINAL angles: custom overrides pillar-derived default
    angles_zones = _resolve_span_angles(default_angles, params.get('custom_zone_angles', []))
    # If we have per-pair angles for override spans, install them to override span-level angles
    try:
        if override_spans:
            for s in override_spans:
                if '_pillar_parallel_crossings' in params:
                    # angles were kept alongside crossings length
                    cross_list = params.get('_pillar_parallel_crossings', {}).get(s, [])
                else:
                    cross_list = []
                # Retrieve computed per-pair angles from earlier block if present
                # We re-compute here safely if not stashed
                if isinstance(angles_zones, list):
                    # retrieve angles computed earlier in override block
                    # note: store angles in local map available in closure via per_pair_angles
                    try:
                        # mypy: best-effort; per_pair_angles may not exist if earlier block failed
                        if 'per_pair_angles' in locals() and s in per_pair_angles:
                            angles_zones[s] = per_pair_angles[s]
                            debug_print(f"   🔁 Span {s+1}: replacing span-angle with {len(per_pair_angles[s])} per-pair angles")
                    except Exception:
                        pass
    except Exception:
        pass
    debug_print(f"🔄 Final angles for spans (deg): {angles_zones}")
    if override_spans:
        debug_print(f"ℹ️ Pillar-parallel spans {sorted(list(override_spans))} set angle to 0° – angles not used in offset computation for these spans.")

    # Offset points
    offset_points_underdeck = _compute_points_with_horizontal_offset(
        base_points, normals, params['horizontal_offsets_underdeck'],
        adjusted_height_offsets, angles_zones
    )
    debug_print(f"🎯 Computed offset points for underdeck routes")
    if override_spans:
        # Log which horizontal offsets were applied to the override spans
        h_off = params.get('horizontal_offsets_underdeck', [])
        for s in sorted(list(override_spans)):
            off_val = (h_off[s] if s < len(h_off) else (h_off[-1] if h_off else 0.0))
            debug_print(f"   ↳ Span {s+1}: using horizontal_offset={off_val:.2f}m with angle=0° (pillar-parallel)")

        # Replace offset points for override spans so that each pair lies directly on the
        # pillar baselines (right: P1.x1y1→P2.x1y1, left: P1.x2y2→P2.x2y2), divided by thresholds
        # and num_points, and heights adjusted. No trajectory-based angles or normals.
        try:
            pairs_sorted, _centers_chain = _get_pillar_pairs_sorted_by_chain(app, np.asarray(trajectory_samples, dtype=float))
            for s in sorted(list(override_spans)):
                off_val = (h_off[s] if s < len(h_off) else (h_off[-1] if h_off else 0.0))
                height_list = adjusted_height_offsets[s] if s < len(adjusted_height_offsets) else [0.0]
                repl = _compute_pillar_parallel_offsets_for_span(
                    s,
                    pairs_sorted,
                    np.asarray(trajectory_samples, dtype=float),
                    params.get('num_points', []),
                    params.get('thresholds_zones', []),
                    off_val,
                    height_list
                )
                if repl:
                    offset_points_underdeck[s] = repl
                    debug_print(f"   🔄 Span {s+1}: replaced with {len(repl)//2} pillar-parallel offset pairs from trajectory crossings @ ±{off_val:.2f}m")
        except Exception as e:
            debug_print(f"⚠️ Could not replace offset points for pillar-parallel spans: {e}")

    # Multi-pass crossing
    routes = _create_multipass_underdeck_routes(offset_points_underdeck, params)

    # Optional axial
    if params.get('underdeck_axial', 0) == 1:
        axial_routes = _create_axial_underdeck_routes(
            base_points, normals, offset_points_underdeck,
            adjusted_height_offsets, angles_zones, params
        )
        routes.extend(axial_routes)
        debug_print(f"✅ Generated {len(axial_routes)} axial underdeck routes")

    return routes



def _apply_safety_checks_to_underdeck_routes(routes: List[Dict[str, Any]], params: Dict[str, Any], 
                                           trajectory_samples: List, app) -> List[Dict[str, Any]]:
    """Apply safety checks to underdeck routes if enabled."""
    
    # Step 9: Apply safety checks if enabled
    processed_routes = _apply_safety_checks_to_routes(routes, params, trajectory_samples, app)
    
    # Step 10: Create combined route if underdeck_split = 0
    if params.get('underdeck_split', 1) == 0:
        combined_route = _create_combined_underdeck_route(processed_routes, params)
        if combined_route:
            processed_routes.append(combined_route)
            debug_print(f"✅ Created combined underdeck route with {len(combined_route.get('points', []))} total points")
    
    return processed_routes




def _compute_base_points_with_thresholds(trajectory: List, distances_pillars: List[float], 
                                       thresholds_zones: List[Tuple], num_points: List[int]) -> List[List]:
    """Compute base points with thresholds_zones (exact replica of original compute_base_points)."""
    
    trajectory_array = np.array(trajectory)
    sections_base_points = []
    start_distance = 0
    
    for section_index, distance in enumerate(distances_pillars):
        end_distance = start_distance + distance
        
        # Apply thresholds_zones (pillar avoidance buffers)
        threshold_start = thresholds_zones[section_index][0] if section_index < len(thresholds_zones) else 0
        threshold_end = thresholds_zones[section_index][1] if section_index < len(thresholds_zones) else 0
        
        section_start_distance = start_distance + threshold_start
        section_end_distance = end_distance - threshold_end
        
        debug_print(f"   Span {section_index+1}: total={distance:.1f}m, thresholds=({threshold_start}, {threshold_end}), "
              f"effective={section_end_distance - section_start_distance:.1f}m")
        
        # Calculate the total length of the current section
        section_length = section_end_distance - section_start_distance
        if section_length <= 0 or num_points[section_index] <= 0:
            sections_base_points.append([])
            start_distance = end_distance
            continue
        
        # Calculate intervals between base points within the section
        if num_points[section_index] == 1:
            interval = section_length  # One point at center
        else:
            interval = section_length / (num_points[section_index] - 1)
        
        # Find base points along trajectory
        section_points = []
        current_distance = 0
        accumulated_distance = 0
        found_base_points = 0
        
        for i in range(1, len(trajectory_array)):
            if found_base_points >= num_points[section_index]:
                break
            
            prev_point = trajectory_array[i - 1]
            current_point = trajectory_array[i]
            segment_length = np.linalg.norm(current_point - prev_point)
            
            while accumulated_distance + segment_length >= section_start_distance + found_base_points * interval:
                if found_base_points >= num_points[section_index]:
                    break
                
                # Distance from the start of the segment to the required base point
                distance_into_segment = (section_start_distance + found_base_points * interval) - accumulated_distance
                
                # Interpolate to find the base point
                ratio = distance_into_segment / segment_length
                base_point = prev_point + ratio * (current_point - prev_point)
                section_points.append(base_point.tolist())
                found_base_points += 1
            
            accumulated_distance += segment_length
        
        sections_base_points.append(section_points)
        start_distance = end_distance
    
    return sections_base_points


def _spans_with_pillar_parallel_override(custom_angles_raw) -> set:
    """Return indices of spans that request pillar-parallel override via the sentinel '00'.

    We intentionally require a string '00' (optionally with whitespace or a trailing degree sign)
    to avoid colliding with numeric 0. Using numeric 0 continues to mean 0° relative
    to the trajectory (legacy behavior).
    """
    spans: set = set()
    if not isinstance(custom_angles_raw, (list, tuple)):
        return spans
    for i, val in enumerate(custom_angles_raw):
        if isinstance(val, str):
            s = val.strip().lower().replace('°', '')
            if s == '00':
                spans.add(i)
    return spans


def _get_pillar_pairs_sorted_by_chain(app, traj_np: np.ndarray):
    """Return (pairs_sorted, centers_chain) for pillar edge pairs ordered along trajectory.

    pairs_sorted: list of [[x1,y1], [x2,y2]] per pillar (two edge points per pillar)
    centers_chain: list of chainage values (meters) of each pillar center along trajectory
    """
    # 1) Gather XY points for pillar edges in project coordinates
    pillars_xy_flat: list = []
    if app is not None and getattr(app, "pillars_project_xy", None):
        pillars_xy_flat = [tuple(map(float, p)) for p in app.pillars_project_xy]
    elif app is not None and getattr(app, "current_pillars", None):
        def _proj(lat, lon):
            try:
                if getattr(app, "_last_transform_func", None):
                    x, y, _ = app._last_transform_func(float(lat), float(lon), 0.0)
                    return float(x), float(y)
                if getattr(app, "current_context", None):
                    x, y, _ = app.current_context.wgs84_to_project(float(lon), float(lat), 0.0)
                    return float(x), float(y)
            except Exception:
                pass
            return float(lon), float(lat)
        for p in app.current_pillars:
            lat = p.get("lat"); lon = p.get("lon")
            if lat is None or lon is None:
                continue
            pillars_xy_flat.append(_proj(lat, lon))

    if not pillars_xy_flat or len(pillars_xy_flat) < 2:
        return [], []

    # 2) Group into edge pairs per pillar: (0,1), (2,3), ...
    pairs: list = []
    i = 0
    while i < len(pillars_xy_flat):
        if i + 1 < len(pillars_xy_flat):
            a = np.array(pillars_xy_flat[i], dtype=float)
            b = np.array(pillars_xy_flat[i+1], dtype=float)
            pairs.append([a, b])
            debug_print(f"   🔗 Pillar pair {(i//2)+1}: A=({a[0]:.2f},{a[1]:.2f}) B=({b[0]:.2f},{b[1]:.2f})")
            i += 2
        else:
            # odd leftover – duplicate
            a = np.array(pillars_xy_flat[i], dtype=float)
            pairs.append([a, a.copy()])
            debug_print(f"   🔗 Pillar pair {(i//2)+1}: single point duplicated A=({a[0]:.2f},{a[1]:.2f})")
            i += 1

    # 3) Sort by chainage of pair centers along trajectory
    def _project_point_to_chainage(pt_xy, traj_xy):
        best_d = 1e30
        best_s = 0.0
        acc = 0.0
        for j in range(1, traj_xy.shape[0]):
            a = traj_xy[j-1]; b = traj_xy[j]
            ab = b - a
            L2 = float(np.dot(ab, ab))
            if L2 <= 0:
                continue
            t = float(np.clip(np.dot(pt_xy - a, ab) / L2, 0.0, 1.0))
            p = a + t * ab
            d = float(np.linalg.norm(pt_xy - p))
            if d < best_d:
                best_d = d
                best_s  = acc + t * float(np.linalg.norm(ab))
            acc += float(np.linalg.norm(ab))
        return best_s

    traj_xy = traj_np[:, :2]
    centers = [0.5 * (p[0] + p[1]) for p in pairs]
    chains = [
        _project_point_to_chainage(np.asarray(c, float), traj_xy)
        for c in centers
    ]
    order = np.argsort(np.asarray(chains))
    pairs_sorted = [pairs[int(k)] for k in order]
    centers_chain = [float(chains[int(k)]) for k in order]
    for idx, (pair, s) in enumerate(zip(pairs_sorted, centers_chain), start=1):
        c = 0.5 * (pair[0] + pair[1])
        debug_print(f"   📍 Pillar order {idx}: center=({c[0]:.2f},{c[1]:.2f}), chainage={s:.2f}m")
    return pairs_sorted, centers_chain


def _compute_pillar_parallel_base_points_for_span(span_idx: int,
                                                  pairs_sorted: list,
                                                  centers_chain: list,
                                                  traj_np: np.ndarray,
                                                  num_points: List[int],
                                                  thresholds_zones: List[Tuple]) -> List[List[float]]:
    """Generate base points along the straight midline between two neighboring pillars.

    - Applies thresholds_zones[span_idx] as start/end buffers (in meters) from each pillar
    - Distributes num_points[span_idx] uniformly along the effective midline segment
    - Z at each base point is interpolated from the nearest trajectory segment
    """
    if span_idx <= 0 or span_idx >= len(pairs_sorted):
        return []

    # Build midline between pillar centers of bounding pillars
    pA = pairs_sorted[span_idx - 1]
    pB = pairs_sorted[span_idx]
    c0 = 0.5 * (np.asarray(pA[0], float) + np.asarray(pA[1], float))
    c1 = 0.5 * (np.asarray(pB[0], float) + np.asarray(pB[1], float))
    seg = c1 - c0
    L = float(np.linalg.norm(seg))
    if L <= 1e-6:
        return []

    seg_dir = seg / L
    debug_print(f"   🧮 Span {span_idx+1} pillar centers: C0=({c0[0]:.2f},{c0[1]:.2f}) C1=({c1[0]:.2f},{c1[1]:.2f}) length={L:.2f}m")

    # Thresholds for this span
    thr_start = thresholds_zones[span_idx][0] if span_idx < len(thresholds_zones) else 0.0
    thr_end   = thresholds_zones[span_idx][1] if span_idx < len(thresholds_zones) else 0.0
    eff_len = max(0.0, L - float(thr_start) - float(thr_end))
    n = num_points[span_idx] if span_idx < len(num_points) else 0
    if eff_len <= 0.0 or n <= 0:
        return []

    debug_print(f"   🚧 thresholds: start={thr_start:.2f}m end={thr_end:.2f}m → effective={eff_len:.2f}m, points={n}")

    # Interpolate Z from nearest trajectory segment
    traj = np.asarray(traj_np, float)
    def _interp_z_near(xy: np.ndarray) -> float:
        best_d = 1e30
        best_z = float(traj[0][2]) if traj.shape[1] >= 3 else 0.0
        for j in range(1, traj.shape[0]):
            a = traj[j-1][:2]; b = traj[j][:2]
            v = b - a
            L2 = float(np.dot(v, v))
            if L2 <= 0: 
                continue
            t = float(np.clip(np.dot(xy - a, v) / L2, 0.0, 1.0))
            p = a + t * v
            d = float(np.linalg.norm(xy - p))
            if d < best_d:
                best_d = d
                # linear z along the same segment proportion t
                za = float(traj[j-1][2]) if traj.shape[1] >= 3 else 0.0
                zb = float(traj[j][2])   if traj.shape[1] >= 3 else 0.0
                best_z = (1.0 - t) * za + t * zb
        return best_z

    # Compute sample positions along effective segment
    if n == 1:
        s_positions = [float(thr_start + 0.5 * eff_len)]
    else:
        interval = eff_len / float(n - 1)
        s_positions = [float(thr_start + k * interval) for k in range(n)]

    base_points: List[List[float]] = []
    for s in s_positions:
        xy = (c0 + s * seg_dir).tolist()
        z = _interp_z_near(np.asarray(xy, float))
        base_points.append([xy[0], xy[1], z])
    debug_print(f"   📍 Created {len(base_points)} pillar-parallel base points for span {span_idx+1}")

    return base_points


def _compute_pillar_parallel_pairs_and_midpoints_for_span(span_idx: int,
                                                          pairs_sorted: list,
                                                          traj_np: np.ndarray,
                                                          num_points: List[int],
                                                          thresholds_zones: List[Tuple]) -> Tuple[List[List[float]], List[float], List[List[float]]]:
    """Compute pillar-parallel right/left base lines, trimmed by thresholds, then build base point pairs.

    Returns:
      - midpoints (base points for this span)
      - angles_deg per base pair: angle of the R→L segment vs deck-normal at crossing
      - crossings per base pair: intersection points [x,y,z] onto trajectory polyline (Z from segment interpolation)
    """
    if span_idx <= 0 or span_idx >= len(pairs_sorted):
        return [], [], []

    # Right/Left points per pillar: assume index 0 is right, 1 is left
    pA_r, pA_l = np.asarray(pairs_sorted[span_idx - 1][0], float), np.asarray(pairs_sorted[span_idx - 1][1], float)
    pB_r, pB_l = np.asarray(pairs_sorted[span_idx][0], float),   np.asarray(pairs_sorted[span_idx][1], float)

    # Build right and left baselines
    v_r = pB_r - pA_r
    v_l = pB_l - pA_l
    Lr = float(np.linalg.norm(v_r)); Ll = float(np.linalg.norm(v_l))
    if Lr <= 1e-6 or Ll <= 1e-6:
        return [], [], []
    er = v_r / Lr; el = v_l / Ll

    # thresholds
    thr_start = thresholds_zones[span_idx][0] if span_idx < len(thresholds_zones) else 0.0
    thr_end   = thresholds_zones[span_idx][1] if span_idx < len(thresholds_zones) else 0.0
    eff_r = max(0.0, Lr - thr_start - thr_end)
    eff_l = max(0.0, Ll - thr_start - thr_end)
    n = num_points[span_idx] if span_idx < len(num_points) else 0
    if n <= 0 or eff_r <= 0.0 or eff_l <= 0.0:
        return [], [], []

    # sample positions (matched counts on both sides)
    if n == 1:
        s_r = [thr_start + 0.5 * eff_r]
        s_l = [thr_start + 0.5 * eff_l]
    else:
        step_r = eff_r / float(n - 1)
        step_l = eff_l / float(n - 1)
        s_r = [thr_start + k * step_r for k in range(n)]
        s_l = [thr_start + k * step_l for k in range(n)]

    # helper: project onto trajectory and compute deck-normal + z
    traj = np.asarray(traj_np, float)
    traj_xy = traj[:, :2]
    def _closest_segment_info(xy: np.ndarray) -> Tuple[int, float, np.ndarray, float]:
        best_d = 1e30; best_seg = 0; best_t = 0.0; best_p = traj_xy[0]
        acc = 0.0; s_at = 0.0
        for j in range(1, traj_xy.shape[0]):
            a = traj_xy[j-1]; b = traj_xy[j]
            v = b - a
            L2 = float(np.dot(v, v))
            if L2 <= 0:
                continue
            t = float(np.clip(np.dot(xy - a, v) / L2, 0.0, 1.0))
            p = a + t * v
            d = float(np.linalg.norm(xy - p))
            if d < best_d:
                best_d = d; best_seg = j; best_t = t; best_p = p
                s_at = acc + t * float(np.linalg.norm(v))
            acc += float(np.linalg.norm(v))
        return best_seg, best_t, best_p, s_at

    def _z_interp(seg_idx: int, t: float) -> float:
        za = float(traj[seg_idx-1][2]) if traj.shape[1] >= 3 else 0.0
        zb = float(traj[seg_idx][2])   if traj.shape[1] >= 3 else 0.0
        return (1.0 - t) * za + t * zb

    midpoints: List[List[float]] = []
    angles_deg: List[float] = []
    crossings: List[List[float]] = []

    for k in range(n):
        pr = pA_r + s_r[k] * er
        pl = pA_l + s_l[k] * el
        mid = 0.5 * (pr + pl)

        # crossing and angle vs deck-normal
        seg_idx, t_seg, p_xy, _s = _closest_segment_info(mid)
        z_cross = _z_interp(seg_idx, t_seg)
        crossings.append([float(p_xy[0]), float(p_xy[1]), z_cross])

        traj_dir = traj_xy[seg_idx] - traj_xy[seg_idx-1]
        Ld = float(np.linalg.norm(traj_dir))
        if Ld <= 0:
            deck_n = np.array([1.0, 0.0])
        else:
            traj_t = traj_dir / Ld
            deck_n = np.array([-traj_t[1], traj_t[0]])

        rl = pl - pr
        Lrl = float(np.linalg.norm(rl))
        rl_u = rl / Lrl if Lrl > 1e-9 else np.array([1.0, 0.0])
        dot = float(np.clip(np.dot(deck_n, rl_u), -1.0, 1.0))
        cross_z = float(deck_n[0]*rl_u[1] - deck_n[1]*rl_u[0])
        ang = float(np.degrees(np.arctan2(cross_z, dot)))

        midpoints.append([float(mid[0]), float(mid[1]), z_cross])
        angles_deg.append(ang)

    debug_print(f"   📍 Created {len(midpoints)} pillar-parallel pairs (midpoints) for span {span_idx+1}")
    return midpoints, angles_deg, crossings


def _compute_pillar_parallel_offsets_for_span(span_idx: int,
                                              pairs_sorted: list,
                                              traj_np: np.ndarray,
                                              num_points: List[int],
                                              thresholds_zones: List[Tuple],
                                              horizontal_offset: float,
                                              height_offsets: List[float]) -> List[List[float]]:
    """For a '00' span: place right/left points at a fixed perpendicular distance from the
    trajectory at the crossing with the R–L line sampled along the pillar baselines.

    - No angle usage; strictly normal to trajectory at crossing.
    - thresholds_zones control earliest/latest sampling along both right and left baselines.
    - height_offsets cycles per base pair.
    Returns flat list [R1, L1, R2, L2, ...].
    """
    if span_idx <= 0 or span_idx >= len(pairs_sorted):
        return []

    # Build right/left baselines
    pA_r, pA_l = np.asarray(pairs_sorted[span_idx - 1][0], float), np.asarray(pairs_sorted[span_idx - 1][1], float)
    pB_r, pB_l = np.asarray(pairs_sorted[span_idx][0], float),   np.asarray(pairs_sorted[span_idx][1], float)
    v_r = pB_r - pA_r
    v_l = pB_l - pA_l
    Lr = float(np.linalg.norm(v_r)); Ll = float(np.linalg.norm(v_l))
    if Lr <= 1e-6 or Ll <= 1e-6:
        return []
    er = v_r / Lr; el = v_l / Ll

    thr_start = thresholds_zones[span_idx][0] if span_idx < len(thresholds_zones) else 0.0
    thr_end   = thresholds_zones[span_idx][1] if span_idx < len(thresholds_zones) else 0.0
    eff_r = max(0.0, Lr - thr_start - thr_end)
    eff_l = max(0.0, Ll - thr_start - thr_end)
    n = num_points[span_idx] if span_idx < len(num_points) else 0
    if n <= 0 or eff_r <= 0.0 or eff_l <= 0.0:
        return []

    if n == 1:
        s_r = [thr_start + 0.5 * eff_r]
        s_l = [thr_start + 0.5 * eff_l]
    else:
        step_r = eff_r / float(n - 1)
        step_l = eff_l / float(n - 1)
        s_r = [thr_start + k * step_r for k in range(n)]
        s_l = [thr_start + k * step_l for k in range(n)]

    traj = np.asarray(traj_np, float)
    traj_xy = traj[:, :2]

    def _closest_segment_and_normal(xy: np.ndarray) -> Tuple[int, float, np.ndarray]:
        best_d = 1e30; best_seg = 1; best_t = 0.0
        for j in range(1, traj_xy.shape[0]):
            a = traj_xy[j-1]; b = traj_xy[j]
            v = b - a
            L2 = float(np.dot(v, v))
            if L2 <= 0:
                continue
            t = float(np.clip(np.dot(xy - a, v) / L2, 0.0, 1.0))
            p = a + t * v
            d = float(np.linalg.norm(xy - p))
            if d < best_d:
                best_d = d; best_seg = j; best_t = t
        a = traj_xy[best_seg-1]; b = traj_xy[best_seg]
        v = b - a
        L = float(np.linalg.norm(v))
        if L <= 0:
            nrm = np.array([1.0, 0.0])
        else:
            tdir = v / L
            nrm = np.array([-tdir[1], tdir[0]])
        return best_seg, best_t, nrm

    def _z_interp(seg_idx: int, t: float) -> float:
        za = float(traj[seg_idx-1][2]) if traj.shape[1] >= 3 else 0.0
        zb = float(traj[seg_idx][2])   if traj.shape[1] >= 3 else 0.0
        return (1.0 - t) * za + t * zb

    out: List[List[float]] = []
    for k in range(n):
        pr = pA_r + s_r[k] * er
        pl = pA_l + s_l[k] * el
        mid = 0.5 * (pr + pl)

        seg_idx, t_seg, nrm = _closest_segment_and_normal(mid)
        a = traj_xy[seg_idx-1]; b = traj_xy[seg_idx]
        p_xy = a + t_seg * (b - a)
        zc = _z_interp(seg_idx, t_seg)

        # Place right/left points at fixed perpendicular distance from crossing point
        nrm_u = nrm / (np.linalg.norm(nrm) + 1e-12)
        h = height_offsets[k % len(height_offsets)] if height_offsets else 0.0
        right = [float(p_xy[0] + horizontal_offset * nrm_u[0]), float(p_xy[1] + horizontal_offset * nrm_u[1]), float(zc - h)]
        left  = [float(p_xy[0] - horizontal_offset * nrm_u[0]), float(p_xy[1] - horizontal_offset * nrm_u[1]), float(zc - h)]
        out.append(right)
        out.append(left)

    return out


def _compute_pillar_baseline_points_for_span(span_idx: int,
                                             pairs_sorted: list,
                                             traj_np: np.ndarray,
                                             num_points: List[int],
                                             thresholds_zones: List[Tuple],
                                             height_offsets: List[float]) -> List[List[float]]:
    """Simplified '00' mode: generate points strictly on pillar baselines.

    Right baseline:  P1.x1y1 → P2.x1y1
    Left baseline:   P1.x2y2 → P2.x2y2

    - Apply thresholds_zones as distances from start/end of each baseline
    - Divide each baseline into num_points points
    - Adjust heights according to provided height_offsets (cycled)

    Returns flat list [R1, L1, R2, L2, ...] with Z lowered by height offset.
    """
    if span_idx <= 0 or span_idx >= len(pairs_sorted):
        return []

    pA_r, pA_l = np.asarray(pairs_sorted[span_idx - 1][0], float), np.asarray(pairs_sorted[span_idx - 1][1], float)
    pB_r, pB_l = np.asarray(pairs_sorted[span_idx][0], float),   np.asarray(pairs_sorted[span_idx][1], float)
    v_r = pB_r - pA_r
    v_l = pB_l - pA_l
    Lr = float(np.linalg.norm(v_r)); Ll = float(np.linalg.norm(v_l))
    if Lr <= 1e-6 or Ll <= 1e-6:
        return []
    er = v_r / Lr; el = v_l / Ll

    thr_start = thresholds_zones[span_idx][0] if span_idx < len(thresholds_zones) else 0.0
    thr_end   = thresholds_zones[span_idx][1] if span_idx < len(thresholds_zones) else 0.0
    eff_r = max(0.0, Lr - thr_start - thr_end)
    eff_l = max(0.0, Ll - thr_start - thr_end)
    n = num_points[span_idx] if span_idx < len(num_points) else 0
    if n <= 0 or eff_r <= 0.0 or eff_l <= 0.0:
        return []

    if n == 1:
        s_r = [thr_start + 0.5 * eff_r]
        s_l = [thr_start + 0.5 * eff_l]
    else:
        step_r = eff_r / float(n - 1)
        step_l = eff_l / float(n - 1)
        s_r = [thr_start + k * step_r for k in range(n)]
        s_l = [thr_start + k * step_l for k in range(n)]

    # Determine Z along baselines by sampling nearest trajectory segment Z (to respect height frame),
    # then subtract the configured height offsets.
    traj = np.asarray(traj_np, float)
    traj_xy = traj[:, :2]
    def _near_z(xy: np.ndarray) -> float:
        best_d = 1e30; best_seg = 1; best_t = 0.0
        for j in range(1, traj_xy.shape[0]):
            a = traj_xy[j-1]; b = traj_xy[j]
            v = b - a
            L2 = float(np.dot(v, v))
            if L2 <= 0:
                continue
            t = float(np.clip(np.dot(xy - a, v) / L2, 0.0, 1.0))
            p = a + t * v
            d = float(np.linalg.norm(xy - p))
            if d < best_d:
                best_d = d; best_seg = j; best_t = t
        za = float(traj[best_seg-1][2]) if traj.shape[1] >= 3 else 0.0
        zb = float(traj[best_seg][2])   if traj.shape[1] >= 3 else 0.0
        return (1.0 - best_t) * za + best_t * zb

    out: List[List[float]] = []
    for k in range(n):
        pr_xy = pA_r + s_r[k] * er
        pl_xy = pA_l + s_l[k] * el
        z_r = _near_z(pr_xy)
        z_l = _near_z(pl_xy)
        h = height_offsets[k % len(height_offsets)] if height_offsets else 0.0
        out.append([float(pr_xy[0]), float(pr_xy[1]), float(z_r - h)])
        out.append([float(pl_xy[0]), float(pl_xy[1]), float(z_l - h)])

    return out

def _generate_span_angles_with_custom(num_spans: int, custom_angles: List, distances_pillars: List[float]) -> List[float]:
    """Generate angles for each span with custom_zone_angles support (like original)."""
    
    if custom_angles and len(custom_angles) >= num_spans:
        debug_print(f"   Using custom zone angles: {custom_angles[:num_spans]}")
        return custom_angles[:num_spans]
    else:
        # Default to 0 degrees for all spans (original behavior when no custom angles)
        debug_print(f"   Using default angles (0.0 degrees for all spans)")
        return [0.0] * num_spans


def _compute_normals_for_base_points(base_points: List[List]) -> List[np.ndarray]:
    """Compute normal vectors for base points."""
    
    all_points = []
    for span in base_points:
        all_points.extend(span)
    
    normals = []
    for i in range(len(all_points)):
        if i == 0:
            direction = np.array(all_points[i+1][:2]) - np.array(all_points[i][:2])
        elif i == len(all_points) - 1:
            direction = np.array(all_points[i][:2]) - np.array(all_points[i-1][:2])
        else:
            dir1 = np.array(all_points[i][:2]) - np.array(all_points[i-1][:2])
            dir2 = np.array(all_points[i+1][:2]) - np.array(all_points[i][:2])
            direction = (dir1 + dir2) / 2
        
        if np.linalg.norm(direction) > 1e-6:
            normal = np.array([-direction[1], direction[0], 0])
            normal = normal / np.linalg.norm(normal)
        else:
            normal = np.array([1, 0, 0])
        
        normals.append(normal)
    
    return normals


def _adjust_height_offsets(height_offsets: List[List], num_points: List[int], 
                         general_offset: float) -> List[List]:
    """Adjust height offsets with general_height_offset."""
    
    adjusted = []
    for span_idx, span_heights in enumerate(height_offsets):
        span_num_points = num_points[span_idx] if span_idx < len(num_points) else 3
        
        # Apply general offset (as per original: [[y + self.general_height_offset for y in x] for x in self.height_offsets_underdeck])
        adjusted_span = [h + general_offset for h in span_heights]
        
        # Ensure we have enough height values for num_points
        while len(adjusted_span) < span_num_points:
            adjusted_span.extend(adjusted_span)  # Repeat pattern
        
        adjusted_span = adjusted_span[:span_num_points]  # Truncate if too many
        adjusted.append(adjusted_span)
    
    return adjusted


def _compute_points_with_horizontal_offset(base_points: List[List], normals: List[np.ndarray],
                                          horizontal_offsets: List[float], height_offsets: List[List],
                                          angles: List[Any]) -> List[List]:
    """Compute offset points; robust to per-span list length mismatches.

    angles may be either:
      - per-span float (legacy behavior)
      - per-span List[float] with one angle per base point (pillar-parallel override)
    """
    offset_points = []
    normal_idx = 0

    for section_index, points in enumerate(base_points):
        if not points:
            offset_points.append([])
            continue

        # safe fetches with sensible fallbacks
        offset = (horizontal_offsets[section_index] if section_index < len(horizontal_offsets)
                  else (horizontal_offsets[-1] if horizontal_offsets else 0.0))
        section_heights = (height_offsets[section_index] if section_index < len(height_offsets) and len(height_offsets[section_index]) > 0
                           else [0.0])
        angle_spec = angles[section_index] if section_index < len(angles) else 0.0

        section_points = []
        for i, base_point in enumerate(points):
            normal = normals[normal_idx % len(normals)] if normals else np.array([1.0, 0.0, 0.0])
            h = section_heights[i % len(section_heights)]

            # Resolve angle per base-point if a list is provided for this section
            if isinstance(angle_spec, (list, tuple)) and len(angle_spec) > 0:
                angle_here = float(angle_spec[i % len(angle_spec)])
            elif isinstance(angle_spec, (int, float)):
                angle_here = float(angle_spec)
            else:
                angle_here = 0.0

            pr = _calculate_adjusted_point(np.array(base_point),  offset, normal, h, angle_here)
            pl = _calculate_adjusted_point(np.array(base_point), -offset, normal, h, angle_here)

            section_points.append(pr.tolist())
            section_points.append(pl.tolist())
            normal_idx += 1

        offset_points.append(section_points)

    return offset_points


def _calculate_adjusted_point(point: np.ndarray, perpendicular_distance: float, 
                            normal: np.ndarray, height_offset: float, angle_degrees: float) -> np.ndarray:
    """Calculate adjusted point with angle compensation for distance."""
    
    angle_radians = np.deg2rad(angle_degrees)
    normalized_normal = normal / np.linalg.norm(normal)
    
    # IMPROVEMENT 1: Adjust distance when using angles to maintain actual offset
    if abs(angle_degrees) > 1e-6:  # If angle is not zero
        # Increase distance to compensate for angle projection
        adjusted_distance = perpendicular_distance / np.cos(angle_radians)
    else:
        adjusted_distance = perpendicular_distance
    
    rotation_matrix = np.array([
        [np.cos(angle_radians), -np.sin(angle_radians), 0],
        [np.sin(angle_radians), np.cos(angle_radians), 0],
        [0, 0, 1]
    ])
    
    rotated_normal = np.dot(rotation_matrix, normalized_normal)
    adjusted_point = point + adjusted_distance * rotated_normal
    adjusted_point[2] -= height_offset  # Negative Z for under-deck
    
    return adjusted_point


def _create_multipass_underdeck_routes(offset_points_underdeck: List[List], params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Create multi-pass underdeck routes with proper crossing pattern and vertical connections."""
    
    routes = []
    num_passes = params['num_passes']
    connection_height = params['connection_height']
    
    for span_idx, span_offset_points in enumerate(offset_points_underdeck):
        if not span_offset_points:
            continue
            
        # Extract right and left points (stored as [right1, left1, right2, left2, ...])
        right_points = []
        left_points = []
        
        for i in range(0, len(span_offset_points), 2):
            if i < len(span_offset_points):
                right_points.append(span_offset_points[i])
            if i + 1 < len(span_offset_points):
                left_points.append(span_offset_points[i + 1])
        
        if not right_points or not left_points:
            continue
            
        # IMPROVEMENT 3: Generate crossing pattern R1↔L1, R2↔L2, etc.
        route_points = []
        route_tags = []
        
        # Process each base point pair
        for base_idx in range(max(len(right_points), len(left_points))):
            right_point = right_points[base_idx] if base_idx < len(right_points) else right_points[-1]
            left_point = left_points[base_idx] if base_idx < len(left_points) else left_points[-1]
            
            # Determine number of passes for this base point
            is_middle_odd = (len(right_points) % 2 == 1) and (base_idx == len(right_points) // 2)
            passes_for_this_base = (2 * num_passes) if is_middle_odd else num_passes
            
            # IMPROVEMENT 2: Add vertical connections at first and last base points (BOTH SIDES)
            add_vertical_start = (base_idx == 0) and (connection_height > 0)
            add_vertical_end = (base_idx == max(len(right_points), len(left_points)) - 1) and (connection_height > 0)
            
            # Create crossing pattern for this base point pair with proper vertical connections
            for pass_num in range(passes_for_this_base):
                pass_tag = f"underdeck_span{span_idx+1}_base{base_idx+1}_pass{pass_num+1}"
                
                if pass_num % 2 != 0:
                    # Even passes: Right → Left with vertical connections
                    # R1
                    route_points.append([right_point[0], right_point[1], right_point[2], pass_tag])
                    route_tags.append(pass_tag)
                    
                    # R1_V (vertical connection at right point)
                    if (add_vertical_start and pass_num == 0) or (add_vertical_end and pass_num == passes_for_this_base - 1):
                        vertical_right = [right_point[0], right_point[1], right_point[2] + connection_height, f"connection_right_span{span_idx+1}"]
                        route_points.append(vertical_right)
                        route_tags.append(f"connection_span{span_idx+1}")
                        
                        # Return to R1
                        route_points.append([right_point[0], right_point[1], right_point[2], pass_tag])
                        route_tags.append(pass_tag)
                    
                    # L1
                    route_points.append([left_point[0], left_point[1], left_point[2], pass_tag])
                    route_tags.append(pass_tag)
                    
                    # L1_V (vertical connection at left point)
                    if (add_vertical_start and pass_num == 0) or (add_vertical_end and pass_num == passes_for_this_base - 1):
                        vertical_left = [left_point[0], left_point[1], left_point[2] + connection_height, f"connection_left_span{span_idx+1}"]
                        route_points.append(vertical_left)
                        route_tags.append(f"connection_span{span_idx+1}")
                        
                        # Return to L1
                        route_points.append([left_point[0], left_point[1], left_point[2], pass_tag])
                        route_tags.append(pass_tag)
                else:
                    # Odd passes: Left → Right with vertical connections
                    # L1
                    route_points.append([left_point[0], left_point[1], left_point[2], pass_tag])
                    route_tags.append(pass_tag)
                    
                    # L1_V (vertical connection at left point)
                    if (add_vertical_start and pass_num == 0) or (add_vertical_end and pass_num == passes_for_this_base - 1):
                        vertical_left = [left_point[0], left_point[1], left_point[2] + connection_height, f"connection_left_span{span_idx+1}"]
                        route_points.append(vertical_left)
                        route_tags.append(f"connection_span{span_idx+1}")
                        
                        # Return to L1
                        route_points.append([left_point[0], left_point[1], left_point[2], pass_tag])
                        route_tags.append(pass_tag)
                    
                    # R1
                    route_points.append([right_point[0], right_point[1], right_point[2], pass_tag])
                    route_tags.append(pass_tag)
                    
                    # R1_V (vertical connection at right point)
                    if (add_vertical_start and pass_num == 0) or (add_vertical_end and pass_num == passes_for_this_base - 1):
                        vertical_right = [right_point[0], right_point[1], right_point[2] + connection_height, f"connection_right_span{span_idx+1}"]
                        route_points.append(vertical_right)
                        route_tags.append(f"connection_span{span_idx+1}")
                        
                        # Return to R1
                        route_points.append([right_point[0], right_point[1], right_point[2], pass_tag])
                        route_tags.append(pass_tag)
        
        if route_points:
            total_passes = sum([
                (2 * num_passes) if (len(right_points) % 2 == 1 and i == len(right_points) // 2) else num_passes
                for i in range(max(len(right_points), len(left_points)))
            ])
            
            routes.append({
                'id': f"underdeck_span_{span_idx+1}_crossing",
                'points': route_points,
                'tags': route_tags,
                'num_passes': num_passes,
                'total_passes': total_passes,
                'connection_height': connection_height,
                'pattern': 'crossing'
            })
            
            debug_print(f"   ✅ Span {span_idx+1}: {len(route_points)} points, {len(right_points)} base pairs, "
                  f"{total_passes} total passes, crossing pattern, connection_height={connection_height}m")
    
    return routes


def _visualize_underdeck_routes(app, routes: List[Dict[str, Any]]):
    """Visualize underdeck routes in 3D viewer with color coding."""
    
    if not hasattr(app, 'visualizer') or not app.visualizer:
        debug_print("ℹ️  No visualizer available – skipping 3D preview")
        return
    
    vis = app.visualizer
    
    # Remove previous underdeck meshes
    removed_count = 0
    for name in list(vis.meshes.keys()):
        if name.startswith("underdeck_") or name.startswith("axial_"):
            try:
                vis._remove_mesh(name)
                removed_count += 1
            except Exception as e:
                debug_print(f"⚠️  Could not remove mesh {name}: {e}")
    
    if removed_count > 0:
        debug_print(f"🔄 Removed {removed_count} previous underdeck meshes")
    
    # Color schemes
    normal_base_color = [0.53, 0.81, 0.92]  # Light blue (skyblue)
    axial_base_color = [1.0, 0.71, 0.76]    # Light pink
    
    # Track span indices for color variation
    normal_span_count = 0
    axial_span_count = 0
    
    # Add new underdeck routes with appropriate colors
    for route in routes:
        route_id = route.get('id', 'underdeck_route')
        route_points = route.get('points', [])
        pattern = route.get('pattern', 'unknown')
        
        if not route_points:
            continue
            
        # Determine route type and assign color
        if 'axial' in route_id.lower() or pattern == 'axial_longitudinal':
            # Axial routes: Light pink with brightness variation
            base_color = axial_base_color.copy()
            brightness_factor = 1.0 + (axial_span_count * 0.15)  # Increase brightness per span
            color = [min(1.0, c * brightness_factor) for c in base_color]
            axial_span_count += 1
            route_type = "axial"
        else:
            # Normal underdeck routes: Light blue with brightness variation  
            base_color = normal_base_color.copy()
            brightness_factor = 1.0 + (normal_span_count * 0.15)  # Increase brightness per span
            color = [min(1.0, c * brightness_factor) for c in base_color]
            normal_span_count += 1
            route_type = "normal"
        
        # Extract just [x, y, z] for visualization
        viz_points = [[p[0], p[1], p[2]] for p in route_points]
        
        try:
            vis.add_polyline(
                route_id, 
                viz_points, 
                color=color,
                line_width=5,  # Slightly thicker for better visibility
                tube_radius=0
            )
            
            color_desc = f"{'bright ' if brightness_factor > 1.15 else ''}{'pink' if route_type == 'axial' else 'blue'}"
            debug_print(f"✅ Added {route_type} visualization: {route_id} ({len(viz_points)} points, {color_desc})")
            
        except Exception as e:
            debug_print(f"❌ Failed to add visualization {route_id}: {e}")
    
    debug_print(f"✅ Visualized {len(routes)} underdeck routes: {normal_span_count} normal (blue), {axial_span_count} axial (pink)")


def _apply_safety_checks_to_routes(routes: List[Dict[str, Any]], params: Dict[str, Any], 
                                 trajectory_samples: List, app=None) -> List[Dict[str, Any]]:
    """Apply safety checks to underdeck routes if enabled using EnhancedSafetyProcessor."""
    
    safety_check_underdeck = params.get('safety_check_underdeck', [[0], [0], [0]])
    
    # Check if any span has safety check enabled
    safety_enabled = False
    for span_safety in safety_check_underdeck:
        if isinstance(span_safety, list) and len(span_safety) > 0:
            if span_safety[0] == 1:
                safety_enabled = True
                break
    
    if not safety_enabled:
        debug_print("ℹ️  Safety check disabled for all underdeck spans")
        return routes
    
    debug_print(f"🛡️  Applying safety checks for underdeck routes...")
    
    # Get safety zones from app if available (using same logic as FlightPathConstructor)
    safety_zones = []
    safety_clearance = []
    safety_adjust = []
    takeoff_altitude = 0.0
    
    if app and hasattr(app, 'current_safety_zones') and app.current_safety_zones:
        debug_print(f"   📍 Processing {len(app.current_safety_zones)} safety zones for underdeck routes")
        
        # Convert safety zones from WGS84 to project coordinates (same as FlightPathConstructor)
        for zone_idx, zone in enumerate(app.current_safety_zones):
            if isinstance(zone, dict) and 'points' in zone and len(zone['points']) >= 3:
                zone_points_project = []
                for point in zone['points']:
                    # Points are stored as [lat, lng] in WGS84
                    lat, lng = point[0], point[1]
                    # Use same transformation logic as FlightPathConstructor
                    if hasattr(app, '_last_transform_func') and app._last_transform_func:
                        x, y, _ = app._last_transform_func(lat, lng, 0)
                    elif hasattr(app, 'current_context') and app.current_context:
                        # Fall back to project context CRS
                        x, y, _ = app.current_context.wgs84_to_project(lng, lat, 0)
                    else:
                        # Absolute fallback – leave in degrees so that we do not crash
                        x, y = lng, lat
                        debug_print(f"   ⚠️  [UNDERDECK SAFETY] No context available for coordinate conversion! Using WGS84 coordinates.")
                    zone_points_project.append([x, y])
                    
                    # Debug: print the first few conversions for the very first zone only
                    if zone_idx == 0 and len(zone_points_project) <= 3:
                        debug_print(f"   🔄 Zone {zone_idx} Point WGS84: ({lat:.6f}, {lng:.6f}) -> Project: ({x:.2f}, {y:.2f})")
                
                safety_zones.append(zone_points_project)
                debug_print(f"   ✅ Converted safety zone {zone_idx+1}: {len(zone_points_project)} points")
        
        debug_print(f"   📍 Successfully converted {len(safety_zones)} safety zones to project coordinates")
        
        # Get safety parameters from parsed data
        if hasattr(app, 'parsed_data'):
            flight_data = app.parsed_data.get('flight_routes', {})
            safety_clearance = flight_data.get('safety_zones_clearance', [[20, 50]] * len(safety_zones))
            safety_adjust = flight_data.get('safety_zones_clearance_adjust', [[10]] * len(safety_zones))
            takeoff_altitude = flight_data.get('takeoff_altitude', 0.0)
            debug_print(f"   🔧 Safety parameters: clearance={len(safety_clearance)} zones, adjust={len(safety_adjust)} zones")
            
            # Validate safety zone parameters before processing
            if hasattr(app, '_validate_safety_zone_parameters'):
                app._validate_safety_zone_parameters()
    else:
        debug_print("   ⚠️  No safety zones available - skipping safety processing")
        return routes
    
    # Apply safety processing to each route
    processed_routes = []
    for route in routes:
        route_points = route.get('points', [])
        if not route_points:
            processed_routes.append(route)
            continue
            
        # Extract span index from route ID
        span_idx = 0
        if 'span_' in route.get('id', ''):
            try:
                span_idx = int(route['id'].split('span_')[1].split('_')[0]) - 1
            except (IndexError, ValueError):
                span_idx = 0
        
        # Check if safety is enabled for this span
        if (span_idx < len(safety_check_underdeck) and 
            len(safety_check_underdeck[span_idx]) > 0 and 
            safety_check_underdeck[span_idx][0] == 1):
            
            debug_print(f"   🛡️  Processing safety for span {span_idx+1} - {len(route_points)} points")
            
            # Extract just [x, y, z] coordinates for safety processing
            waypoints = [[p[0], p[1], p[2]] for p in route_points]
            
            try:
                # Apply EnhancedSafetyProcessor
                safety_processor = EnhancedSafetyProcessor(
                    waypoints,
                    safety_zones,
                    safety_clearance,
                    takeoff_altitude
                )
                
                                # Process the route with safety adjustments
                # Get min_angle_change from GUI
                min_angle_change = 15  # Default fallback
                if hasattr(app, 'get_min_angle_change'):
                    min_angle_change = app.get_min_angle_change()
                
                processed_waypoints = safety_processor.process_route(
                    safety_adjust, 
                    resample_interval=0.5,
                    min_angle_change=min_angle_change
                )
                
                # Reconstruct route points with original tags (if any)
                processed_points = []
                original_tags = route.get('tags', [])
                
                for i, waypoint in enumerate(processed_waypoints):
                    if len(waypoint) >= 3:
                        # Preserve original tag if available, otherwise use route ID
                        tag = original_tags[i] if i < len(original_tags) else route.get('id', 'underdeck_safe')
                        processed_points.append([waypoint[0], waypoint[1], waypoint[2], tag])
                    else:
                        debug_print(f"   ⚠️  Invalid waypoint format: {waypoint}")
                
                # Create processed route
                processed_route = route.copy()
                processed_route['points'] = processed_points
                processed_route['safety_processed'] = True
                processed_route['original_points'] = len(route_points)
                processed_route['processed_points'] = len(processed_points)
                
                processed_routes.append(processed_route)
                
                debug_print(f"   ✅ Safety processed span {span_idx+1}: {len(route_points)} → {len(processed_points)} points")
                
            except Exception as e:
                error_debug_print(f"   ❌ Safety processing failed for span {span_idx+1}: {e}")
                # Fall back to original route
                processed_routes.append(route)
        else:
            debug_print(f"   ℹ️  Safety check disabled for span {span_idx+1}")
            processed_routes.append(route)
    
    return processed_routes


def _create_combined_underdeck_route(routes: List[Dict[str, Any]], params: Dict[str, Any]) -> Dict[str, Any]:
    """Create a single combined underdeck route from all span routes when underdeck_split = 0."""
    
    if not routes:
        return {}
    
    debug_print(f"🔗 Combining {len(routes)} underdeck routes into single route...")
    
    combined_points = []
    combined_tags = []
    total_spans = 0
    total_passes = 0
    
    # Combine all route points in sequence
    for route in routes:
        route_points = route.get('points', [])
        route_tags = route.get('tags', [])
        
        if route_points:
            combined_points.extend(route_points)
            combined_tags.extend(route_tags)
            total_spans += 1
            total_passes += route.get('total_passes', route.get('num_passes', 1))
    
    if not combined_points:
        return {}
    
    # Create combined route metadata
    combined_route = {
        'id': 'underdeck_combined_all_spans',
        'points': combined_points,
        'tags': combined_tags,
        'num_passes': params.get('num_passes', 2),
        'total_passes': total_passes,
        'connection_height': params.get('connection_height', 0),
        'pattern': 'combined_crossing',
        'spans_combined': total_spans,
        'split': False  # Indicates this is a non-split route
    }
    
    debug_print(f"   ✅ Combined route: {len(combined_points)} points from {total_spans} spans")
    debug_print(f"   📊 Total passes: {total_passes}, Connection height: {params.get('connection_height', 0)}m")
    
    return combined_route


def _create_axial_underdeck_routes(base_points: List[List], normals: List[np.ndarray], 
                                  offset_points_underdeck: List[List], adjusted_height_offsets: List[List],
                                  angles_zones: List[float], params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Create axial underdeck routes that follow girder lines (longitudinal inspection)."""
    
    n_girders = params.get('n_girders', 5)
    bridge_width = params.get('bridge_width', 13.29)
    connection_height = params.get('connection_height', 20.0)
    
    debug_print(f"🔧 Creating axial underdeck routes with {n_girders} girders")
    
    # Step 1: Compute girder offsets (sorted from nearest to farthest from centerline)
    girder_offsets = _compute_girder_offsets(bridge_width, n_girders)
    girder_offsets = sorted(girder_offsets, reverse=True)  # Largest to smallest
    debug_print(f"   📏 Girder offsets: {girder_offsets}")
    
    axial_routes = []
    
    # Step 2: Generate axial routes for each span
    for section_index, section_base_points in enumerate(base_points):
        if not section_base_points:
            continue
            
        debug_print(f"   🏗️  Processing axial routes for span {section_index + 1}")
        
        # Start section with connection to first offset point (entry point)
        section_points = []
        section_tags = []
        
        if section_index < len(offset_points_underdeck) and offset_points_underdeck[section_index]:
            first_offset_point = offset_points_underdeck[section_index][0]
            section_points.extend([
                first_offset_point,
                [first_offset_point[0], first_offset_point[1], first_offset_point[2] + connection_height],
                first_offset_point
            ])
            section_tags.extend([
                f"axial_span{section_index+1}_entry",
                f"axial_span{section_index+1}_entry_climb", 
                f"axial_span{section_index+1}_entry"
            ])
        
        # Step 3: Process each girder offset (create longitudinal lines)
        for offset_index, offset in enumerate(girder_offsets):
            girder_tag = f"axial_span{section_index+1}_girder{offset_index+1}"
            
            # Forward pass along this girder line
            forward_points = []
            for i, base_point in enumerate(section_base_points):
                normal = normals[i % len(normals)] if normals else np.array([1, 0, 0])
                angle = angles_zones[section_index] if section_index < len(angles_zones) else 0.0
                height_offset = adjusted_height_offsets[section_index][i % len(adjusted_height_offsets[section_index])]
                
                # Calculate girder point using original logic
                adjusted_point = _calculate_adjusted_point(
                    np.array(base_point), offset, normal, height_offset, angle
                )
                forward_points.append(adjusted_point.tolist())
            
            # Add connection flights at start and end of first and last girders
            if offset_index == 0:  # First girder - add connection at end
                if section_index < len(offset_points_underdeck) and len(offset_points_underdeck[section_index]) >= 2:
                    last_right_point = offset_points_underdeck[section_index][-2]  # Second to last (right)
                    forward_points.extend([
                        last_right_point,
                        [last_right_point[0], last_right_point[1], last_right_point[2] + connection_height]
                    ])
            
            elif offset_index == len(girder_offsets) - 1:  # Last girder - add connection at end
                if section_index < len(offset_points_underdeck) and len(offset_points_underdeck[section_index]) >= 1:
                    last_left_point = offset_points_underdeck[section_index][-1]  # Last (left)
                    forward_points.extend([
                        last_left_point,
                        [last_left_point[0], last_left_point[1], last_left_point[2] + connection_height]
                    ])
            
            # Add forward points
            section_points.extend(forward_points)
            section_tags.extend([girder_tag] * len(forward_points))
            
            # Add backward points (return along same girder)
            backward_points = forward_points[::-1]
            section_points.extend(backward_points)
            section_tags.extend([f"{girder_tag}_return"] * len(backward_points))
        
        # Finish section with connection to last offset point (exit point)
        if section_index < len(offset_points_underdeck) and len(offset_points_underdeck[section_index]) >= 2:
            last_offset_point = offset_points_underdeck[section_index][1]  # Second point (left)
            section_points.extend([
                last_offset_point,
                [last_offset_point[0], last_offset_point[1], last_offset_point[2] + connection_height],
                last_offset_point
            ])
            section_tags.extend([
                f"axial_span{section_index+1}_exit",
                f"axial_span{section_index+1}_exit_climb",
                f"axial_span{section_index+1}_exit"
            ])
        
        # Create route for this span
        if section_points:
            axial_route = {
                'id': f"axial_underdeck_span_{section_index+1}",
                'points': section_points,
                'tags': section_tags,
                'pattern': 'axial_longitudinal',
                'n_girders': n_girders,
                'girder_offsets': girder_offsets,
                'connection_height': connection_height
            }
            
            axial_routes.append(axial_route)
            debug_print(f"   ✅ Axial span {section_index+1}: {len(section_points)} points, {n_girders} girders")
    
    return axial_routes
def _derive_sections_and_angles_from_pillars(trajectory_samples, app=None):
    """
    Minimal + robust:
      - trajectory_samples: Nx3 in project/local metric coords
      - pillars: use app.pillars_project_xy if available; else project map pillars once
      - sections = [start->P1, P1->P2, ..., Plast->end]
      - angles  = per-section defaults from pillar skew vs deck normal (light smoothing)
    """
    import numpy as np
    traj = np.asarray(trajectory_samples, dtype=float)
    if traj.shape[0] < 2:
        debug_print("   ⚠️ No trajectory to split; returning single section.")
        return [], []

    # --- helpers --------------------------------------------------------------
    def _canon(a_deg, cap=85.0):
        # clamp to [-90,90] and cap extremes for stability
        a = ((float(a_deg) + 180.0) % 360.0) - 180.0
        if a > 90.0: a -= 180.0
        if a < -90.0: a += 180.0
        if cap is not None:
            a = max(-cap, min(cap, a))
        return a

    def _poly_len(xy):
        d = np.linalg.norm(xy[1:] - xy[:-1], axis=1)
        return float(np.sum(d))

    def _project_point_to_chainage(pt_xy, traj_xy):
        best_d = 1e30
        best_s = 0.0
        acc = 0.0
        for i in range(1, traj_xy.shape[0]):
            a = traj_xy[i-1]; b = traj_xy[i]
            ab = b - a
            L2 = float(np.dot(ab, ab))
            if L2 <= 0:
                continue
            t = float(np.clip(np.dot(pt_xy - a, ab) / L2, 0.0, 1.0))
            p = a + t * ab
            d = float(np.linalg.norm(pt_xy - p))
            if d < best_d:
                best_d = d
                best_s  = acc + t * float(np.linalg.norm(ab))
            acc += float(np.linalg.norm(ab))
        return best_s

    def _tangent_at(pt_xy, traj_xy):
        # tangent of closest segment to pt_xy
        best_d = 1e30
        best_v = np.array([1.0, 0.0], float)
        for i in range(1, traj_xy.shape[0]):
            a = traj_xy[i-1]; b = traj_xy[i]
            v = b - a
            L = np.linalg.norm(v)
            if L <= 0: 
                continue
            # distance to segment
            L2 = float(np.dot(v, v))
            t = float(np.clip(np.dot(pt_xy - a, v) / L2, 0.0, 1.0))
            p = a + t * v
            d = float(np.linalg.norm(pt_xy - p))
            if d < best_d:
                best_d = d
                best_v = v / L
        return best_v

    def _angle_vs_normal(pdir, traj_tan):
        n = np.array([-traj_tan[1], traj_tan[0]], float)  # deck normal
        # angle between pillar direction and deck normal
        dot = float(np.clip(np.dot(n, pdir), -1.0, 1.0))
        cross_z = float(n[0]*pdir[1] - n[1]*pdir[0])
        ang = np.degrees(np.arctan2(cross_z, dot))
        return _canon(ang)

    # --- pillars in PROJECT coords -------------------------------------------
    # Best source: already-projected by the 3D builder
    pillars_xy = []
    if app is not None and getattr(app, "pillars_project_xy", None):
        pillars_xy = [tuple(map(float, p)) for p in app.pillars_project_xy]

    # Fallback: project WGS84 map pillars once using the same transform the app uses
    elif app is not None and getattr(app, "current_pillars", None):
        def _proj(lat, lon):
            try:
                if getattr(app, "_last_transform_func", None):
                    x, y, _ = app._last_transform_func(float(lat), float(lon), 0.0)  # your app uses (lat,lon)
                    return float(x), float(y)
                if getattr(app, "current_context", None):
                    x, y, _ = app.current_context.wgs84_to_project(float(lon), float(lat), 0.0)  # (lon,lat)
                    return float(x), float(y)
            except Exception:
                pass
            # conservative fallback (unlikely used)
            return float(lon), float(lat)

        for p in app.current_pillars:
            lat = p.get("lat"); lon = p.get("lon")
            if lat is None or lon is None:
                continue
            pillars_xy.append(_proj(lat, lon))

    if not pillars_xy:
        # no pillars → one section (whole length) and neutral angle
        L = _poly_len(traj[:, :2])
        return [L], [0.0]

    # --- build midline centers from pillar pairs -----------------------------
    # Pair in order: (0,1), (2,3), ...
    xy = np.asarray(pillars_xy, float)
    centers = []
    dirs    = []
    i = 0
    while i < xy.shape[0]:
        if i+1 < xy.shape[0]:
            a = xy[i]; b = xy[i+1]
            v = b - a
            L = np.linalg.norm(v)
            if L > 1e-9:
                centers.append(0.5*(a+b))
                dirs.append(v / L)
            else:
                centers.append(a.copy())
                dirs.append(None)
            i += 2
        else:
            # odd single → treat as center with unknown dir
            centers.append(xy[i].copy())
            dirs.append(None)
            i += 1

    centers = np.asarray(centers, float)

    # --- sort centers by chainage along trajectory ---------------------------
    traj_xy = traj[:, :2]
    chain = np.array([_project_point_to_chainage(c, traj_xy) for c in centers], float)
    order = np.argsort(chain)
    centers = centers[order]
    dirs    = [dirs[k] for k in order]
    chain   = chain[order]

    # --- section lengths: start->P1, P1->P2, ..., Plast->end -----------------
    total_len = _poly_len(traj_xy)
    sections = []
    prev_s = 0.0
    for s in chain:
        if s > prev_s:
            sections.append(s - prev_s)
        prev_s = max(prev_s, s)
    if total_len > prev_s:
        sections.append(total_len - prev_s)

    # --- default angles per section (light smoothing) ------------------------
    # angle at each center; then spread to sections as [a0, (a0+a1)/2, ..., ak]
    pillar_angles = []
    for c, d in zip(centers, dirs):
        tan = _tangent_at(c, traj_xy)
        if d is None:
            pillar_angles.append(0.0)
        else:
            pillar_angles.append(_angle_vs_normal(d, tan))

    if len(pillar_angles) == 0:
        default_angles = [0.0] * max(1, len(sections))
    elif len(pillar_angles) == 1:
        default_angles = [pillar_angles[0]] * max(1, len(sections))
    else:
        default_angles = [pillar_angles[0]]
        for i2 in range(len(pillar_angles)-1):
            default_angles.append(_canon(0.5*(pillar_angles[i2] + pillar_angles[i2+1])))
        # pad/truncate to sections length
        if len(default_angles) < len(sections):
            default_angles += [default_angles[-1]] * (len(sections)-len(default_angles))
        elif len(default_angles) > len(sections):
            default_angles = default_angles[:len(sections)]

    debug_print(f"   📏 Sections: {len(sections)} | lengths(m) {[round(x,1) for x in sections]}")
    debug_print(f"   🧭 Default angles (deg): {[round(a,1) for a in default_angles]}")
    return sections, default_angles

def _calculate_pillar_distances(trajectory_samples: List, num_spans: int, app=None) -> List[float]:
    """
    Calculate section lengths using the actual centerpoints of pillar *pairs*.
    Sections are: [start -> P1_center], [P1_center -> P2_center], ..., [Plast_center -> end].
    Forgiving behavior:
      - If pillars are provided as single points, we use that point.
      - If fewer (or more) sections than user-configured arrays, we DO NOT pad/truncate here.
      - If no pillars: single section = full trajectory length.
    """
    traj = np.array(trajectory_samples, dtype=float)
    if len(traj) < 2:
        return []

    # helper: total trajectory length
    def _polyline_length(poly):
        return float(sum(np.linalg.norm(poly[i] - poly[i-1]) for i in range(1, len(poly))))

    total_len = _polyline_length(traj)

    # ---- extract pillar centerpoints (projected XY) ----
    pillar_centers_xy: List[np.ndarray] = []

    def _project_wgs84_guess(lat, lon) -> Tuple[float, float]:
        """
        Try (lon,lat) and (lat,lon); pick the one whose XY is closer to the trajectory.
        This makes us robust to mixed argument orders.
        """
        def _closest_dist(pt):
            # distance from pt to polyline
            dmin = float("inf")
            for i in range(1, len(traj)):
                a = traj[i-1][:2]; b = traj[i][:2]
                ab = b - a
                if np.allclose(ab, 0): 
                    d = np.linalg.norm(pt - a)
                else:
                    t = np.clip(np.dot(pt - a, ab) / np.dot(ab, ab), 0.0, 1.0)
                    p = a + t * ab
                    d = np.linalg.norm(pt - p)
                dmin = min(dmin, d)
            return dmin

        # try both orders (lon,lat) vs (lat,lon)
        if hasattr(app, 'current_context') and app.current_context:
            x1, y1, _ = app.current_context.wgs84_to_project(lon, lat, 0.0)  # (lon, lat)
            x2, y2, _ = app.current_context.wgs84_to_project(lat, lon, 0.0)  # (lat, lon) fallback
        elif hasattr(app, '_last_transform_func') and app._last_transform_func:
            x1, y1, _ = app._last_transform_func(lat, lon, 0.0)               # legacy path
            x2, y2, _ = app._last_transform_func(lon, lat, 0.0)               # swapped fallback
        else:
            # no context; just return as-is (best-effort)
            return float(lon), float(lat)

        cand1 = np.array([x1, y1], dtype=float)
        cand2 = np.array([x2, y2], dtype=float)
        return (cand1 if _closest_dist(cand1) <= _closest_dist(cand2) else cand2).tolist()

    def _as_xy_points(pillar_entry) -> List[np.ndarray]:
        """
        Accept many shapes:
          - {'points': [[lat, lon], [lat, lon]]}
          - {'lat':..,'lon':..} or {'x':..,'y':..}
          - {'lat1':..,'lon1':..,'lat2':..,'lon2':..}
          - [[lat, lon], [lat, lon]]   (list)
        Returns a list of 1 or 2 projected XY points.
        """
        pts: List[np.ndarray] = []
        # dict cases
        if isinstance(pillar_entry, dict):
            if 'x' in pillar_entry and 'y' in pillar_entry:
                pts.append(np.array([pillar_entry['x'], pillar_entry['y']], dtype=float))
            elif 'points' in pillar_entry and isinstance(pillar_entry['points'], (list, tuple)) and len(pillar_entry['points']) >= 2:
                a, b = pillar_entry['points'][0], pillar_entry['points'][1]
                ax, ay = _project_wgs84_guess(a[0], a[1])
                bx, by = _project_wgs84_guess(b[0], b[1])
                pts.extend([np.array([ax, ay]), np.array([bx, by])])
            elif {'lat','lon'} <= set(pillar_entry.keys()):
                x, y = _project_wgs84_guess(pillar_entry['lat'], pillar_entry['lon'])
                pts.append(np.array([x, y]))
            elif {'lat1','lon1','lat2','lon2'} <= set(pillar_entry.keys()):
                ax, ay = _project_wgs84_guess(pillar_entry['lat1'], pillar_entry['lon1'])
                bx, by = _project_wgs84_guess(pillar_entry['lat2'], pillar_entry['lon2'])
                pts.extend([np.array([ax, ay]), np.array([bx, by])])
        # list-of-points case
        elif (isinstance(pillar_entry, (list, tuple)) and len(pillar_entry) >= 2 
              and all(isinstance(p, (list, tuple)) and len(p) >= 2 for p in pillar_entry[:2])):
            a, b = pillar_entry[0], pillar_entry[1]
            ax, ay = _project_wgs84_guess(a[0], a[1])
            bx, by = _project_wgs84_guess(b[0], b[1])
            pts.extend([np.array([ax, ay]), np.array([bx, by])])
        return pts

    # gather centers
    if app and getattr(app, 'current_pillars', None):
        for raw in app.current_pillars:
            pts = _as_xy_points(raw)
            if len(pts) >= 2:
                center = 0.5 * (pts[0] + pts[1])
                pillar_centers_xy.append(center)
            elif len(pts) == 1:
                pillar_centers_xy.append(pts[0])

    if not pillar_centers_xy:
        # no pillars: one section = full length
        debug_print("   No pillar pairs/points found; treating whole bridge as one section.")
        return [total_len]

    # ---- distance along trajectory to each center ----
    centers_s = []
    for center in pillar_centers_xy:
        min_d = float('inf')
        s_at_min = 0.0
        acc = 0.0
        for i in range(1, len(traj)):
            a = traj[i-1]; b = traj[i]
            ab = b - a
            seg_len = float(np.linalg.norm(ab))
            if seg_len < 1e-9:
                continue
            t = np.dot(center - a[:2], ab[:2]) / np.dot(ab[:2], ab[:2]) if np.dot(ab[:2], ab[:2]) > 0 else 0.0
            t = max(0.0, min(1.0, t))
            p = a[:2] + t * ab[:2]
            d = float(np.linalg.norm(center - p))
            if d < min_d:
                min_d = d
                s_at_min = acc + t * seg_len
            acc += seg_len
        centers_s.append(s_at_min)

    # dedupe & sort
    centers_s = sorted(s for i, s in enumerate(sorted(centers_s)) 
                       if i == 0 or abs(s - sorted(centers_s)[i-1]) > 0.5)

    # ---- sections from start->first->...->end ----
    sections = []
    prev_s = 0.0
    for s in centers_s:
        if s > prev_s:
            sections.append(s - prev_s)
        prev_s = max(prev_s, s)
    if total_len > prev_s:
        sections.append(total_len - prev_s)

    # NOTE: we deliberately do NOT pad or truncate to num_spans here.
    debug_print(f"   Pillar-based sections: {len(sections)} (no padding). Lengths: {[round(x,1) for x in sections]}")
    if len(sections) != num_spans:
        debug_print(f"   ⚠️ Sections ({len(sections)}) ≠ configured spans ({num_spans}). Extra/missing spans will be skipped downstream.")
    return sections

def _resolve_span_angles(default_angles: List[float], custom_angles: List) -> List[float]:
    """
    Resolve angles for each span.
    Rules:
      - If custom angle is string '00' → special pillar-parallel mode handles base points; angle here = 0.0
      - If custom angle is string 'parallel' → use pillar-derived default
      - If numeric custom angle → use it
      - Else → use pillar-derived default
    """
    out: list[float] = []
    for i in range(len(default_angles)):
        # Attempt to get custom angle for this span
        ca = None
        if custom_angles and i < len(custom_angles):
            ca = custom_angles[i]
        # If user requests pillar-parallel override '00', return 0 here
        if isinstance(ca, str) and ca.strip().lower().replace('°','') == '00':
            out.append(0.0)
        # If user requests 'parallel', use pillar-derived default
        if isinstance(ca, str) and ca.lower() == 'parallel':
            out.append(default_angles[i])
        # If numeric custom angle, use it
        elif isinstance(ca, (int, float)):
            out.append(float(ca))
        # Otherwise, default to pillar-based angle
        else:
            out.append(default_angles[i])
    return out

def _compute_girder_offsets(bridge_width: float, n_girders: int) -> List[float]:
    """Compute girder offset positions from bridge centerline (replicates original logic)."""
    
    if n_girders <= 1:
        return [0.0]  # Single girder at center
    
    # Calculate spacing between girders
    girder_spacing = bridge_width / (n_girders + 1)
    
    # Generate offsets symmetrically around centerline
    offsets = []
    for i in range(n_girders):
        # Position girders from -bridge_width/2 to +bridge_width/2
        offset = -bridge_width/2 + (i + 1) * girder_spacing
        offsets.append(offset)
    
    debug_print(f"   📐 Computed {n_girders} girder offsets with {girder_spacing:.2f}m spacing")

    return offsets


def _fix_connection_speed_tags(routes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Fix connection speed tags to ensure consistent vertical flight speeds.

    When a connection tag is found on a point, this function overwrites the tag
    of only the immediate previous point with the same connection tag, ensuring
    consistent flight speed during vertical ascents and descents.

    Parameters
    ----------
    routes : List[Dict[str, Any]]
        List of route dictionaries containing 'points' with [x, y, z, tag] format

    Returns
    -------
    List[Dict[str, Any]]
        Routes with corrected connection speed tags
    """
    debug_print("🔧 Fixing connection speed tags for consistent vertical flight speeds")

    for route_idx, route in enumerate(routes):
        if 'points' not in route:
            continue

        points = route['points']
        if len(points) < 2:
            continue

        # Process points to fix connection tags
        for i in range(1, len(points)):  # Start from index 1 to ensure there's a previous point
            point = points[i]
            if len(point) < 4:
                continue

            tag = point[3]  # Tag is at index 3

            # Check if this is a connection tag
            if 'connection' in tag:
                # Only change the immediate previous point's tag
                prev_point = points[i - 1]
                if len(prev_point) >= 4:
                    prev_point[3] = tag

        debug_print(f"   ✅ Fixed connection tags for route {route_idx + 1}")

    return routes
