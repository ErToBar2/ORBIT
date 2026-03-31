import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
from pyproj import CRS, Transformer

try:
    import ipywidgets as widgets
    from IPython.display import display, clear_output
except Exception:
    widgets = None
    display = None
    clear_output = None


# ============================================================
# Hardwritten defaults
# ============================================================
DEFAULT_INPUT_PATH = r""  # file or folder
DEFAULT_TARGET_CRS = "EPSG:3812"   # Lambert 2008
DEFAULT_SPACING_MM = 5.0           # 5 mm
DEFAULT_OUTPUT_FOLDER = "ROUTE_EXPORT"
DEFAULT_OVERWRITE = True
DEFAULT_WRITE_LOCAL_COORDS = True   # strongly recommended for viewing
DEFAULT_SAVE_TXT = True


# ============================================================
# Core helpers
# ============================================================
def collect_input_files(input_path: Path):
    """Collect .kmz/.zip/.kml from file or folder (recursive)."""
    if not input_path.exists():
        raise FileNotFoundError(f"Input path does not exist: {input_path}")

    exts = {".kmz", ".zip", ".kml"}

    if input_path.is_file():
        if input_path.suffix.lower() not in exts:
            raise ValueError(f"Unsupported file: {input_path.suffix}")
        return [input_path]

    return sorted([p for p in input_path.rglob("*") if p.is_file() and p.suffix.lower() in exts])


def safe_relative(path: Path, root: Path):
    try:
        return path.relative_to(root)
    except Exception:
        return Path(path.name)


def extract_kml_from_archive(src_archive: Path, kml_root: Path, input_root: Path):
    """
    Extract KML from KMZ/ZIP.
    Priority:
      1) template.kml
      2) doc.kml
      3) unique .kml if only one exists
      4) first .kml
    """
    kml_root.mkdir(parents=True, exist_ok=True)
    rel = safe_relative(src_archive, input_root)

    out_dir = kml_root / rel.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    out_kml = out_dir / f"{src_archive.stem}__extracted.kml"

    with zipfile.ZipFile(src_archive, "r") as zf:
        names = zf.namelist()
        kml_names = [n for n in names if n.lower().endswith(".kml")]
        if not kml_names:
            raise FileNotFoundError(f"No .kml found in archive: {src_archive}")

        # Prefer template/doc naming
        preferred = None
        for n in kml_names:
            low = n.lower()
            if low.endswith("template.kml"):
                preferred = n
                break
        if preferred is None:
            for n in kml_names:
                low = n.lower()
                if low.endswith("doc.kml"):
                    preferred = n
                    break
        if preferred is None:
            preferred = kml_names[0] if len(kml_names) == 1 else kml_names[0]

        out_kml.write_bytes(zf.read(preferred))

    return out_kml


def parse_waypoints_in_order(kml_path: Path):
    """
    Parse waypoint placemarks in document order.
    Reads KML <Placemark><Point><coordinates>lon,lat,h</coordinates>.
    """
    root = ET.parse(kml_path).getroot()

    waypoints = []
    for pm in root.findall(".//{*}Placemark"):
        coord_node = pm.find(".//{*}Point/{*}coordinates")
        if coord_node is None or not coord_node.text:
            continue

        txt = coord_node.text.strip()
        # KML Point coordinates are usually a single tuple "lon,lat,h"
        parts = [p.strip() for p in txt.split(",")]
        if len(parts) < 2:
            continue

        try:
            lon = float(parts[0])
            lat = float(parts[1])
            h = float(parts[2]) if len(parts) >= 3 and parts[2] != "" else 0.0
            waypoints.append((lon, lat, h))
        except Exception:
            continue

    return waypoints


def transform_waypoints(waypoints_llh, target_crs: str):
    """
    Transform WGS84 lon/lat/h (EPSG:4979) -> target CRS.
    If target CRS is 2D and no z is returned, keep original h.
    """
    dst = CRS.from_user_input(target_crs)
    tr = Transformer.from_crs(CRS.from_epsg(4979), dst, always_xy=True)

    xyz = []
    for lon, lat, h in waypoints_llh:
        res = tr.transform(lon, lat, h)
        if isinstance(res, tuple) and len(res) >= 3:
            x, y, z = res[0], res[1], res[2]
        else:
            x, y = res[0], res[1]
            z = h
        xyz.append((float(x), float(y), float(z)))
    return xyz, dst


def remove_consecutive_duplicates(points_xyz, eps=1e-12):
    """Remove consecutive duplicates."""
    if not points_xyz:
        return []
    out = [np.asarray(points_xyz[0], dtype=float)]
    for p in points_xyz[1:]:
        p = np.asarray(p, dtype=float)
        if np.linalg.norm(p - out[-1]) > eps:
            out.append(p)
    return [tuple(v.tolist()) for v in out]


def sample_polyline_segment_exact(points_xyz, spacing_m=0.005, eps=1e-12):
    """
    Exact segment-wise sampling:
    - For each consecutive waypoint pair, sample every spacing_m along the segment
    - Points lie EXACTLY on the straight segment (before file writing)
    - The spacing is reset at each segment (as requested)
    - Endpoints (main waypoints) are preserved exactly

    Returns:
      sampled_xyz: (N,3) float64
      is_main_wp: (N,) bool
      segment_id: (N,) int   # segment index for each point, -1 for first point
      s_route_m:  (N,) float # cumulative distance along route
    """
    p = np.asarray(points_xyz, dtype=np.float64)
    if p.ndim != 2 or p.shape[1] != 3:
        raise ValueError("points_xyz must be shape (N,3)")
    if len(p) < 2:
        raise ValueError("Need at least 2 points")

    spacing_m = float(spacing_m)
    if spacing_m <= 0:
        raise ValueError("spacing_m must be > 0")

    out_pts = [p[0].copy()]
    out_main = [True]
    out_seg = [-1]
    out_s = [0.0]

    route_s = 0.0

    for i in range(len(p) - 1):
        a = p[i]
        b = p[i + 1]
        v = b - a
        L = float(np.linalg.norm(v))

        if L <= eps:
            # Degenerate segment, still ensure endpoint is represented once
            if np.linalg.norm(out_pts[-1] - b) > eps:
                out_pts.append(b.copy())
                out_main.append(True)
                out_seg.append(i)
                out_s.append(route_s)
            else:
                # same point as current, mark current as main if needed
                out_main[-1] = True
            continue

        u = v / L

        # Interior samples at spacing, 2*spacing, ... < L
        k_max = int(np.floor((L - eps) / spacing_m))
        for k in range(1, k_max + 1):
            d = k * spacing_m
            if d >= L - eps:
                break
            q = a + d * u
            out_pts.append(q)
            out_main.append(False)
            out_seg.append(i)
            out_s.append(route_s + d)

        # Always include endpoint b (main waypoint)
        if np.linalg.norm(out_pts[-1] - b) > eps:
            out_pts.append(b.copy())
            out_main.append(True)
            out_seg.append(i)
            out_s.append(route_s + L)
        else:
            # extremely rare due to exact spacing hitting endpoint
            out_main[-1] = True

        route_s += L

    return (
        np.asarray(out_pts, dtype=np.float64),
        np.asarray(out_main, dtype=bool),
        np.asarray(out_seg, dtype=int),
        np.asarray(out_s, dtype=np.float64),
    )


def build_edges_consecutive(n_points: int):
    """Connect every consecutive sampled point."""
    if n_points < 2:
        return []
    return [(i, i + 1) for i in range(n_points - 1)]


def write_ply_ascii(
    out_ply: Path,
    xyz_points_global,
    edges,
    dst_crs: CRS,
    use_local_coords=True,
    overwrite=True,
):
    """
    Write ASCII PLY with DOUBLE precision vertices and edge list.
    If use_local_coords=True, writes local coordinates relative to first point (for viewer precision).
    Origin is stored in comments.
    """
    out_ply.parent.mkdir(parents=True, exist_ok=True)
    if out_ply.exists() and not overwrite:
        return out_ply

    pts_global = np.asarray(xyz_points_global, dtype=np.float64)
    if pts_global.ndim != 2 or pts_global.shape[1] != 3:
        raise ValueError("xyz_points_global must be shape (N,3)")

    if len(pts_global) == 0:
        raise ValueError("No points to write")

    if use_local_coords:
        origin = pts_global[0].copy()
        pts_write = pts_global - origin
    else:
        origin = np.zeros(3, dtype=np.float64)
        pts_write = pts_global

    with out_ply.open("w", encoding="utf-8", newline="\n") as f:
        f.write("ply\n")
        f.write("format ascii 1.0\n")
        f.write("comment Flight route sampled polyline\n")
        f.write(f"comment CRS: {dst_crs.to_string()}\n")
        f.write(f"comment COORDINATE_MODE: {'LOCAL' if use_local_coords else 'GLOBAL'}\n")
        f.write(f"comment ORIGIN_X {origin[0]:.12f}\n")
        f.write(f"comment ORIGIN_Y {origin[1]:.12f}\n")
        f.write(f"comment ORIGIN_Z {origin[2]:.12f}\n")

        f.write(f"element vertex {len(pts_write)}\n")
        f.write("property double x\n")
        f.write("property double y\n")
        f.write("property double z\n")

        f.write(f"element edge {len(edges)}\n")
        f.write("property int vertex1\n")
        f.write("property int vertex2\n")
        f.write("end_header\n")

        for x, y, z in pts_write:
            f.write(f"{x:.12f} {y:.12f} {z:.12f}\n")
        for a, b in edges:
            f.write(f"{int(a)} {int(b)}\n")

    return out_ply


def write_txt(
    out_txt: Path,
    xyz_points_global,
    is_main_wp,
    segment_id,
    s_route_m,
    dst_crs: CRS,
    use_local_coords=True,
    overwrite=True,
):
    """
    Write TXT with both global and local coordinates + metadata.
    """
    out_txt.parent.mkdir(parents=True, exist_ok=True)
    if out_txt.exists() and not overwrite:
        return out_txt

    pts_global = np.asarray(xyz_points_global, dtype=np.float64)
    is_main_wp = np.asarray(is_main_wp, dtype=bool)
    segment_id = np.asarray(segment_id, dtype=int)
    s_route_m = np.asarray(s_route_m, dtype=np.float64)

    if use_local_coords:
        origin = pts_global[0].copy()
        pts_local = pts_global - origin
    else:
        origin = np.zeros(3, dtype=np.float64)
        pts_local = pts_global.copy()

    with out_txt.open("w", encoding="utf-8", newline="\n") as f:
        f.write("# Flight route sampled points\n")
        f.write(f"# CRS: {dst_crs.to_string()}\n")
        f.write(f"# coordinate_mode: {'LOCAL+GLOBAL' if use_local_coords else 'GLOBAL'}\n")
        f.write(f"# origin_global_xyz: {origin[0]:.12f}, {origin[1]:.12f}, {origin[2]:.12f}\n")
        f.write("#\n")
        f.write("# idx\tis_main_wp\tsegment_id\ts_route_m\tx_local\ty_local\tz_local\tx_global\ty_global\tz_global\n")

        for i in range(len(pts_global)):
            xl, yl, zl = pts_local[i]
            xg, yg, zg = pts_global[i]
            f.write(
                f"{i}\t{1 if is_main_wp[i] else 0}\t{int(segment_id[i])}\t{s_route_m[i]:.6f}\t"
                f"{xl:.12f}\t{yl:.12f}\t{zl:.12f}\t{xg:.12f}\t{yg:.12f}\t{zg:.12f}\n"
            )

    return out_txt


def process_route_file(
    src_file: Path,
    input_root: Path,
    output_root: Path,
    target_crs: str,
    spacing_mm: float,
    overwrite=True,
    write_local_coords=True,
    save_txt=True,
):
    """
    Full pipeline for one route file.
    """
    # 1) KMZ/ZIP -> KML extract (or use KML directly)
    kml_cache_root = output_root / "_KML_EXTRACTED"
    if src_file.suffix.lower() in {".kmz", ".zip"}:
        kml_path = extract_kml_from_archive(src_file, kml_cache_root, input_root)
    else:
        kml_path = src_file

    # 2) Extract waypoints
    waypoints_llh = parse_waypoints_in_order(kml_path)
    if len(waypoints_llh) < 2:
        raise ValueError("Need at least 2 waypoint placemarks with <Point><coordinates>")

    # 3) Convert them (WGS84 -> target CRS)
    xyz_main, dst_crs = transform_waypoints(waypoints_llh, target_crs)

    # Clean consecutive duplicates
    xyz_main = remove_consecutive_duplicates(xyz_main)
    if len(xyz_main) < 2:
        raise ValueError("All consecutive waypoints collapsed to duplicates")

    # 4+5) Sample exactly on each segment every X mm
    spacing_m = float(spacing_mm) / 1000.0
    sampled_xyz, is_main_wp, segment_id, s_route_m = sample_polyline_segment_exact(xyz_main, spacing_m=spacing_m)

    # 4) Connect with edges (sampled polyline edges)
    edges = build_edges_consecutive(len(sampled_xyz))

    # Output paths (mirror structure)
    rel = safe_relative(src_file, input_root)
    out_ply = (output_root / "PLY" / rel).with_suffix(".ply")
    out_txt = (output_root / "TXT" / rel).with_suffix(".txt")

    # 6) Save PLY and TXT
    write_ply_ascii(
        out_ply=out_ply,
        xyz_points_global=sampled_xyz,
        edges=edges,
        dst_crs=dst_crs,
        use_local_coords=write_local_coords,
        overwrite=overwrite,
    )

    if save_txt:
        write_txt(
            out_txt=out_txt,
            xyz_points_global=sampled_xyz,
            is_main_wp=is_main_wp,
            segment_id=segment_id,
            s_route_m=s_route_m,
            dst_crs=dst_crs,
            use_local_coords=write_local_coords,
            overwrite=overwrite,
        )

    return {
        "source": str(src_file),
        "kml": str(kml_path),
        "out_ply": str(out_ply),
        "out_txt": str(out_txt) if save_txt else None,
        "n_waypoints": len(xyz_main),
        "n_sampled": int(len(sampled_xyz)),
        "n_edges": int(len(edges)),
        "target_crs": dst_crs.to_string(),
    }


# ============================================================
# Simple UI (ipywidgets)
# ============================================================
if widgets is None:
    print("ipywidgets is not available. Install it or run in Jupyter.")
else:
    path_w = widgets.Text(
        value=DEFAULT_INPUT_PATH,
        placeholder=r"C:\path\to\file.kmz  or  C:\path\to\folder",
        description="Input:",
        layout=widgets.Layout(width="95%"),
    )

    crs_w = widgets.Text(
        value=DEFAULT_TARGET_CRS,
        description="Target CRS:",
        layout=widgets.Layout(width="280px"),
    )

    spacing_mm_w = widgets.FloatText(
        value=float(DEFAULT_SPACING_MM),
        description="Step [mm]:",
        layout=widgets.Layout(width="170px"),
    )

    out_folder_w = widgets.Text(
        value=DEFAULT_OUTPUT_FOLDER,
        description="Out dir:",
        layout=widgets.Layout(width="240px"),
    )

    local_coords_w = widgets.Checkbox(
        value=bool(DEFAULT_WRITE_LOCAL_COORDS),
        description="PLY local coords"
    )

    save_txt_w = widgets.Checkbox(
        value=bool(DEFAULT_SAVE_TXT),
        description="Save TXT"
    )

    overwrite_w = widgets.Checkbox(
        value=bool(DEFAULT_OVERWRITE),
        description="Overwrite"
    )

    run_btn = widgets.Button(description="Run", button_style="success")
    prog = widgets.IntProgress(
        value=0,
        min=0,
        max=1,
        description="Routes",
        bar_style="warning",
        layout=widgets.Layout(width="430px")
    )

    status_w = widgets.HTML(value="<span style='color:#666;'>Ready</span>")
    out = widgets.Output()

    def _set_status(msg, color="#666"):
        status_w.value = f"<span style='color:{color};'>{msg}</span>"

    def _run(_):
        with out:
            clear_output()

            raw_path = str(path_w.value).strip().strip('"').strip("'")
            if not raw_path:
                _set_status("Input path missing", "#b00020")
                print("Please set an input path.")
                return

            try:
                spacing_mm = float(spacing_mm_w.value)
                if spacing_mm <= 0:
                    raise ValueError
            except Exception:
                _set_status("Invalid spacing", "#b00020")
                print("Step [mm] must be > 0.")
                return

            input_path = Path(raw_path)
            try:
                files = collect_input_files(input_path)
            except Exception as e:
                _set_status("Input error", "#b00020")
                print(f"ERROR: {e}")
                return

            if not files:
                _set_status("No files found", "#b00020")
                print("No .kmz/.zip/.kml files found.")
                return

            input_root = input_path if input_path.is_dir() else input_path.parent
            output_root = input_root / (str(out_folder_w.value).strip() or "ROUTE_EXPORT")

            prog.max = len(files)
            prog.value = 0

            ok_count = 0
            for i, src in enumerate(files, start=1):
                _set_status(f"Processing {i}/{len(files)}: {src.name}", "#666")
                try:
                    r = process_route_file(
                        src_file=src,
                        input_root=input_root,
                        output_root=output_root,
                        target_crs=str(crs_w.value).strip(),
                        spacing_mm=spacing_mm,
                        overwrite=bool(overwrite_w.value),
                        write_local_coords=bool(local_coords_w.value),
                        save_txt=bool(save_txt_w.value),
                    )
                    ok_count += 1
                    print(
                        f"OK  {src.name} -> {Path(r['out_ply']).name} "
                        f"({r['n_waypoints']} wp -> {r['n_sampled']} pts, {r['n_edges']} edges)"
                    )
                except Exception as e:
                    print(f"ERR {src.name} -> {e}")
                prog.value = i

            print()
            print(f"Done: {ok_count}/{len(files)} routes")
            print(f"Output root: {output_root}")
            _set_status(f"Done: {ok_count}/{len(files)} routes", "#0a7f2e")

    run_btn.on_click(_run)

    display(widgets.VBox([
        path_w,
        widgets.HBox([crs_w, spacing_mm_w, out_folder_w]),
        widgets.HBox([local_coords_w, save_txt_w, overwrite_w]),
        widgets.HBox([run_btn, prog]),
        status_w,
        out
    ]))