from __future__ import annotations

"""
MRK2RC.py
=========
Generates RealityScan RTK priors (trusted / untrusted image lists + trajectory
TSV + apply-priors .bat) from DJI .MRK timestamp files.

Key improvements over original:
  - Matching uses the _NNNN_ sequence number embedded in every DJI filename as
    the primary key (MRK row N == image _NNNN_).  This is robust to deletions
    and folder reorganisation.
  - Neighbor search: sibling folders of the MRK folder are scanned automatically
    so images that were moved are still found.
  - Collision resolution: when the same _NNNN_ appears in more than one folder
    (e.g. two different flights), the candidate with the smallest GPS-SOW
    residual wins.
  - Two-pass offset estimation: the SOW timezone/clock offset is estimated from
    unambiguous (single-candidate) pairs first, then applied when resolving
    collisions and validating all pairs.
  - RSPROJ is optional: set to None / "" to run without a RealityScan project.
    Outputs fall back to disk-path image lists and a per-MRK diagnostic CSV.
"""

import argparse
import csv as _csv
import datetime as dt
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from tqdm import tqdm

try:
    from pyproj import CRS, Transformer
except Exception:
    CRS = None
    Transformer = None


# ============================================================
# CONFIG
# ============================================================

CONFIG = {
    # One or more root directories or MRK file paths.
    # When a directory is given the script discovers all .MRK files and images
    # inside it recursively.
    "ROOTS": [
        r"L:\Projects\2022-10_Project_Erkki\Data\2023-11_Merendreeburg\1_RawData\260220"
    ],
    "OUT_ROOT": r"L:\Projects\2022-10_Project_Erkki\Data\2023-11_Merendreeburg\1_RawData\260220\All_trajectories_RTK",
    "RSPROJ": r"L:\Projects\2022-10_Project_Erkki\Data\2023-11_Merendreeburg\3_Processing\260226_AllMerendree\260226_AllMerendree.rsproj",
    "RS_EXE": r"%ProgramFiles%\Epic Games\RealityScan_2.1\RealityScan.exe",

    "CRS_OUT": "EPSG:3812",

    # Trust thresholds
    "MIN_HEIGHT_M": 60.0,
    "MAX_SIG_E": 0.03,
    "MAX_SIG_N": 0.03,
    "MAX_SIG_V": 0.06,

    # Use only FIX lines (last col)
    "FIX_ONLY": True,
    "FIX_ONLY_TAG": "50,Q",

    # Time matching
    "SOW_MATCH_TOL_S": 1.0,       # filename timestamp is 1-second resolution
    "MAX_BAD_RATE": 0.10,

    # Offset estimation between MRK SOW and filename-derived SOW
    "ENABLE_OFFSET_ESTIMATION": True,
    "OFFSET_EST_SAMPLE_MAX": 80,
    "OFFSET_EST_MAX_ABS_S": 3 * 3600.0,   # allow local-vs-UTC differences
    "OFFSET_EST_MAX_MAD_S": 2.0,

    "IMAGE_EXTS": [".jpg", ".jpeg", ".tif", ".tiff", ".png", ".dng"],

    "ENFORCE_SINGLE_CALIB_AND_LENS_GROUP": True,
}


# ============================================================
# Logging
# ============================================================

class Logger:
    def __init__(self, log_path: Path):
        self.log_path = log_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._f = self.log_path.open("w", encoding="utf-8")

    def close(self):
        try:
            self._f.close()
        except Exception:
            pass

    def log(self, msg: str):
        stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{stamp}] {msg}"
        print(line, flush=True)
        self._f.write(line + "\n")
        self._f.flush()


def abort(log: Logger, msg: str, code: int = 1):
    log.log(f"[ABORT] {msg}")
    log.close()
    raise SystemExit(code)


def ensure_exists(log: Logger, p: Path, label: str):
    if not p.exists():
        abort(log, f"{label} does not exist: {p}")


def natural_key(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def dedup_preserve(seq: List[Path]) -> List[Path]:
    seen = set()
    out: List[Path] = []
    for p in seq:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


# ============================================================
# Project path extraction
# ============================================================

def extract_project_image_paths(rsproj_path: Path, exts: List[str]) -> List[str]:
    """
    Extract image paths stored in a RealityScan .rsproj file.

    RealityScan stores paths as fileName="..." XML attributes.  These can be
    either absolute (C:\\...) or relative (..\\..\\folder\\image.JPG) depending
    on how the project was created.  We capture both and return them exactly as
    they appear in the file so that RealityScan's CLI selection commands can
    reference them verbatim.

    Falls back to a broad drive-letter scan in case the project uses a
    non-standard format.
    """
    txt = rsproj_path.read_text(encoding="utf-8", errors="ignore")
    exts_re = "|".join(re.escape(e.lstrip(".")) for e in exts)

    paths: List[str] = []

    # Primary: extract fileName="..." attribute values (relative or absolute)
    attr_pattern = re.compile(
        rf'fileName="([^"]*\.({exts_re}))"',
        re.IGNORECASE,
    )
    for m in attr_pattern.finditer(txt):
        paths.append(m.group(1))

    # Fallback: scan for bare absolute Windows paths (C:\... or C:/...)
    if not paths:
        abs_pattern = re.compile(
            rf'([A-Za-z]:[\\/][^<>\r\n"\']+\.({exts_re}))',
            re.IGNORECASE,
        )
        for m in abs_pattern.finditer(txt):
            paths.append(m.group(1))

    seen: set = set()
    out: List[str] = []
    base = rsproj_path.parent

    for p in paths:
        if p in seen:
            continue
        seen.add(p)

        p_str = p.strip().strip('"')

        # If the rsproj stores a relative path like ..\..\foo\bar.jpg,
        # expand it to an absolute path based on the rsproj folder.
        pp = Path(p_str)
        if not pp.is_absolute():
            import os  # (only once at top of file if not already imported)

            pp = Path(os.path.normpath(os.path.abspath(str(base / pp))))

        # RealityCapture is happiest with Windows-style backslashes

        out.append(str(pp).replace("/", "\\"))

    return out


def build_project_basename_index(project_paths: List[str]) -> Dict[str, List[str]]:
    idx: Dict[str, List[str]] = {}
    for p in project_paths:
        base = Path(p).name.lower()
        idx.setdefault(base, []).append(p)
    return idx


def map_disk_paths_to_project_paths(
    disk_paths: List[Path],
    proj_index: Dict[str, List[str]],
    log: Logger,
    label: str
) -> Tuple[List[str], List[Path]]:
    project_list: List[str] = []
    dropped: List[Path] = []
    for p in disk_paths:
        base = p.name.lower()
        cands = proj_index.get(base, [])
        if len(cands) == 1:
            project_list.append(cands[0])
        else:
            dropped.append(p)

    if dropped:
        n_amb = sum(1 for p in dropped if len(proj_index.get(p.name.lower(), [])) > 1)
        n_miss = len(dropped) - n_amb
        log.log(f"[INFO] {label}: {len(dropped)} images could not be mapped to project paths "
                f"(missing={n_miss}, ambiguous={n_amb}). They remain UNTRUSTED.")
    return project_list, dropped


# ============================================================
# Discovery
# ============================================================

def dji_session_id(folder_name: str) -> Optional[str]:
    """
    Extract the session number from a DJI folder name.

    DJI standard:  DJI_YYYYMMDDHHMMSS_NNN_description
    Example:       DJI_202602201224_681_OverviewAuto  ->  '681'

    Returns None for folders that don't follow this pattern
    (e.g. 'Different folder name', 'deleted', 'All2').
    """
    m = re.match(r"DJI_\d{8,14}_(\d+)_", folder_name, re.IGNORECASE)
    return m.group(1) if m else None


def neighbor_search_folders(image_root: Path) -> List[Path]:
    """
    Return the list of folders to scan for images belonging to the same flight
    as the MRK that lives in *image_root*.

    Filtering rule (prevents cross-flight sequence-number collisions):
      - Always include *image_root* itself.
      - For each sibling directory S of image_root:
          * If image_root has a DJI session ID (e.g. '681') and S also has a
            DJI session ID: only include S when both IDs match.
          * If S does NOT have a DJI session ID (ad-hoc folder like
            'Different folder name' or 'deleted'): always include.
          * If image_root has no DJI session ID: include all siblings
            (fallback for non-standard folder naming).
    """
    folders = [image_root]
    primary_sid = dji_session_id(image_root.name)

    for sib in image_root.parent.iterdir():
        if not sib.is_dir() or sib == image_root:
            continue
        sib_sid = dji_session_id(sib.name)
        if primary_sid is None:
            folders.append(sib)                         # no pattern: include all
        elif sib_sid is None:
            folders.append(sib)                         # ad-hoc folder: include
        elif sib_sid == primary_sid:
            folders.append(sib)                         # same session: include
        # else: different DJI session – skip to avoid cross-flight collisions

    return folders


def discover_mrk_files_from_input(p: Path) -> List[Path]:
    if p.is_file():
        return [p] if p.suffix.lower() == ".mrk" else []
    if p.is_dir():
        return sorted(set(list(p.rglob("*.MRK")) + list(p.rglob("*.mrk"))))
    return []


def build_image_inventory_recursive(root: Path, exts: List[str]) -> List[Path]:
    exts_l = set(e.lower() for e in exts)
    imgs: List[Path] = []
    for fp in root.rglob("*"):
        if fp.is_file() and fp.suffix.lower() in exts_l:
            imgs.append(fp)
    imgs.sort(key=lambda p: natural_key(str(p)))
    return imgs


def build_image_inventory_shallow(root: Path, exts: List[str]) -> List[Path]:
    exts_l = set(e.lower() for e in exts)
    imgs: List[Path] = []
    for fp in root.iterdir():
        if fp.is_file() and fp.suffix.lower() in exts_l:
            imgs.append(fp)
    imgs.sort(key=lambda p: natural_key(str(p)))
    return imgs


def build_seq_image_map(
    folders: List[Path],
    exts: List[str],
) -> Dict[int, List[Tuple[Path, Tuple[int, float, int]]]]:
    """
    Scan each folder (shallow) for DJI images containing a _NNNN_ sequence number.

    Returns:  seq_number -> [(image_path, (gps_week, sow, seq)), ...]

    Multiple entries per key mean the same sequence number exists in more than
    one folder — a collision that will be resolved later via SOW distance.
    """
    exts_l = {e.lower() for e in exts}
    seq_re = re.compile(r"_(\d{4})_", re.IGNORECASE)
    result: Dict[int, List[Tuple[Path, Tuple[int, float, int]]]] = {}
    for folder in folders:
        if not folder.is_dir():
            continue
        for fp in sorted(folder.iterdir(), key=lambda p: natural_key(p.name)):
            if not fp.is_file() or fp.suffix.lower() not in exts_l:
                continue
            m = seq_re.search(fp.name)
            if not m:
                continue
            seq_num = int(m.group(1))
            time_info = read_image_gps_week_sow_seq(fp)
            if time_info is None:
                continue
            result.setdefault(seq_num, []).append((fp, time_info))
    return result


# ============================================================
# MRK parsing
# ============================================================

@dataclass(frozen=True)
class MrkRecord:
    idx: int
    sow: float
    gps_week: int
    lat: float
    lon: float
    ellh: float
    sig_n: float
    sig_e: float
    sig_v: float
    fix_tag: str


def _parse_labeled_float(s: str) -> float:
    s = s.strip()
    if "," in s:
        a, _ = s.split(",", 1)
        return float(a.strip())
    return float(s)


def parse_timestamp_mrk(mrk_path: Path) -> List[MrkRecord]:
    recs: List[MrkRecord] = []
    lines = mrk_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    for ln in lines:
        if not ln.strip():
            continue
        parts = ln.split("\t")
        if len(parts) < 11:
            continue
        try:
            idx = int(parts[0].strip())
            sow = float(parts[1].strip())
        except Exception:
            continue

        m = re.search(r"\[(\d+)\]", parts[2])
        if not m:
            continue
        gps_week = int(m.group(1))

        try:
            lat = _parse_labeled_float(parts[6])
            lon = _parse_labeled_float(parts[7])
            ellh = _parse_labeled_float(parts[8])
        except Exception:
            continue

        acc_nums = [a.strip() for a in parts[9].strip().split(",")]
        if len(acc_nums) < 3:
            continue
        try:
            sig_n = float(acc_nums[0])
            sig_e = float(acc_nums[1])
            sig_v = float(acc_nums[2])
        except Exception:
            continue

        fix_tag = parts[-1].strip()

        recs.append(MrkRecord(
            idx=idx, sow=sow, gps_week=gps_week,
            lat=lat, lon=lon, ellh=ellh,
            sig_n=sig_n, sig_e=sig_e, sig_v=sig_v,
            fix_tag=fix_tag
        ))
    return recs


# ============================================================
# CRS transform
# ============================================================

def to_output_xy(lat: float, lon: float, crs_out: str) -> Tuple[float, float]:
    if crs_out.upper() in ("EPSG:4326", "WGS84", "WGS 84"):
        return lon, lat

    if CRS is None or Transformer is None:
        raise RuntimeError("pyproj not installed. pip install pyproj")

    tf = Transformer.from_crs(CRS.from_epsg(4326), CRS.from_user_input(crs_out), always_xy=True)
    X, Y = tf.transform(lon, lat)
    return float(X), float(Y)


# ============================================================
# Trust filter
# ============================================================

def is_trustworthy(rec: MrkRecord, min_height_m: float, max_sig_e: float, max_sig_n: float, max_sig_v: float) -> bool:
    return (rec.ellh >= min_height_m) and (rec.sig_e <= max_sig_e) and (rec.sig_n <= max_sig_n) and (rec.sig_v <= max_sig_v)


# ============================================================
# Time conversion + filename parsing
# ============================================================

GPS_EPOCH = dt.datetime(1980, 1, 6, 0, 0, 0)


def datetime_to_gps_week_sow(t: dt.datetime) -> Tuple[int, float]:
    if t.tzinfo is not None:
        t = t.replace(tzinfo=None)
    delta = t - GPS_EPOCH
    total_seconds = delta.total_seconds()
    gps_week = int(total_seconds // (7 * 86400))
    sow = float(total_seconds - gps_week * 7 * 86400)
    return gps_week, sow


def parse_dji_time_and_seq_from_name(img_path: Path) -> Optional[Tuple[dt.datetime, int]]:
    """DJI_20260220132647_0006_V -> dt=2026-02-20 13:26:47, seq=6"""
    s = img_path.stem
    m = re.search(r"DJI_(\d{14})(?:_(\d{4}))?", s)
    if not m:
        return None
    ts = m.group(1)
    seq = int(m.group(2)) if m.group(2) else 0
    try:
        t = dt.datetime(
            int(ts[0:4]), int(ts[4:6]), int(ts[6:8]),
            int(ts[8:10]), int(ts[10:12]), int(ts[12:14])
        )
        return t, seq
    except Exception:
        return None


def read_image_gps_week_sow_seq(img_path: Path) -> Optional[Tuple[int, float, int]]:
    parsed = parse_dji_time_and_seq_from_name(img_path)
    if parsed is None:
        return None
    t, seq = parsed
    w, sow = datetime_to_gps_week_sow(t)
    return w, sow, seq


# ============================================================
# Robust stats for offset estimation
# ============================================================

def median(vals: List[float]) -> float:
    if not vals:
        return float("nan")
    v = sorted(vals)
    n = len(v)
    mid = n // 2
    if n % 2 == 1:
        return v[mid]
    return 0.5 * (v[mid - 1] + v[mid])


def mad(vals: List[float], center: float) -> float:
    if not vals or not math.isfinite(center):
        return float("nan")
    dev = [abs(x - center) for x in vals]
    return median(dev)


# ============================================================
# Seq-based matching with SOW cross-validation
# ============================================================

def match_by_seq_and_sow(
    recs: List[MrkRecord],
    seq_map: Dict[int, List[Tuple[Path, Tuple[int, float, int]]]],
    sow_tol_s: float,
    log: Logger,
    mrk_name: str,
) -> Tuple[List[Tuple[MrkRecord, Path]], float, int, int]:
    """
    Two-pass matching:

    Pass 1 — seq only, unambiguous candidates:
        Collect (mrk_sow - img_sow) differences from records that map to
        exactly one image, then estimate the clock/timezone offset as the
        median of those differences.

    Pass 2 — seq + SOW:
        For each MRK record look up its seq number in seq_map.
        - No candidates    -> image was deleted; count as n_deleted.
        - One candidate    -> validate SOW residual; flag if outside tolerance.
        - Many candidates  -> collision (same _NNNN_ in multiple folders).
                             Pick the one with the smallest adjusted SOW
                             residual; log the decision.

    Returns:
        pairs      – validated (MrkRecord, image_path) list
        offset_s   – estimated SOW offset applied
        n_deleted  – MRK records with no image file anywhere
        n_sow_fail – pairs whose SOW residual exceeded sow_tol_s
    """
    # ------------------------------------------------------------------
    # Pass 1: estimate offset from unambiguous matches
    # ------------------------------------------------------------------
    sow_diffs: List[float] = []
    for rec in recs:
        cands = seq_map.get(rec.idx, [])
        if len(cands) == 1:
            _, (_, img_sow, _) = cands[0]
            sow_diffs.append(rec.sow - img_sow)

    offset_s = 0.0
    if sow_diffs and CONFIG["ENABLE_OFFSET_ESTIMATION"]:
        k = min(CONFIG["OFFSET_EST_SAMPLE_MAX"], len(sow_diffs))
        sample = sow_diffs[:k]
        off = median(sample)
        if math.isfinite(off) and abs(off) <= CONFIG["OFFSET_EST_MAX_ABS_S"]:
            residuals = [d - off for d in sample]
            r_mad = mad(residuals, 0.0)
            if math.isfinite(r_mad) and r_mad <= CONFIG["OFFSET_EST_MAX_MAD_S"]:
                offset_s = off

    # ------------------------------------------------------------------
    # Pass 2: match each record using seq + adjusted SOW
    # ------------------------------------------------------------------
    def sow_residual(rec: MrkRecord, time_info: Tuple[int, float, int]) -> float:
        _, img_sow, _ = time_info
        return abs((rec.sow - offset_s) - img_sow)

    pairs: List[Tuple[MrkRecord, Path]] = []
    n_deleted = 0
    n_sow_fail = 0

    for rec in recs:
        cands = seq_map.get(rec.idx, [])

        if not cands:
            n_deleted += 1
            continue

        if len(cands) == 1:
            img_path, time_info = cands[0]
            res = sow_residual(rec, time_info)
            if res > sow_tol_s:
                n_sow_fail += 1
                log.log(
                    f"  [WARN] {mrk_name} seq={rec.idx:04d}: "
                    f"SOW residual {res:.3f}s > tol {sow_tol_s}s "
                    f"(img={img_path.name})"
                )
            pairs.append((rec, img_path))

        else:
            # Collision: rank candidates by SOW residual, pick the closest
            ranked = sorted(cands, key=lambda c: sow_residual(rec, c[1]))
            best_img, best_ti = ranked[0]
            best_res = sow_residual(rec, best_ti)
            losers = [c[0].name for c in ranked[1:]]

            if best_res > sow_tol_s:
                n_sow_fail += 1
                log.log(
                    f"  [WARN] {mrk_name} seq={rec.idx:04d}: collision, "
                    f"best SOW residual {best_res:.3f}s > tol. "
                    f"Picked {best_img.name}, rejected {losers}"
                )
            else:
                log.log(
                    f"  [INFO] {mrk_name} seq={rec.idx:04d}: collision resolved "
                    f"by SOW -> {best_img.name} (res={best_res:.3f}s), "
                    f"rejected {losers}"
                )
            pairs.append((rec, best_img))

    return pairs, offset_s, n_deleted, n_sow_fail


# ============================================================
# Writers
# ============================================================

def write_imagelist_strings(out_path: Path, image_paths: List[str]) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(image_paths) + ("\n" if image_paths else ""), encoding="utf-8")


def write_trajectory_tsv_no_header(
    out_path: Path,
    rows: List[Tuple[str, float, float, float, float, float, float]]
) -> None:
    """image_path<TAB>X<TAB>Y<TAB>alt<TAB>sigE<TAB>sigN<TAB>sigV"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="\n") as f:
        for img_path_str, X, Y, alt, sigE, sigN, sigV in rows:
            f.write(f"{img_path_str}\t{X:.10f}\t{Y:.10f}\t{alt:.4f}\t{sigE:.6f}\t{sigN:.6f}\t{sigV:.6f}\n")


def write_match_diagnostics_csv(
    out_path: Path,
    all_recs: List[MrkRecord],
    pairs: List[Tuple[MrkRecord, Path]],
    n_deleted: int,
) -> None:
    """
    Write a CSV with one row per MRK record showing the matched image path
    (or an empty path with status='image_deleted' for unmatched records).
    """
    paired_by_idx = {rec.idx: img for rec, img in pairs}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = _csv.writer(f)
        w.writerow([
            "mrk_index", "gps_sow", "latitude", "longitude", "ellh",
            "sig_e", "sig_n", "sig_v", "fix_tag",
            "image_name", "image_folder", "image_path", "status",
        ])
        for rec in sorted(all_recs, key=lambda r: r.idx):
            img = paired_by_idx.get(rec.idx)
            if img:
                status = "matched"
                img_name = img.name
                img_folder = img.parent.name
                img_path_str = str(img)
            else:
                status = "image_deleted"
                img_name = img_folder = img_path_str = ""
            w.writerow([
                rec.idx, f"{rec.sow:.6f}",
                f"{rec.lat:.8f}", f"{rec.lon:.8f}", f"{rec.ellh:.4f}",
                f"{rec.sig_e:.6f}", f"{rec.sig_n:.6f}", f"{rec.sig_v:.6f}",
                rec.fix_tag,
                img_name, img_folder, img_path_str, status,
            ])


def write_bat_apply_all(
    out_bat: Path,
    rs_exe: str,
    rsproj: Path,
    trusted_list: Path,
    untrusted_list: Path,
    enforce_groups: bool = True,
) -> None:
    """
    Write a robust .bat that applies pose priors / groups in RealityScan/RealityCapture.

    Critical BAT rule:
    - Do NOT place blank lines or REM comments inside a line-continued (^) command block.
      We therefore write the long command as ONE logical block (joined with ^\n  ),
      and put comments outside that block (using `echo`).
    """
    out_bat.parent.mkdir(parents=True, exist_ok=True)

    # Pre-flight checks and human-readable messages
    header = [
        "@echo off",
        "setlocal",
        f'if not exist "{rsproj}" (echo [ABORT] Project not found: "{rsproj}" & exit /b 1)',
        f'if not exist "{trusted_list}" (echo [ABORT] Missing: "{trusted_list}" & exit /b 1)',
        f'if not exist "{untrusted_list}" (echo [ABORT] Missing: "{untrusted_list}" & exit /b 1)',
        "echo [INFO] Applying priors and groups...",
        "echo [INFO] Project: " + str(rsproj),
        "echo [INFO] Trusted list: " + str(trusted_list),
        "echo [INFO] Untrusted list: " + str(untrusted_list),
        "",
    ]

    # Build the RealityScan command as a list of args
    # IMPORTANT: no blank lines / REM inside the continued block.
    cmd = [
        f'"{rs_exe}"',
        f'-load "{rsproj}"',
        "-selectAllImages",
        '  -editInputSelection "inpPose=0"',
        f'-importImageSelection "{trusted_list}"',
        '  -editInputSelection "inpPose=1"',
    ]

    if enforce_groups:
        cmd += [
            "-setConstantCalibrationGroups",
            "-setPriorCalibrationGroup 1",
            "-setPriorLensGroup 1",
        ]

    cmd += [
        f'-importImageSelection "{untrusted_list}"',
        '  -editInputSelection "inpPose=0"',
    ]

    if enforce_groups:
        cmd += [
            "-setConstantCalibrationGroups",
            "-setPriorCalibrationGroup 1",
            "-setPriorLensGroup 1",
        ]

    cmd += [
        f'-save "{rsproj}"',
    ]

    # Join into a single line-continued block
    # (We indent continuation lines for readability.)
    cmd_block = " ^\n  ".join(cmd)

    footer = [
        "",
        "if errorlevel 1 (echo [ERROR] RealityScan command failed & exit /b 1)",
        "echo [OK] Done. Project saved.",
        "endlocal",
        "",
    ]

    out_bat.write_text("\n".join(header + [cmd_block] + footer), encoding="utf-8")

# ============================================================
# CLI + defaults
# ============================================================

def parse_args_or_defaults() -> argparse.Namespace:
    ap = argparse.ArgumentParser(add_help=True)

    ap.add_argument("--roots", nargs="+", default=None)
    ap.add_argument("--out_root", default=None)
    ap.add_argument("--rsproj", default=None)
    ap.add_argument("--rs_exe", default=None)

    ap.add_argument("--crs_out", default=None)
    ap.add_argument("--min_height_m", type=float, default=None)
    ap.add_argument("--max_sig_e", type=float, default=None)
    ap.add_argument("--max_sig_n", type=float, default=None)
    ap.add_argument("--max_sig_v", type=float, default=None)

    ap.add_argument("--fix_only", action="store_true", default=False)
    ap.add_argument("--no_fix_only", action="store_true", default=False)

    ap.add_argument("--sow_tol_s", type=float, default=None)
    ap.add_argument("--max_bad_rate", type=float, default=None)

    ap.add_argument("--enforce_single_calibration_and_lens_group", action="store_true", default=False)

    ns = ap.parse_args()

    ns.roots = ns.roots if ns.roots else CONFIG["ROOTS"]
    ns.out_root = ns.out_root if ns.out_root else CONFIG["OUT_ROOT"]
    # rsproj: CLI arg overrides CONFIG; both None means "no project"
    ns.rsproj = ns.rsproj if ns.rsproj else (CONFIG["RSPROJ"] or None)
    ns.rs_exe = ns.rs_exe if ns.rs_exe else CONFIG["RS_EXE"]

    ns.crs_out = ns.crs_out if ns.crs_out else CONFIG["CRS_OUT"]
    ns.min_height_m = ns.min_height_m if ns.min_height_m is not None else CONFIG["MIN_HEIGHT_M"]
    ns.max_sig_e = ns.max_sig_e if ns.max_sig_e is not None else CONFIG["MAX_SIG_E"]
    ns.max_sig_n = ns.max_sig_n if ns.max_sig_n is not None else CONFIG["MAX_SIG_N"]
    ns.max_sig_v = ns.max_sig_v if ns.max_sig_v is not None else CONFIG["MAX_SIG_V"]

    if ns.no_fix_only:
        ns.fix_only = False
    elif ns.fix_only:
        ns.fix_only = True
    else:
        ns.fix_only = bool(CONFIG["FIX_ONLY"])

    ns.sow_tol_s = ns.sow_tol_s if ns.sow_tol_s is not None else CONFIG["SOW_MATCH_TOL_S"]
    ns.max_bad_rate = ns.max_bad_rate if ns.max_bad_rate is not None else CONFIG["MAX_BAD_RATE"]

    ns.enforce_single_calibration_and_lens_group = (
        True if ns.enforce_single_calibration_and_lens_group
        else bool(CONFIG["ENFORCE_SINGLE_CALIB_AND_LENS_GROUP"])
    )
    return ns


# ============================================================
# Main
# ============================================================

def main():
    ns = parse_args_or_defaults()

    out_root = Path(ns.out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    log = Logger(out_root / "run_log.txt")

    log.log("=== MRK2RC start ===")
    log.log(f"Python: {sys.executable}")
    log.log(f"OUT_ROOT: {out_root}")
    log.log(f"RSPROJ:   {ns.rsproj or '(none – disk-path mode)'}")
    log.log(f"CRS_OUT:  {ns.crs_out}")
    log.log(f"Filters:  minH={ns.min_height_m}, sigE<={ns.max_sig_e}, sigN<={ns.max_sig_n}, sigV<={ns.max_sig_v}")
    log.log(f"FIX_ONLY: {ns.fix_only} (tag='{CONFIG['FIX_ONLY_TAG']}')")
    log.log(f"SOW matching: tol={ns.sow_tol_s}s, max_bad_rate={ns.max_bad_rate:.2f}")
    log.log(f"Enforce single calib+lens group: {ns.enforce_single_calibration_and_lens_group}")

    # ------------------------------------------------------------------
    # Optional RealityScan project
    # ------------------------------------------------------------------
    rsproj_path: Optional[Path] = Path(ns.rsproj) if ns.rsproj else None
    if rsproj_path is not None:
        ensure_exists(log, rsproj_path, "RealityScan project")
        proj_paths = extract_project_image_paths(rsproj_path, CONFIG["IMAGE_EXTS"])
        log.log(f"Project image paths extracted from rsproj: {len(proj_paths)}")
        if not proj_paths:
            abort(log, "Could not extract any image paths from rsproj. Is this the correct project file?")
        proj_index = build_project_basename_index(proj_paths)
    else:
        log.log("[INFO] No RSPROJ configured – running in disk-path mode.")
        proj_paths = []
        proj_index = {}

    roots = [Path(p) for p in ns.roots]
    for r in roots:
        ensure_exists(log, r, "Root/MRK input")

    # Global image inventory (used to initialise the untrusted set)
    all_images_disk: List[Path] = []
    for r in roots:
        img_root = r.parent if (r.is_file() and r.suffix.lower() == ".mrk") else r
        all_images_disk.extend(build_image_inventory_recursive(img_root, CONFIG["IMAGE_EXTS"]))
    all_images_disk = dedup_preserve(sorted(all_images_disk, key=lambda p: natural_key(str(p))))
    log.log(f"All images discovered on disk (roots union): {len(all_images_disk)}")

    # MRK discovery
    mrk_files: List[Path] = []
    for r in roots:
        mrk_files.extend(discover_mrk_files_from_input(r))
    mrk_files = sorted(set(mrk_files))
    log.log(f"MRK files found: {len(mrk_files)}")

    trusted_disk: set[Path] = set()
    untrusted_disk: set[Path] = set(all_images_disk)
    traj_by_disk: Dict[Path, Tuple[float, float, float, float, float, float]] = {}

    for mrk in tqdm(mrk_files, desc="Processing MRKs"):
        if not mrk.exists():
            continue

        image_root = mrk.parent

        recs_all = parse_timestamp_mrk(mrk)
        if not recs_all:
            continue

        recs_used = [r for r in recs_all if (not ns.fix_only or r.fix_tag == CONFIG["FIX_ONLY_TAG"])]
        if not recs_used:
            continue

        # ------------------------------------------------------------------
        # Build the seq->image map across the MRK folder and related
        # sibling folders (same DJI session ID, or non-DJI named folders).
        # ------------------------------------------------------------------
        search_folders = neighbor_search_folders(image_root)

        log.log(
            f"[SCAN] {mrk.name}: searching {len(search_folders)} folder(s): "
            + ", ".join(f.name for f in search_folders)
        )

        seq_map = build_seq_image_map(search_folders, CONFIG["IMAGE_EXTS"])

        if not seq_map:
            log.log(f"[SKIP] {mrk.name}: no images with DJI sequence numbers found.")
            continue

        # ------------------------------------------------------------------
        # Match by sequence number, cross-validate with SOW
        # ------------------------------------------------------------------
        pairs, offset_s, n_deleted, n_sow_fail = match_by_seq_and_sow(
            recs_used, seq_map, ns.sow_tol_s, log, mrk.name
        )

        if not pairs:
            log.log(f"[SKIP] {mrk.name}: no image-MRK pairs could be established.")
            continue

        bad_rate = n_sow_fail / max(1, len(pairs))
        if bad_rate > ns.max_bad_rate:
            log.log(
                f"[SKIP] {mrk.name}: SOW validation failures too high "
                f"({n_sow_fail}/{len(pairs)} = {bad_rate:.1%}). Keeping untrusted."
            )
            continue

        # Write per-MRK diagnostic CSV (always, regardless of rsproj)
        diag_csv = out_root / "diagnostics" / (mrk.stem + ".matched.csv")
        write_match_diagnostics_csv(diag_csv, recs_used, pairs, n_deleted)

        # ------------------------------------------------------------------
        # Promote trustworthy images
        # ------------------------------------------------------------------
        newly_trusted = 0
        for rec, img in pairs:
            if not is_trustworthy(rec, ns.min_height_m, ns.max_sig_e, ns.max_sig_n, ns.max_sig_v):
                continue
            try:
                X, Y = to_output_xy(rec.lat, rec.lon, ns.crs_out)
            except Exception:
                continue

            trusted_disk.add(img)
            untrusted_disk.discard(img)
            traj_by_disk[img] = (X, Y, rec.ellh, rec.sig_e, rec.sig_n, rec.sig_v)
            newly_trusted += 1

        folders_used = sorted({img.parent.name for _, img in pairs})
        log.log(
            f"[OK] {mrk.name}: "
            f"mrk_recs={len(recs_used)} pairs={len(pairs)} deleted={n_deleted} "
            f"sow_fail={n_sow_fail} offset={offset_s:.3f}s "
            f"newly_trusted={newly_trusted} "
            f"folders={folders_used}"
        )

    # ------------------------------------------------------------------
    # Output
    # ------------------------------------------------------------------
    all_trusted_disk = sorted(trusted_disk, key=lambda p: natural_key(str(p)))
    all_untrusted_disk = sorted(untrusted_disk, key=lambda p: natural_key(str(p)))

    traj_dir = out_root / "trajectories"
    traj_dir.mkdir(parents=True, exist_ok=True)
    trusted_list_path = traj_dir / "AllTrustedCameras.imagelist"
    untrusted_list_path = traj_dir / "AllUntrustedCameras.imagelist"
    trajectories_tsv_path = traj_dir / "AllTrajectories.tsv"

    if rsproj_path is not None:
        # Project-path mode: map disk paths to paths as stored in the .rsproj
        trusted_proj, dropped_t = map_disk_paths_to_project_paths(
            all_trusted_disk, proj_index, log, "Trusted mapping"
        )
        untrusted_proj, dropped_u = map_disk_paths_to_project_paths(
            all_untrusted_disk, proj_index, log, "Untrusted mapping"
        )

        trusted_set_proj = set(trusted_proj)
        untrusted_proj = [p for p in untrusted_proj if p not in trusted_set_proj]

        traj_rows_proj: List[Tuple[str, float, float, float, float, float, float]] = []
        for disk_path in all_trusted_disk:
            if disk_path not in traj_by_disk:
                continue
            base = disk_path.name.lower()
            cands = proj_index.get(base, [])
            if len(cands) != 1:
                continue
            proj_path_str = cands[0]

            # --- normalize project path for TSV too (expand ..\..\ relative paths) ---
            pp = Path(proj_path_str.strip().strip('"'))
            if not pp.is_absolute():
                pp = (rsproj_path.parent / pp).resolve()
            proj_path_str = str(pp).replace("/", "\\")
            
            X, Y, alt, sigE, sigN, sigV = traj_by_disk[disk_path]
            traj_rows_proj.append((proj_path_str, X, Y, alt, sigE, sigN, sigV))

        write_imagelist_strings(trusted_list_path, trusted_proj)
        write_imagelist_strings(untrusted_list_path, untrusted_proj)
        write_trajectory_tsv_no_header(trajectories_tsv_path, traj_rows_proj)

        bat_path = out_root / "apply_priors_and_groups.bat"
        write_bat_apply_all(
            out_bat=bat_path,
            rs_exe=ns.rs_exe,
            rsproj=rsproj_path,
            trusted_list=trusted_list_path,
            untrusted_list=untrusted_list_path,
            enforce_groups=ns.enforce_single_calibration_and_lens_group,
        )
        log.log(f"[BAT] Wrote: {bat_path}")
        log.log(f"Trusted cameras (project-mapped):   {len(trusted_proj)} -> {trusted_list_path}")
        log.log(f"Untrusted cameras (project-mapped): {len(untrusted_proj)} -> {untrusted_list_path}")
        log.log(f"Trajectory rows (project-mapped):   {len(traj_rows_proj)} -> {trajectories_tsv_path}")

    else:
        # Disk-path mode: write lists directly with filesystem paths
        trusted_disk_strs = [str(p) for p in all_trusted_disk]
        untrusted_disk_strs = [str(p) for p in all_untrusted_disk]

        traj_rows_disk: List[Tuple[str, float, float, float, float, float, float]] = []
        for disk_path in all_trusted_disk:
            if disk_path not in traj_by_disk:
                continue
            X, Y, alt, sigE, sigN, sigV = traj_by_disk[disk_path]
            traj_rows_disk.append((str(disk_path), X, Y, alt, sigE, sigN, sigV))

        write_imagelist_strings(trusted_list_path, trusted_disk_strs)
        write_imagelist_strings(untrusted_list_path, untrusted_disk_strs)
        write_trajectory_tsv_no_header(trajectories_tsv_path, traj_rows_disk)

        log.log(f"Trusted cameras (disk paths):   {len(trusted_disk_strs)} -> {trusted_list_path}")
        log.log(f"Untrusted cameras (disk paths): {len(untrusted_disk_strs)} -> {untrusted_list_path}")
        log.log(f"Trajectory rows (disk paths):   {len(traj_rows_disk)} -> {trajectories_tsv_path}")
        log.log("[INFO] No RSPROJ – skipped .bat generation.")

    log.log("=== MRK2RC done ===")
    log.close()


if __name__ == "__main__":
    main()
