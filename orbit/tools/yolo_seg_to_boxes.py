# yolo_seg_to_boxes.py
# Convert YOLO segmentation masks (polygons) -> axis-aligned boxes (YOLO cx cy w h)
# and oriented bounding boxes (either cx cy w h theta or quad8).
# Works with 3..N polygon vertices; robust to degeneracies; no external deps required
# (OpenCV is optional for true min-area OBB).

import os
import math
from pathlib import Path
from typing import Optional, Tuple, List

import numpy as np

# =================== USER INPUT (your paths) ===================
LABELS_IN = r"L:\Projects\2022-10_Project_Erkki\Data\2025-09_Zultebrug\5_DamageDetection\1_RawAnnotations\labels_DJI_202509051325_592_ZultebrugUnderdeckSection2"
# Output folders will be created as siblings of LABELS_IN's parent:
#   ...\1_RawAnnotations\2_BB\labels
#   ...\1_RawAnnotations\3_OBB\labels

# =================== OBB SETTINGS ===================
WRITE_OBB    = True                  # set False to write only 2_BB
OBB_FORMAT   = "cxcywh_theta"        # "cxcywh_theta" or "quad8"
TRY_OPENCV_MINAREA = True            # If cv2 available, use minAreaRect for true min-area OBB

# Angle convention (for cxcywh_theta):
#   theta in radians, counter-clockwise from +x axis (image space, y downward).
#   We canonicalize so w >= h and theta ∈ [-pi/2, pi/2).

# =================== HELPERS ===================

def parse_seg_line(line: str) -> Optional[Tuple[int, np.ndarray]]:
    """
    Parse a YOLO segmentation line: 'cls x1 y1 x2 y2 ...'
    Returns (class_id, Nx2 array of normalized points) or None if malformed.
    """
    toks = line.strip().split()
    if not toks:
        return None
    try:
        cls = int(float(toks[0]))
    except ValueError:
        return None
    vals = toks[1:]
    if len(vals) < 6 or len(vals) % 2 != 0:
        return None
    try:
        pts = np.array(list(map(float, vals)), dtype=np.float64).reshape(-1, 2)
    except Exception:
        return None
    return cls, pts


def aabb_from_points(pts: np.ndarray) -> Tuple[float, float, float, float]:
    """Axis-aligned bbox (normalized): returns cx, cy, w, h."""
    xmin, ymin = pts.min(axis=0)
    xmax, ymax = pts.max(axis=0)
    w = max(1e-12, xmax - xmin)
    h = max(1e-12, ymax - ymin)
    cx = (xmin + xmax) * 0.5
    cy = (ymin + ymax) * 0.5
    return cx, cy, w, h


def _sanitize_points(pts: np.ndarray) -> np.ndarray:
    """Remove NaNs, clamp to [0,1], drop near-duplicates."""
    pts = np.asarray(pts, dtype=np.float64)
    pts = pts[np.isfinite(pts).all(axis=1)]
    if pts.size == 0:
        return pts
    pts = np.clip(pts, 0.0, 1.0)
    # Merge jittery duplicates by quantizing to a fine grid
    quant = np.round(pts * 1e6) / 1e6
    _, idx = np.unique(quant, axis=0, return_index=True)
    return pts[np.sort(idx)]


def _canonicalize_cxcywh_theta(cx, cy, w, h, theta):
    """
    Enforce w >= h and theta in [-pi/2, pi/2) with consistent orientation.
    If h > w, swap and rotate theta by +/- pi/2 accordingly.
    """
    if h > w:
        w, h = h, w
        theta += math.pi / 2
    while theta >=  math.pi/2: theta -= math.pi
    while theta <  -math.pi/2: theta += math.pi
    return cx, cy, w, h, theta


def _quad_from_cxcywh_theta(cx, cy, w, h, theta) -> np.ndarray:
    """4x2 rectangle corners from center/size/angle (normalized coords)."""
    c, s = math.cos(theta), math.sin(theta)
    R = np.array([[c, -s],
                  [s,  c]], dtype=np.float64)
    half = np.array([[-w/2, -h/2],
                     [ w/2, -h/2],
                     [ w/2,  h/2],
                     [-w/2,  h/2]], dtype=np.float64)
    quad = np.array([[cx, cy]]) + half @ R.T
    return quad


def _obb_opencv_minarea(pts: np.ndarray) -> Tuple[float, float, float, float, float, np.ndarray]:
    """
    True min-area rectangle via OpenCV (if available):
      returns (cx, cy, w, h, theta, quad)
    """
    import cv2  # optional
    box = cv2.minAreaRect(pts.astype(np.float32))   # ((cx,cy),(w,h),angle_degrees)
    (cx, cy), (w, h), angle_deg = box
    # OpenCV angle is degrees CW from +x; convert to CCW radians
    theta = -math.radians(angle_deg)
    cx, cy, w, h, theta = _canonicalize_cxcywh_theta(cx, cy, max(w, 1e-12), max(h, 1e-12), theta)
    quad = cv2.boxPoints(((cx, cy), (w, h), -math.degrees(theta)))  # back from canonical
    quad = quad.astype(np.float64)
    return cx, cy, w, h, theta, quad


def robust_obb(points: np.ndarray) -> Tuple[float, float, float, float, float, np.ndarray]:
    """
    Robust OBB for polygons with 3..N points (handles 1–2 points as degenerate cases).
    Prefers OpenCV minAreaRect; falls back to PCA when OpenCV isn't available.
    Returns: cx, cy, w, h, theta (radians), quad(4x2)
    """
    pts = _sanitize_points(points)
    n = len(pts)
    if n == 0:
        cx = cy = 0.5
        w = h = 1e-12
        theta = 0.0
        return cx, cy, w, h, theta, _quad_from_cxcywh_theta(cx, cy, w, h, theta)
    if n == 1:
        cx, cy = pts[0]
        w = h = 1e-12
        theta = 0.0
        return cx, cy, w, h, theta, _quad_from_cxcywh_theta(cx, cy, w, h, theta)
    if n == 2:
        cx, cy = pts.mean(axis=0)
        v = pts[1] - pts[0]
        L = float(np.hypot(v[0], v[1]))
        theta = math.atan2(v[1], v[0]) if L > 0 else 0.0
        w = max(L, 1e-12)
        h = 1e-12
        cx, cy, w, h, theta = _canonicalize_cxcywh_theta(cx, cy, w, h, theta)
        return cx, cy, w, h, theta, _quad_from_cxcywh_theta(cx, cy, w, h, theta)

    if TRY_OPENCV_MINAREA:
        try:
            return _obb_opencv_minarea(pts)
        except Exception:
            pass  # fall back to PCA

    # PCA fallback
    mu = pts.mean(axis=0)
    X = pts - mu
    cov = (X.T @ X) / max(1, n - 1)
    vals, vecs = np.linalg.eigh(cov)   # ascending eigenvalues
    if vals[-1] < 1e-14:  # near-point
        cx, cy = mu
        w = h = 1e-12
        theta = 0.0
        return cx, cy, w, h, theta, _quad_from_cxcywh_theta(cx, cy, w, h, theta)

    axis1 = vecs[:, 1]                 # principal axis
    proj1 = X @ axis1
    axis0 = vecs[:, 0]
    proj0 = X @ axis0

    w = max(proj1.max() - proj1.min(), 1e-12)
    h = max(proj0.max() - proj0.min(), 1e-12)
    theta = math.atan2(axis1[1], axis1[0])
    cx, cy = mu[0], mu[1]
    cx, cy, w, h, theta = _canonicalize_cxcywh_theta(cx, cy, w, h, theta)
    quad = _quad_from_cxcywh_theta(cx, cy, w, h, theta)
    quad = np.clip(quad, 0.0, 1.0)
    return cx, cy, w, h, theta, quad


def write_bb_line(cls: int, cx: float, cy: float, w: float, h: float) -> str:
    return f"{cls} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n"


def write_obb_line(cls: int, cx: float, cy: float, w: float, h: float, theta: float, quad: np.ndarray) -> str:
    if OBB_FORMAT == "cxcywh_theta":
        return f"{cls} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f} {theta:.6f}\n"
    elif OBB_FORMAT == "quad8":
        q = quad.reshape(-1)
        return f"{cls} " + " ".join(f"{v:.6f}" for v in q) + "\n"
    else:
        raise ValueError("Invalid OBB_FORMAT (use 'cxcywh_theta' or 'quad8').")


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def process_label_file(in_path: Path, bb_out_dir: Path, obb_out_dir: Optional[Path]) -> Tuple[int, int]:
    """
    Process one .txt label file. Returns (#AABB written, #OBB written).
    """
    try:
        lines = [ln for ln in in_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    except UnicodeDecodeError:
        lines = [ln for ln in in_path.read_text(encoding="latin-1").splitlines() if ln.strip()]

    bb_lines: List[str] = []
    obb_lines: List[str] = []

    for ln in lines:
        parsed = parse_seg_line(ln)
        if parsed is None:
            continue
        cls, pts = parsed
        pts = np.clip(pts, 0.0, 1.0)  # safety

        # AABB
        cx, cy, w, h = aabb_from_points(pts)
        bb_lines.append(write_bb_line(cls, cx, cy, w, h))

        # OBB
        if WRITE_OBB and obb_out_dir is not None:
            ocx, ocy, ow, oh, theta, quad = robust_obb(pts)
            quad = np.clip(quad, 0.0, 1.0)
            obb_lines.append(write_obb_line(cls, ocx, ocy, ow, oh, theta, quad))

    # Save outputs
    n_bb = 0
    n_obb = 0
    if bb_lines:
        out_bb = bb_out_dir / in_path.name
        out_bb.write_text("".join(bb_lines), encoding="utf-8")
        n_bb = len(bb_lines)

    if WRITE_OBB and obb_lines and obb_out_dir is not None:
        out_obb = obb_out_dir / in_path.name
        out_obb.write_text("".join(obb_lines), encoding="utf-8")
        n_obb = len(obb_lines)

    return n_bb, n_obb


def main():
    src = Path(LABELS_IN)
    if not src.exists() or not src.is_dir():
        raise SystemExit(f"[error] Input labels dir not found: {src}")

    parent = src.parent  # typically ...\1_RawAnnotations
    bb_dir  = parent / "2_BB"  / "labels"
    obb_dir = parent / "3_OBB" / "labels" if WRITE_OBB else None

    ensure_dir(bb_dir)
    if WRITE_OBB and obb_dir is not None:
        ensure_dir(obb_dir)

    files = sorted(src.glob("*.txt"))
    if not files:
        print(f"[warn] No .txt label files found in: {src}")
        return

    total_bb = total_obb = 0
    for i, p in enumerate(files, 1):
        n_bb, n_obb = process_label_file(p, bb_dir, obb_dir)
        total_bb += n_bb
        total_obb += n_obb
        print(f"[{i:>4}/{len(files)}] {p.name}: AABB={n_bb}  OBB={n_obb}")

    print("\n[done]")
    print(f"  Files processed : {len(files)}")
    print(f"  AABB instances  : {total_bb} → {bb_dir}")
    if WRITE_OBB and obb_dir is not None:
        print(f"  OBB  instances  : {total_obb} → {obb_dir}")
        print(f"  OBB format      : {OBB_FORMAT}")


if __name__ == "__main__":
    main()
