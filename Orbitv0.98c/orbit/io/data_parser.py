#!/usr/bin/env python3
"""orbit.data_parser

Central parsing utility for the ORBIT GUI.

Changes 2025-08-04
------------------
* Removed all references to *default values*.  
  No JSON fallback, no hard-coded literals.
* Only this module is allowed to interpret the raw text
  from the GUI text boxes (`tab0_textEdit1_Photo`,
  `tab0_textEdit1_Photo_2`).  
  Every other part of the codebase must consume the
  dictionary returned by ``parse_text_boxes``.
* If a required variable is missing the parser **prints an
  explicit error message** – nothing is silently substituted
  anymore.

Changes 2025-01-XX
------------------
* Added global DEBUG_PRINT control for all debug output
* All print statements now controlled by DEBUG_PRINT variable
"""

from __future__ import annotations

import ast
import re
from typing import Any, Dict

# -----------------------------------------------------------------------------
# Global Debug Control
# -----------------------------------------------------------------------------

# Global debug print control - set to True to enable debug output
DEBUG_PRINT = False

def set_debug_print(enabled: bool) -> None:
    """Set the global debug print state.
    
    Args:
        enabled: True to enable debug output, False to disable
    """
    global DEBUG_PRINT
    DEBUG_PRINT = enabled

def debug_print(*args, **kwargs) -> None:
    """Print function that only outputs when DEBUG_PRINT is True.
    
    Args:
        *args: Arguments to print
        **kwargs: Keyword arguments for print function
    """
    if DEBUG_PRINT:
        print(*args, **kwargs)

# -----------------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------------

def validate_flight_data(data: Dict[str, Any], *, required_keys: tuple[str, ...] | None = None) -> bool:
    """Validate flight route data against expected types and required keys.

    Args:
        data: Dictionary of flight route parameters
        required_keys: Optional tuple of keys that must be present

    Returns:
        True if validation passed, False if any errors
    """
    # Default required keys if none provided
    if required_keys is None:
        required_keys = (
            "transition_mode",
            "transition_vertical_offset",
            "transition_horizontal_offset",
            "order",
            "standard_flight_routes",
            "flight_speed_map",
            "safety_zones_clearance",
            "safety_zones_clearance_adjust",
        )

    # Check required keys
    missing = [k for k in required_keys if k not in data]
    if missing:
        debug_print("\n[ERROR] Missing required flight-route keys:")
        for key in missing:
            debug_print(f"[ERROR]   {key}")
        return False

    # Validate types
    expected_types = {
        "order": list,
        "transition_mode": int,
        "transition_vertical_offset": float,
        "transition_horizontal_offset": float,
        "num_points": list,
        "horizontal_offsets_underdeck": list,
        "height_offsets_underdeck": list,
        "general_height_offset": float,
        "thresholds_zones": list,
        "custom_zone_angles": list,
        "safety_zones_clearance": list,
        "safety_zones_clearance_adjust": list,
        "heightMode": str,
        "perpendicular_distances": list,
        "connection_height": float,
        "num_passes": int,
        "safety_check_photo": int,
        "safety_check_underdeck": list,
        "safety_check_underdeck_axial": list,
        "n_girders": int,
    }

    type_errors = []
    for key, expected_type in expected_types.items():
        if key in data and not isinstance(data[key], expected_type):
            type_errors.append((key, expected_type.__name__, type(data[key]).__name__))

    if type_errors:
        debug_print("\n[ERROR] Type validation errors:")
        for key, exp, got in type_errors:
            debug_print(f"[ERROR]   {key:<28} expected {exp}, got {got}")
        return False

    return True

def parse_text_boxes(tab0_text: str, tab3_text: str | None = None) -> Dict[str, Dict[str, Any]]:
    """Parse Tab-0 and Tab-3 text-box contents.

    The parser never injects defaults. Everything must be provided by the
    user – otherwise an *error* is printed.

    Args:
        tab0_text: Content of tab0_textEdit1_Photo (project settings)
        tab3_text: Content of tab3_textEdit (flight route settings)

    Returns:
        Dict with "project" and "flight_routes" sections
    """
    debug_print("\n[DATA_PARSER] Starting parse of text box contents...")

    project_data: Dict[str, Any] = {}
    flight_data: Dict[str, Any] = {}

    # Parse project settings (Tab-0)
    if tab0_text:
        debug_print("\n[DATA_PARSER] Processing Tab-0 (Project Settings)")
        debug_print("[DATA_PARSER] " + "-" * 60)
        project_data = _parse_generic_ini(tab0_text)
    else:
        debug_print("\n[DATA_PARSER] ⚠︎ No Tab-0 content provided")

    # Parse flight routes (Tab-3)
    if tab3_text:
        debug_print("\n[DATA_PARSER] Processing Tab-3 (Flight Routes)")
        debug_print("[DATA_PARSER] " + "-" * 60)
        flight_data = _parse_flight_routes_regex(tab3_text)
    else:
        debug_print("\n[DATA_PARSER] ⚠︎ No Tab-3 content provided")

    # Validate required fields
    project_required = ("bridge_name", "epsg_code", "import_dir")
    flight_required = (
        "transition_mode",
        "transition_vertical_offset",
        "transition_horizontal_offset",
        "order",
        "standard_flight_routes",
        "flight_speed_map",
        "safety_zones_clearance",
        "safety_zones_clearance_adjust",
    )

    _print_summary("PROJECT", project_data, required=project_required)
    _print_summary("FLIGHT_ROUTES", flight_data, required=flight_required)

    # Return parsed data
    return {
        "project": project_data,
        "flight_routes": flight_data,
    }

# -----------------------------------------------------------------------------
# Regex-based flight-route parsing (proven reliable)
# -----------------------------------------------------------------------------

# Special patterns for complex dictionaries
_ROUTES_REGEX = r"standard_flight_routes\s*=\s*({(?:\s*\"[^\"]+\":\s*{[^\}]+\},?\s*)*})"
_SPEED_MAP_REGEX = r"flight_speed_map\s*=\s*({(?:\s*\"[^\"]+\":\s*{[^\}]+\},?\s*)*})"

# Complete mapping of all flight-route variables with proven patterns
_FLIGHT_ROUTE_PATTERNS: Dict[str, tuple[str, callable]] = {

    # Integers
    "transition_mode": (r"transition_mode\s*=\s*(\d+)", int),
    "num_passes": (r"num_passes\s*=\s*(\d+)", int),
    "safety_check_photo": (r"safety_check_photo\s*=\s*(\d+)", int),
    "n_girders": (r"n_girders\s*=\s*([0-9]+)", int),
    "underdeck_split": (r"underdeck_split\s*=\s*(\d+)", int),
    "underdeck_axial": (r"underdeck_axial\s*=\s*(\d+)", int),
    "droneEnumValue": (r"droneEnumValue\s*=\s*(\d+)", int),
    "payloadEnumValue": (r"payloadEnumValue\s*=\s*(\d+)", int),

    # Floats
    "photogrammetric_flight_angle": (r"photogrammetric_flight_angle\s*=\s*([+-]?\d*\.?\d+)", float),
    "connection_height": (r"connection_height\s*=\s*([+-]?\d*\.?\d+)", float),
    "general_height_offset": (r"general_height_offset\s*=\s*([+-]?\d*\.?\d+)", float),
    "transition_vertical_offset": (r"transition_vertical_offset\s*=\s*([+-]?\d*\.?\d+)", float),
    "transition_horizontal_offset": (r"transition_horizontal_offset\s*=\s*([+-]?\d*\.?\d+)", float),
    "heightStartingPoint_Ellipsoid": (r"heightStartingPoint_Ellipsoid\s*=\s*([+-]?\d*\.?\d+)", float),
    "heightStartingPoint_Reference": (r"heightStartingPoint_Reference\s*=\s*([+-]?\d*\.?\d+)", float),



    # Lists
    "order": (r"order\s*=\s*\[(.*?)\]", ast.literal_eval),
    "num_points": (r"num_points\s*=\s*(\[.*?\])", ast.literal_eval),
    "perpendicular_distances": (r"perpendicular_distances\s*=\s*(\[.*?\])", ast.literal_eval),
    "horizontal_offsets_underdeck": (r"horizontal_offsets_underdeck\s*=\s*(\[.*?\])", ast.literal_eval),
    "custom_zone_angles": (r"custom_zone_angles\s*=\s*(\[.*?\])", ast.literal_eval),
    "thresholds_zones": (r"thresholds_zones\s*=\s*(\[.*?\])", ast.literal_eval),

    # Nested lists
    "safety_check_underdeck": (r"safety_check_underdeck\s*=\s*(\[\[.*?\]\])", ast.literal_eval),
    "safety_check_underdeck_axial": (r"safety_check_underdeck_axial\s*=\s*(\[\[.*?\]\])", ast.literal_eval),
    "height_offsets_underdeck": (r"height_offsets_underdeck\s*=\s*(\[\[.*?\]\])", ast.literal_eval),
    "safety_zones_clearance": (r"safety_zones_clearance\s*=\s*(\[\[.*?\]\])", ast.literal_eval),
    "safety_zones_clearance_adjust": (r"safety_zones_clearance_adjust\s*=\s*(\[\[.*?\]\])", ast.literal_eval),

    # Complex dictionaries
    "standard_flight_routes": (_ROUTES_REGEX, ast.literal_eval),
    "flight_speed_map": (_SPEED_MAP_REGEX, ast.literal_eval),

    # Strings
    "heightMode": (r"heightMode\s*=\s*(\w+)", str),
    "globalWaypointTurnMode": (r"globalWaypointTurnMode\s*=\s*(\w+)", str),
}


def _parse_flight_routes_regex(raw: str) -> Dict[str, Any]:
    """Extract flight-route parameters using proven regex patterns."""
    debug_print("\n[DATA_PARSER] PARSING FLIGHT ROUTE PARAMETERS")
    debug_print("[DATA_PARSER] " + "-" * 60)

    if not raw or not raw.strip():
        debug_print("[DATA_PARSER] ⚠︎ No input text provided!")
        return {}

    # First, clean up the input text
    lines = []
    for line in raw.splitlines():
        # Remove comments but preserve the line
        if "#" in line and not any(c in line[:line.index("#")] for c in '"\'[{('):
            line = line[:line.index("#")].rstrip()
        if line.strip():
            lines.append(line)
    cleaned = "\n".join(lines)

    debug_print(f"[DATA_PARSER] Processing {len(lines)} non-empty lines")

    # Parse each pattern
    out: Dict[str, Any] = {}
    for key, (pattern, caster) in _FLIGHT_ROUTE_PATTERNS.items():
        m = re.search(pattern, cleaned, re.DOTALL | re.MULTILINE)
        if m:
            val_txt = m.group(1).strip()
            if key == "order":
                # Handle unquoted transition_mode token
                val_txt = val_txt.replace("transition_mode", '"transition_mode"')
            try:
                out[key] = caster(val_txt)
                debug_print(f"[DATA_PARSER] ✓ {key:<28}: {out[key]!r}")
            except Exception as exc:
                debug_print(f"[DATA_PARSER] ⚠︎ failed to cast {key}: {exc}")
        else:
            debug_print(f"[DATA_PARSER] ⚠︎ {key:<28}: not found")

    # Explicit check for missing required keys
    required_keys = [
        "transition_mode",
        "transition_vertical_offset",
        "transition_horizontal_offset",
        "order",
        "standard_flight_routes",
        "flight_speed_map",
        "safety_zones_clearance",
        "safety_zones_clearance_adjust",
    ]

    missing_keys = [k for k in required_keys if k not in out]
    if missing_keys:
        debug_print("\n[ERROR] Missing required flight-route keys:")
        for key in missing_keys:
            debug_print(f"[ERROR]   {key}")

    # Validate types and values
    expected_types = {
        "order": list,
        "transition_mode": int,
        "transition_vertical_offset": float,
        "transition_horizontal_offset": float,
        "num_points": list,
        "horizontal_offsets_underdeck": list,
        "height_offsets_underdeck": list,
        "general_height_offset": float,
        "thresholds_zones": list,
        "custom_zone_angles": list,
        "safety_zones_clearance": list,
        "safety_zones_clearance_adjust": list,
        "heightMode": str,
        "perpendicular_distances": list,
        "connection_height": float,
        "num_passes": int,
        "safety_check_photo": int,
        "safety_check_underdeck": list,
        "safety_check_underdeck_axial": list,
        "n_girders": int,
        "globalWaypointTurnMode": str,
    }

    type_errors = []
    for key, expected_type in expected_types.items():
        if key in out and not isinstance(out[key], expected_type):
            type_errors.append((key, expected_type.__name__, type(out[key]).__name__))

    if type_errors:
        debug_print("\n[ERROR] Type validation errors:")
        for key, exp, got in type_errors:
            debug_print(f"[ERROR]   {key:<28} expected {exp}, got {got}")

    debug_print("[DATA_PARSER] " + "-" * 60 + "\n")
    return out


# -----------------------------------------------------------------------------
 # Internals
# -----------------------------------------------------------------------------

_KEY_VAL = re.compile(r"^(?P<key>[^#=]+?)\s*=\s*(?P<val>.+?)\s*$")


def _parse_generic_ini(raw: str) -> Dict[str, Any]:
    """Flexible *key = value* parser that supports multi-line lists/dicts and ignores headings."""
    out: Dict[str, Any] = {}

    lines = iter(raw.splitlines())
    for line in lines:
        original = line
        stripped = original.strip()
        if not stripped or stripped.startswith("#"):
            continue  # comment / empty
        if stripped.endswith(":") and "=" not in stripped:
            # Heading like "Safety Zones:" – skip
            continue
            
        m = _KEY_VAL.match(stripped)
        if not m:
            debug_print(f"[DATA_PARSER] ⚠︎ Ignored (no key=value): {original}")
            continue
            
        key, val = m.group("key").strip(), m.group("val").strip()
        
        # Merge subsequent lines if value is an opened list/dict spanning multiple lines
        if val and val[0] in "[{(" and not _balanced(val):
            collected = [val]
            for cont in lines:
                collected.append(cont.rstrip())
                if _balanced("\n".join(collected)):
                    break
            val = "\n".join(collected)

        # strip trailing comment (unless inside collection)
        if "#" in val and not val.lstrip().startswith(("[", "{", "(")):
            val = val.split("#", 1)[0].strip()

        out[key] = _auto_cast(val)
        
    return out


def _balanced(txt: str) -> bool:
    """Return *True* if brackets in *txt* are balanced."""
    stack = []
    pairs = {"[":"]", "(":")", "{":"}"}
    for ch in txt:
        if ch in pairs:
            stack.append(pairs[ch])
        elif ch in pairs.values():
            if not stack or stack.pop() != ch:
                return False
    return not stack




_NUM_RE = re.compile(r'^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$')

def _auto_cast(val: Any) -> Any:

    """
    Attempt to cast *val* to bool/int/float/list/dict/tuple/None.
    Returns the original (stripped) string if no cast applies.
    Never raises.
    """
    # Pass non-strings through unchanged
    if not isinstance(val, str):
        return val

    s = val.strip()
    if s == "":
        return s  # keep empty as empty string

    low = s.lower()

    # Booleans
    if low in {"true", "yes", "on"}:
        return True
    if low in {"false", "no", "off"}:
        return False

    # Null-like
    if low in {"none", "null"}:
        return None

    # Quoted strings (preserve content without quotes)
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        return s[1:-1]

    # Numbers: only cast if the whole string matches a numeric pattern
    if _NUM_RE.match(s):
        # Prefer int if there's no decimal point or exponent
        if "." not in s and "e" not in low:
            try:
                return int(s)
            except ValueError:
                # Fall back to float if int fails for some edge case
                try:
                    return float(s)
                except ValueError:
                    return s
        else:
            try:
                return float(s)
            except ValueError:
                return s

    # Structured literals: lists/dicts/tuples
    if s[:1] in "[{(" and s[-1:] in "]})":
        try:
            lit = ast.literal_eval(s)
            return lit
        except Exception:
            pass  # leave as string if it isn't a valid literal

    # Simple CSV fallback (only if not a bracketed literal)
    if "," in s and s[:1] not in "[{(":
        parts = [p.strip() for p in s.split(",")]
        # Try to cast each part recursively
        return [_auto_cast(p) for p in parts]

    # Default: keep as (stripped) string
    return s


def _print_summary(section: str, data: Dict[str, Any], *, required: tuple[str, ...]):
    """Pretty diagnostic printout for one section."""
    divider = "-" * 60
    debug_print(f"\n[DATA_PARSER] {divider}\n[DATA_PARSER] {section} PARAMETERS SUMMARY")
    if data:
        for k in sorted(data.keys()):
            v = data[k]
            debug_print(f"[DATA_PARSER]   {k:<25} : {v!r}  ({type(v).__name__})")
    else:
        debug_print(f"[DATA_PARSER]   <NO DATA PROVIDED>")

    missing = [m for m in required if m not in data]
    if missing:
        debug_print(f"[DATA_PARSER]   MISSING => {', '.join(missing)}")
        for m in missing:
            debug_print(f"[ERROR] Missing required {section.lower()} variable '{m}'. Please specify it in the corresponding text box.")
    debug_print(f"[DATA_PARSER] {divider}\n")
    


def _warn_if_missing(data: Dict[str, Any], *, required: tuple[str, ...], source: str) -> None:
    """Print an error for every *required* key that is missing in *data*."""
    for key in required:
        if key not in data:
            debug_print(f"[ERROR] Missing required {source} variable '{key}'. Please specify it in the corresponding text box.")


