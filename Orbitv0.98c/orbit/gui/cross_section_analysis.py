import os
import cv2
import numpy as np
import math
from matplotlib import pyplot as plt

def debug_print(*args, **kwargs) -> None:
    try:
        from ..io.data_parser import DEBUG_PRINT
        if DEBUG_PRINT:
            print(*args, **kwargs)
    except ImportError:
        try:
            import sys
            main_module = sys.modules.get('__main__')
            if hasattr(main_module, 'DEBUG') and main_module.DEBUG:
                print(*args, **kwargs)
        except:
            pass

def error_print(*args, **kwargs) -> None:
    print(*args, **kwargs)

def _find_contours(mask):
    """
    OpenCV 4: (contours, hierarchy)
    OpenCV 3: (image, contours, hierarchy)
    """
    res = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return res[0] if len(res) == 2 else res[1]

def process_crosssection_image(crosssection_dir, input_scale_meters, epsilon_factor):
    try:
        # ---- Input / file safety
        if not os.path.exists(crosssection_dir):
            raise FileNotFoundError(f"Cross-section image not found: {crosssection_dir}")

        image = cv2.imread(crosssection_dir, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"cv2.imread returned None for: {crosssection_dir}")

        # ---- HSV thresholds
        lower_green_hsv = np.array([40, 50, 50])
        upper_green_hsv = np.array([80, 255, 255])
        lower_blue_hsv  = np.array([100, 50, 50])
        upper_blue_hsv  = np.array([140, 255, 255])

        hsv_image = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        blue_mask  = cv2.inRange(hsv_image, lower_blue_hsv,  upper_blue_hsv)
        green_mask = cv2.inRange(hsv_image, lower_green_hsv, upper_green_hsv)

        # For BLUE (cross-section): small CLOSE to connect gaps
        kernel = np.ones((3,3), np.uint8)
        blue_mask = cv2.morphologyEx(blue_mask, cv2.MORPH_CLOSE, kernel, iterations=1)

        # For GREEN (scale): DO NOT open/erode — it can kill thin lines.
        # Try contours directly; if none, dilate once and try again.
        contours_green = _find_contours(green_mask)
    
        if not contours_green:
            raise RuntimeError("No GREEN scale-line detected. Check HSV thresholds or template graphics.")

        scale_line_contour = max(contours_green, key=lambda c: cv2.arcLength(c, False))
        rect = cv2.minAreaRect(scale_line_contour)
        (w, h) = rect[1]  # width, height in pixels of the min area rectangle
        scale_length_pixels = max(w, h)
        if scale_length_pixels <= 0:
            raise RuntimeError("Detected scale-line has zero length; cannot compute pixel→meter ratio.")

        pixel_to_meter_ratio = float(input_scale_meters) / float(scale_length_pixels)

        # ---- Find cross-section (blue)
        contours_blue = _find_contours(blue_mask)
        if not contours_blue:
            raise RuntimeError("No BLUE cross-section contour detected. Check HSV thresholds or template graphics.")

        cross_section_contour = max(contours_blue, key=cv2.contourArea)

        # ---- Approximate polygon safely
        peri = cv2.arcLength(cross_section_contour, True)
        # ensure epsilon is at least 1px to avoid degenerate outputs on tiny shapes
        epsilon = max(1.0, float(epsilon_factor) * float(peri))
        approx_polygon = cv2.approxPolyDP(cross_section_contour, epsilon, True)

        if len(approx_polygon) < 3:
            raise RuntimeError(f"approxPolyDP returned too few points ({len(approx_polygon)}). Try smaller epsilon_factor.")

        # ---- Draw and measure segment lengths
        distances = []
        for i in range(len(approx_polygon)):
            p1 = approx_polygon[i][0]
            p2 = approx_polygon[(i + 1) % len(approx_polygon)][0]
            cv2.line(image, tuple(p1), tuple(p2), (0, 0, 255), 2)
            distance_m = float(np.linalg.norm(p1 - p2)) * pixel_to_meter_ratio
            distances.append(distance_m)
            mid = ((p1[0] + p2[0]) // 2, (p1[1] + p2[1]) // 2)
            cv2.putText(image, f"{distance_m:.2f}", mid, cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200,200,200), 2)

        # ---- Transform to cross-section coords (metres)
        mid_x = image.shape[1] // 2
        top_y = int(np.min(approx_polygon[:, 0, 1]))
        midpoint = np.array([mid_x, top_y], dtype=float)

        transformed_points = np.zeros((len(approx_polygon), 2), dtype=float)
        for i, pt in enumerate(approx_polygon[:,0,:]):  # (x,y) in image pixels
            x_offset = (pt[0] - midpoint[0]) * pixel_to_meter_ratio
            y_offset = (pt[1] - midpoint[1]) * pixel_to_meter_ratio
            transformed_points[i] = [x_offset, y_offset]
            if i < 5:
                debug_print(f"[XSEC] P{i:02d}: img=({pt[0]},{pt[1]})  →  x={x_offset:.3f} m , y={y_offset:.3f} m")

        return image, transformed_points

    except Exception as e:
        import traceback
        error_print(f"Error in process_crosssection_image: {e}")
        traceback.print_exc()
        return None, None

def calculate_maximum_width(points):
    """
    Max pairwise distance in the XY plane (metres).
    Accepts list/np.array of shape (N,2).
    """
    pts = np.asarray(points, dtype=float)
    if pts.ndim != 2 or pts.shape[1] != 2 or len(pts) == 0:
        return 0.0
    max_d = 0.0
    for i in range(len(pts)-1):
        diffs = pts[i+1:] - pts[i]
        if diffs.size:
            dists = np.hypot(diffs[:,0], diffs[:,1])
            local_max = float(dists.max(initial=0.0))
            if local_max > max_d:
                max_d = local_max
    return max_d
