# -*- coding: utf-8 -*-
"""
TorahNotesOCR - Offline Hebrew OCR Engine (v1.4.2)
Wraps the Mishkefet-v1 CTC neural recognizer for Hebrew handwriting,
providing:
- 4-point perspective dewarping ("CamScanner" flatten) & dark-desk cropping
  with pixel-exact inverse coordinate mapping back to displayed viewer pixels
- Automatic Looseleaf Paper Cleaner:
    * 1.2% edge inset eliminating dark desk slivers along paper borders
    * Automatic circular black binder-hole detection & white-paper fill
    * Automatic vertical red margin-line detection & ink-preserving removal
    * Automatic pale-blue horizontal ruled-line detection & suppression
- Shadow lighting normalization (optional full LAB background flattening)
- Sideways landscape auto-orientation & 180° upside-down verification
- Open two-page notebook spread detection & RTL splitting (Right Page -> Left Page)
- Region-of-Interest (ROI) partial/margin-note recognition
- Fast (Greedy) vs. High-Accuracy (Beam Search) decoding toggle
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Any, Callable, Optional, Tuple
import cv2
import numpy as np
from PIL import Image, ImageEnhance, ImageOps


def _order_quad_points(pts: np.ndarray) -> np.ndarray:
    """Orders 4 corner points into [top-left, top-right, bottom-right, bottom-left]."""
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def _map_box_to_original(box: Optional[dict], coord_info: Optional[dict], orig_w: int, orig_h: int) -> Optional[dict]:
    """
    Maps a bounding box dict {'x','y','w','h'} from cropped/perspective-warped OCR space
    back into exact original displayed-image coordinates so DocumentViewer highlights align pixel-for-pixel.
    """
    if not box or not isinstance(box, dict) or not coord_info:
        return box
    try:
        x = float(box.get("x", 0))
        y = float(box.get("y", 0))
        bw = float(box.get("w", 0))
        bh = float(box.get("h", 0))

        # Undo any inner safety border inset first
        inset_x = float(coord_info.get("inset_x", 0.0))
        inset_y = float(coord_info.get("inset_y", 0.0))
        x += inset_x
        y += inset_y

        mode = coord_info.get("mode", "identity")
        if mode == "perspective" and coord_info.get("M_inv") is not None:
            M_inv = coord_info["M_inv"]
            corners = np.array([
                [[x, y]],
                [[x + bw, y]],
                [[x + bw, y + bh]],
                [[x, y + bh]]
            ], dtype="float32")
            mapped = cv2.perspectiveTransform(corners, M_inv).reshape(4, 2)
            min_x = max(0.0, float(np.min(mapped[:, 0])))
            min_y = max(0.0, float(np.min(mapped[:, 1])))
            max_x = min(float(orig_w), float(np.max(mapped[:, 0])))
            max_y = min(float(orig_h), float(np.max(mapped[:, 1])))
            return {
                "x": int(round(min_x)),
                "y": int(round(min_y)),
                "w": max(1, int(round(max_x - min_x))),
                "h": max(1, int(round(max_y - min_y)))
            }
        elif mode == "crop":
            ox = float(coord_info.get("offset_x", 0.0))
            oy = float(coord_info.get("offset_y", 0.0))
            nx = max(0.0, x + ox)
            ny = max(0.0, y + oy)
            nw = min(float(orig_w) - nx, bw)
            nh = min(float(orig_h) - ny, bh)
            return {
                "x": int(round(nx)),
                "y": int(round(ny)),
                "w": max(1, int(round(nw))),
                "h": max(1, int(round(nh)))
            }
    except Exception:
        pass
    return box


class OCREngine:
    def __init__(self, model_dir: Optional[str] = None):
        self.model_dir = model_dir or self._resolve_model_dir()
        self.checkpoint_path = os.path.join(self.model_dir, "mishkefet-v1.pt")
        self._recognizer = None
        self._is_loaded = False
        self.high_accuracy_mode = False
        self.clean_shadows_lines = False
        self.clean_looseleaf = True  # Auto-remove binder holes, red margin line & pale blue ruled lines
        self.check_upside_down = True

    def _resolve_model_dir(self) -> str:
        """Finds model assets in custom dir, frozen bundle, or local folder."""
        env_model_dir = os.environ.get("OHR_HAKSAV_MODEL_DIR") or os.environ.get("KSAV_KOOKER_MODEL_DIR")
        if env_model_dir and os.path.exists(os.path.join(env_model_dir, "mishkefet-v1.pt")):
            return env_model_dir

        if getattr(sys, 'frozen', False):
            base_dir = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        candidates = [
            os.path.join(base_dir, "model_assets"),
            os.path.join(base_dir, "models"),
            base_dir,
            os.path.expanduser(r"~/.cache/huggingface/hub/models--itayinbar--Mishkefet-v1/snapshots/16380452d62839f369c36f17312c94d5d1af1768")
        ]
        for c in candidates:
            if os.path.exists(os.path.join(c, "mishkefet-v1.pt")):
                return c
        return candidates[0]

    def load_model(self):
        """Loads model into memory if not already loaded."""
        if self._is_loaded and self._recognizer is not None:
            return

        if not os.path.exists(self.checkpoint_path):
            raise FileNotFoundError(
                f"Mishkefet model checkpoint not found at: {self.checkpoint_path}.\n"
                f"Please run 'python scripts/download_model.py' to download the weights from GitHub Releases."
            )

        from core.hebocr.recognize import Recognizer
        beam_w = 5 if self.high_accuracy_mode else 0
        self._recognizer = Recognizer(self.checkpoint_path, device="cpu", beam_width=beam_w)
        self._is_loaded = True

    def set_accuracy_mode(self, high_accuracy: bool):
        """Switches between Fast Greedy (beam=0) and High-Accuracy Beam Search (beam=5) live."""
        self.high_accuracy_mode = bool(high_accuracy)
        if self._recognizer is not None:
            self._recognizer.beam_width = 5 if self.high_accuracy_mode else 0

    def is_ready(self) -> bool:
        return self._is_loaded and self._recognizer is not None

    def crop_document_if_desk_with_map(self, img: Image.Image) -> Tuple[Image.Image, dict]:
        """
        Detects if an image is a page photographed on a darker table/desk background.
        Applies 4-point perspective dewarp ("CamScanner" flatten) when tilted, or clean crop.
        Trims a ~1.2% safety inset inside the paper edge so dark desk slivers never create phantom edge letters.
        Returns (cropped_img, coord_info) for exact inverse bounding-box mapping.
        """
        coord_info = {"mode": "identity", "inset_x": 0, "inset_y": 0}
        try:
            arr = np.array(img.convert("RGB"))
            gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
            h, w = gray.shape

            scale = 800.0 / max(h, w) if max(h, w) > 800 else 1.0
            if scale < 1.0:
                small_gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
            else:
                small_gray = gray

            sh, sw = small_gray.shape
            small_area = sh * sw

            border_thickness = max(2, int(min(sh, sw) * 0.03))
            top = small_gray[:border_thickness, :]
            bottom = small_gray[-border_thickness:, :]
            left = small_gray[:, :border_thickness]
            right = small_gray[:, -border_thickness:]
            border_pixels = np.concatenate([top.ravel(), bottom.ravel(), left.ravel(), right.ravel()])
            border_mean = float(np.mean(border_pixels))
            center_mean = float(np.mean(small_gray[int(sh * 0.25) : int(sh * 0.75), int(sw * 0.25) : int(sw * 0.75)]))

            if center_mean - border_mean > 25.0:
                blurred = cv2.GaussianBlur(small_gray, (5, 5), 0)
                split_thresh = int(border_mean + (center_mean - border_mean) * 0.4)
                _, thresh = cv2.threshold(blurred, split_thresh, 255, cv2.THRESH_BINARY)

                kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
                thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

                contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                if contours:
                    largest = max(contours, key=cv2.contourArea)
                    c_area = cv2.contourArea(largest)
                    if c_area > 0.22 * small_area:
                        peri = cv2.arcLength(largest, True)
                        approx = cv2.approxPolyDP(largest, 0.025 * peri, True)
                        if len(approx) == 4 and cv2.isContourConvex(approx):
                            pts_small = approx.reshape(4, 2).astype("float32")
                            rect_small = _order_quad_points(pts_small)
                            rect_orig = rect_small / scale

                            (tl, tr, br, bl) = rect_orig
                            width_a = np.linalg.norm(br - bl)
                            width_b = np.linalg.norm(tr - tl)
                            max_w = int(max(width_a, width_b))

                            height_a = np.linalg.norm(tr - br)
                            height_b = np.linalg.norm(tl - bl)
                            max_h = int(max(height_a, height_b))

                            top_tilt = abs(tr[1] - tl[1]) / max(1.0, max_w)
                            side_tilt = abs(br[0] - tr[0]) / max(1.0, max_h)
                            if max_w > 0.35 * w and max_h > 0.35 * h and (top_tilt > 0.02 or side_tilt > 0.02):
                                dst = np.array([
                                    [0, 0],
                                    [max_w - 1, 0],
                                    [max_w - 1, max_h - 1],
                                    [0, max_h - 1]
                                ], dtype="float32")
                                M = cv2.getPerspectiveTransform(rect_orig, dst)
                                M_inv = np.linalg.inv(M)
                                warped = cv2.warpPerspective(arr, M, (max_w, max_h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)

                                # Trim safety border inset so dark desk edges never bleed into OCR,
                                # using a tiny top inset (0.3%) to preserve top-corner "בס\"ד" headers
                                ix = max(4, int(max_w * 0.012))
                                iy_top = max(2, int(max_h * 0.003))
                                iy_bot = max(4, int(max_h * 0.010))
                                if max_w - 2 * ix > 100 and max_h - (iy_top + iy_bot) > 100:
                                    warped = warped[iy_top : max_h - iy_bot, ix : max_w - ix]
                                else:
                                    ix, iy_top = 0, 0

                                coord_info = {
                                    "mode": "perspective",
                                    "M_inv": M_inv,
                                    "inset_x": ix,
                                    "inset_y": iy_top
                                }
                                try:
                                    from core.logger import log
                                    log.info(f"Perspective dewarp applied: flattened {w}x{h} -> {warped.shape[1]}x{warped.shape[0]}")
                                except Exception:
                                    pass
                                return Image.fromarray(warped), coord_info

                        # Fallback: clean bounding-box crop with 1% inward trim against dark edges
                        x, y, cw, ch = cv2.boundingRect(largest)
                        orig_x = max(0, int(x / scale))
                        orig_y = max(0, int(y / scale))
                        orig_w = min(w - orig_x, int(cw / scale))
                        orig_h = min(h - orig_y, int(ch / scale))
                        if orig_w > 0.3 * w and orig_h > 0.3 * h:
                            ix = max(2, int(orig_w * 0.008))
                            iy = max(2, int(orig_h * 0.008))
                            cx1 = min(w - 1, orig_x + ix)
                            cy1 = min(h - 1, orig_y + iy)
                            cx2 = max(cx1 + 50, orig_x + orig_w - ix)
                            cy2 = max(cy1 + 50, orig_y + orig_h - iy)
                            coord_info = {
                                "mode": "crop",
                                "offset_x": cx1,
                                "offset_y": cy1,
                                "inset_x": 0,
                                "inset_y": 0
                            }
                            return img.crop((cx1, cy1, cx2, cy2)), coord_info
        except Exception:
            pass
        return img, coord_info

    def crop_document_if_desk(self, img: Image.Image) -> Image.Image:
        """Backward-compatible wrapper returning just the cropped/warped PIL image."""
        cropped, _ = self.crop_document_if_desk_with_map(img)
        return cropped

    def clean_looseleaf_artifacts(self, img: Image.Image) -> Tuple[Image.Image, Optional[int]]:
        """
        Automatically cleans standard looseleaf notebook artifacts WITHOUT erasing real ink:
          1. Circular dark binder holes in left/right 14% margins -> filled with local paper color
          2. Vertical red looseleaf margin line -> red/pink pixels lifted to paper white (preserving crossing ink!)
          3. Pale blue horizontal ruled lines (when detected) -> gently lifted to paper white so baseline lines
             do not turn cursive 'כ' into 'ב'.
        Returns (cleaned_img, red_margin_x_or_None).
        """
        red_margin_x = None
        try:
            rgb = np.array(img.convert("RGB"))
            h, w, _ = rgb.shape
            if h < 200 or w < 200:
                return img, None

            # Estimate bright paper background color (75th percentile in center region)
            center_patch = rgb[int(h * 0.15) : int(h * 0.85), int(w * 0.20) : int(w * 0.85)]
            paper_rgb = np.percentile(center_patch.reshape(-1, 3), 75, axis=0).astype(np.uint8)
            gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)

            # 1. Detect & fill dark circular binder holes in left 14% and right 14% strips
            # Uses MORPH_OPEN with an elliptical kernel so thin pale-blue ruled lines never fuse with dark holes!
            margin_w = int(w * 0.14)
            page_area = float(h * w)
            min_hole_area = max(120.0, page_area * 0.00035)
            max_hole_area = page_area * 0.0075

            holes_removed = 0
            open_k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (13, 13))
            close_k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
            for x_off in (0, w - margin_w):
                strip = gray[:, x_off : x_off + margin_w]
                # Threshold below paper brightness; MORPH_OPEN((13,13)) wipes out thin ruled lines cleanly
                dark_thresh = min(148, max(55, int(np.percentile(strip, 65)) - 70))
                _, mask = cv2.threshold(strip, dark_thresh, 255, cv2.THRESH_BINARY_INV)
                mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, open_k)
                mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, close_k)
                contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                for cnt in contours:
                    area = cv2.contourArea(cnt)
                    if min_hole_area <= area <= max_hole_area:
                        bx, by, bw, bh = cv2.boundingRect(cnt)
                        aspect = bw / max(1.0, float(bh))
                        peri = cv2.arcLength(cnt, True)
                        circ = (4.0 * np.pi * area / (peri * peri)) if peri > 0 else 0.0
                        fill_ratio = area / max(1.0, float(bw * bh))
                        if 0.55 <= aspect <= 1.85 and circ >= 0.42 and fill_ratio >= 0.52:
                            cx = x_off + bx + bw // 2
                            cy = by + bh // 2
                            rad = int(max(bw, bh) * 0.68) + 6
                            # Estimate local paper color from surrounding neighborhood so shadowed margins blend cleanly
                            py1 = max(0, cy - rad - 24)
                            py2 = min(h, cy + rad + 24)
                            px1 = max(0, cx - rad - 24)
                            px2 = min(w, cx + rad + 24)
                            local_patch = rgb[py1:py2, px1:px2]
                            local_gray = gray[py1:py2, px1:px2]
                            bright_px = local_patch[local_gray > dark_thresh + 25]
                            fill_rgb = (
                                np.percentile(bright_px, 75, axis=0).astype(np.uint8)
                                if len(bright_px) >= 40
                                else paper_rgb
                            )
                            cv2.circle(rgb, (cx, cy), rad, tuple(int(c) for c in fill_rgb), -1)
                            holes_removed += 1

            # Recompute float channels after hole filling
            r_f = rgb[:, :, 0].astype(np.float32)
            g_f = rgb[:, :, 1].astype(np.float32)
            b_f = rgb[:, :, 2].astype(np.float32)
            redness = r_f - 0.5 * (g_f + b_f)

            # 2. Detect & surgically remove vertical red/pink looseleaf margin line
            # Tracks slight page tilt across vertical bands and adapts to shaded paper!
            col_red = redness.mean(axis=0)
            med_red = float(np.median(col_red))

            left_lim = int(w * 0.25)
            cand_x = int(np.argmax(col_red[:left_lim]))
            red_line_x_per_row = None
            if float(col_red[cand_x]) > med_red + 6.5:
                red_margin_x = cand_x
                # Fit a linear track x(y) across 6 vertical bands to follow slightly slanted red margin lines
                band_pts_y = []
                band_pts_x = []
                n_bands = 6
                band_h = max(1, h // n_bands)
                search_x1 = max(0, cand_x - 45)
                search_x2 = min(left_lim, cand_x + 46)
                for b_idx in range(n_bands):
                    by1 = b_idx * band_h
                    by2 = h if b_idx == n_bands - 1 else (b_idx + 1) * band_h
                    b_col = redness[by1:by2, search_x1:search_x2].mean(axis=0)
                    if b_col.size > 0:
                        rel_x = int(np.argmax(b_col))
                        if float(b_col[rel_x]) > med_red + 5.5:
                            band_pts_y.append(0.5 * (by1 + by2))
                            band_pts_x.append(float(search_x1 + rel_x))

                ys = np.arange(h, dtype=np.float32)
                if len(band_pts_y) >= 2:
                    slope, intercept = np.polyfit(band_pts_y, band_pts_x, 1)
                    red_line_x_per_row = np.clip(slope * ys + intercept, 0, w - 1)
                else:
                    red_line_x_per_row = np.full(h, float(cand_x), dtype=np.float32)

                # Erase red/pink margin pixels within ±16px of tracked x(y) using local paper fill
                chunk_h = 64
                for cy1 in range(0, h, chunk_h):
                    cy2 = min(h, cy1 + chunk_h)
                    cx_mid = int(round(float(np.mean(red_line_x_per_row[cy1:cy2]))))
                    bx1 = max(0, cx_mid - 16)
                    bx2 = min(w, cx_mid + 17)
                    band_red = redness[cy1:cy2, bx1:bx2]
                    band_r = r_f[cy1:cy2, bx1:bx2]
                    band_g = g_f[cy1:cy2, bx1:bx2]
                    band_b = b_f[cy1:cy2, bx1:bx2]
                    red_px_mask = (band_red > 12.0) & ((band_r - band_b) > 10.0) & ((band_r - band_g) > 8.0)
                    if np.any(red_px_mask):
                        red_u8 = (red_px_mask.astype(np.uint8) * 255)
                        red_u8 = cv2.dilate(red_u8, np.ones((1, 3), np.uint8))
                        # Protect dark blue/black handwriting ink (which never has high redness),
                        # while still erasing dark-red margin segments in shadows!
                        dark_ink = (gray[cy1:cy2, bx1:bx2] < 115) & (band_red < 15.0)
                        erase_mask = (red_u8 > 0) & (~dark_ink)
                        if np.any(erase_mask):
                            # Local paper color from clean pixels immediately adjacent to the red line
                            sample_x1 = min(w - 1, bx2 + 4)
                            sample_x2 = min(w, bx2 + 28)
                            local_bg = rgb[cy1:cy2, sample_x1:sample_x2]
                            local_fill = (
                                np.percentile(local_bg.reshape(-1, 3), 75, axis=0).astype(np.uint8)
                                if local_bg.size >= 30
                                else paper_rgb
                            )
                            rgb[cy1:cy2, bx1:bx2][erase_mask] = local_fill

            # 3. Clean pale-blue ruled lines ONLY inside the empty left margin (strictly left of red_margin_x)
            # using local vertical-chunk paper colors so shaded margins blend seamlessly without white stripes,
            # while preserving 100% of faint blue ballpoint pen strokes inside the main writing area!
            if red_margin_x is not None and red_margin_x > 20:
                blue_excess = b_f - r_f
                chunk_h = 64
                for cy1 in range(0, h, chunk_h):
                    cy2 = min(h, cy1 + chunk_h)
                    cx_lim = int(round(float(np.min(red_line_x_per_row[cy1:cy2])))) - 2 if red_line_x_per_row is not None else (red_margin_x - 2)
                    if cx_lim <= 10:
                        continue
                    chunk_rgb = rgb[cy1:cy2, :cx_lim]
                    chunk_gray = gray[cy1:cy2, :cx_lim]
                    hsv_left = cv2.cvtColor(chunk_rgb, cv2.COLOR_RGB2HSV)
                    hl, sl, vl = cv2.split(hsv_left)
                    left_blue = (
                        (hl >= 85) & (hl <= 138) &
                        (sl >= 14) & (sl <= 185) &
                        (vl >= 115) &
                        (blue_excess[cy1:cy2, :cx_lim] >= 6.0) &
                        (chunk_gray >= 110)
                    )
                    if np.any(left_blue):
                        non_blue = chunk_rgb[(~left_blue) & (chunk_gray >= 115)]
                        local_fill = (
                            np.percentile(non_blue, 70, axis=0).astype(np.uint8)
                            if len(non_blue) >= 40
                            else paper_rgb
                        )
                        chunk_rgb[left_blue] = local_fill

            if holes_removed > 0 or red_margin_x is not None:
                try:
                    from core.logger import log
                    log.info(f"Looseleaf cleaner: erased {holes_removed} binder hole(s), red_margin_x={red_margin_x}")
                except Exception:
                    pass

            return Image.fromarray(rgb), red_margin_x
        except Exception:
            return img, None

    def clean_shadows_and_lines(self, img: Image.Image) -> Image.Image:
        """
        Normalizes uneven desk-lamp lighting/shadows and gently suppresses pale blue/cyan
        looseleaf ruled lines while preserving dark pen and pencil handwriting strokes.
        """
        try:
            rgb = np.array(img.convert("RGB"))

            hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
            h_ch, s_ch, v_ch = cv2.split(hsv)
            blue_line_mask = (h_ch >= 88) & (h_ch <= 135) & (s_ch >= 22) & (s_ch <= 160) & (v_ch >= 140)
            cleaned = rgb.copy()
            cleaned[blue_line_mask] = np.clip(cleaned[blue_line_mask].astype(np.int32) + 55, 0, 255).astype(np.uint8)

            lab = cv2.cvtColor(cleaned, cv2.COLOR_RGB2LAB)
            l_ch, a_ch, b_ch = cv2.split(lab)
            dilated = cv2.dilate(l_ch, np.ones((7, 7), np.uint8))
            bg_img = cv2.medianBlur(dilated, 21)
            diff_img = 255 - cv2.absdiff(l_ch, bg_img)
            norm_l = cv2.normalize(diff_img, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_8UC1)
            blended_l = cv2.addWeighted(norm_l, 0.65, l_ch, 0.35, 0)
            merged_lab = cv2.merge([blended_l, a_ch, b_ch])
            out_rgb = cv2.cvtColor(merged_lab, cv2.COLOR_LAB2RGB)
            return Image.fromarray(out_rgb)
        except Exception:
            return img

    def detect_and_split_two_page_spread(self, img: Image.Image, force: bool = False) -> Optional[Tuple[Image.Image, Image.Image]]:
        """
        Detects an open two-page notebook photograph (left + right pages) by locating the
        dark vertical spine gutter in the middle 30% of the image.
        Returns (right_page, left_page) in Hebrew RTL reading order, or None if single page.
        """
        try:
            img_rgb = ImageOps.exif_transpose(img).convert("RGB")
            w, h = img_rgb.size
            if not force and w < h * 1.25:
                return None

            gray = cv2.cvtColor(np.array(img_rgb), cv2.COLOR_RGB2GRAY)
            x_start = int(w * 0.35)
            x_end = int(w * 0.65)
            y_start = int(h * 0.10)
            y_end = int(h * 0.90)
            roi = gray[y_start:y_end, x_start:x_end]

            col_means = np.mean(roi, axis=0)
            k = max(5, int(w * 0.01) | 1)
            smooth = np.convolve(col_means, np.ones(k) / k, mode="same")

            min_idx = int(np.argmin(smooth))
            valley_val = float(smooth[min_idx])
            median_val = float(np.median(smooth))

            if force or (median_val - valley_val >= 16.0):
                split_x = x_start + min_idx
                right_page = img_rgb.crop((split_x, 0, w, h))
                left_page = img_rgb.crop((0, 0, split_x, h))
                return (right_page, left_page)
        except Exception:
            pass
        return None

    def auto_orient_if_sideways(self, img: Image.Image) -> Tuple[Image.Image, bool]:
        """
        Detects if a notebook page was photographed sideways (landscape mode where ruled lines run vertically)
        and automatically rotates it 90 degrees clockwise so Hebrew handwriting lines run horizontally.
        Returns (oriented_img, was_rotated).
        """
        try:
            w, h = img.size
            if w > h * 1.15:
                small = img.convert("L").resize((400, 300))
                arr_sm = np.array(small)
                sob_y = cv2.Sobel(arr_sm, cv2.CV_64F, 0, 1, ksize=3)
                sob_x = cv2.Sobel(arr_sm, cv2.CV_64F, 1, 0, ksize=3)
                y_str = float(np.mean(np.abs(sob_y)))
                x_str = float(np.mean(np.abs(sob_x)))
                if x_str > y_str * 1.08:
                    try:
                        from core.logger import log
                        log.info(f"Auto-orient: Detected sideways notebook page ({w}x{h}, vert_energy={x_str:.1f} > horiz_energy={y_str:.1f}). Rotating 90° CW.")
                    except Exception:
                        pass
                    return img.rotate(270, expand=True), True
        except Exception:
            pass
        return img, False

    def verify_upright_orientation(self, img: Image.Image) -> Tuple[Image.Image, bool]:
        """
        Checks if a page is upside-down (180°) by comparing neural OCR confidence on
        up to 2 middle line crops upright vs. rotated 180°.
        Returns (img, was_flipped_180).
        """
        try:
            if not self.is_ready():
                return img, False
            from core.hebocr.page.segment import segment_page

            crops, _, _ = segment_page(img)
            if not crops:
                return img, False

            mid = len(crops) // 2
            sample = crops[max(0, mid - 1) : min(len(crops), mid + 1)]
            if not sample:
                return img, False

            _, confs_up = self._recognizer.read(sample, return_confidence=True)
            avg_up = float(np.mean(confs_up)) if confs_up else 0.0

            if avg_up >= 0.72:
                return img, False

            sample_flipped = [c.rotate(180) for c in sample]
            _, confs_flip = self._recognizer.read(sample_flipped, return_confidence=True)
            avg_flip = float(np.mean(confs_flip)) if confs_flip else 0.0

            if avg_flip > avg_up + 0.09:
                try:
                    from core.logger import log
                    log.info(f"Auto-orient 180° fix: Upright conf={avg_up:.2f}, Flipped 180° conf={avg_flip:.2f}. Flipping page upright.")
                except Exception:
                    pass
                return img.rotate(180), True
        except Exception:
            pass
        return img, False

    def preprocess_image_with_meta(
        self,
        img: Image.Image,
        enhance_contrast: bool = True,
        auto_crop_desk: bool = True,
        auto_orient: bool = True,
        clean_shadows_lines: Optional[bool] = None
    ) -> Tuple[Image.Image, dict]:
        """
        Cleans and standardizes image for optimal Hebrew handwriting recognition.
        Returns (preprocessed_img, meta_dict) containing inverse coordinate mapping & red_margin_x.
        """
        if img.mode != "RGB":
            img = img.convert("RGB")

        img = ImageOps.exif_transpose(img)
        orig_w, orig_h = img.size

        if auto_orient:
            img, _ = self.auto_orient_if_sideways(img)
            orig_w, orig_h = img.size

        coord_info = {"mode": "identity", "inset_x": 0, "inset_y": 0}
        if auto_crop_desk:
            img, coord_info = self.crop_document_if_desk_with_map(img)

        red_margin_x = None
        if self.clean_looseleaf:
            img, red_margin_x = self.clean_looseleaf_artifacts(img)

        use_clean = self.clean_shadows_lines if clean_shadows_lines is None else clean_shadows_lines
        if use_clean:
            img = self.clean_shadows_and_lines(img)

        if enhance_contrast:
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.30)
            sharpener = ImageEnhance.Sharpness(img)
            img = sharpener.enhance(1.18)

        meta = {
            "coord_info": coord_info,
            "orig_size": (orig_w, orig_h),
            "proc_size": img.size,
            "red_margin_x": red_margin_x
        }
        return img, meta

    def preprocess_image(
        self,
        img: Image.Image,
        enhance_contrast: bool = True,
        auto_crop_desk: bool = True,
        auto_orient: bool = True,
        clean_shadows_lines: Optional[bool] = None
    ) -> Image.Image:
        """Backward-compatible wrapper returning preprocessed image."""
        out, _ = self.preprocess_image_with_meta(
            img,
            enhance_contrast=enhance_contrast,
            auto_crop_desk=auto_crop_desk,
            auto_orient=auto_orient,
            clean_shadows_lines=clean_shadows_lines
        )
        return out

    def recognize_region(
        self,
        image_or_path: Any,
        box: Tuple[int, int, int, int],
        learning_engine = None
    ) -> Dict[str, Any]:
        """
        Recognizes handwriting strictly inside a user-drawn selection box (x, y, w, h).
        Ideal for margin notes (hagahos) or re-scanning a single paragraph.
        """
        self.load_model()
        if isinstance(image_or_path, (str, Path)):
            img = ImageOps.exif_transpose(Image.open(str(image_or_path)))
        else:
            img = image_or_path

        x, y, w, h = [int(v) for v in box]
        iw, ih = img.size
        x1 = max(0, min(x, iw - 1))
        y1 = max(0, min(y, ih - 1))
        x2 = max(x1 + 5, min(x + w, iw))
        y2 = max(y1 + 5, min(y + h, ih))
        crop = img.crop((x1, y1, x2, y2))

        return self.recognize_page(
            crop,
            learning_engine=learning_engine,
            auto_crop_desk=False,
            auto_orient=False,
            verify_180=False
        )

    def recognize_page(
        self,
        image_or_path: Any,
        learning_engine = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
        auto_crop_desk: bool = True,
        auto_orient: bool = True,
        verify_180: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Runs full-page segmentation and OCR recognition on an image,
        filtering looseleaf margin noise and mapping line bounding boxes
        back into exact displayed-image coordinates.
        """
        self.load_model()

        if isinstance(image_or_path, (str, Path)):
            img = Image.open(str(image_or_path))
        else:
            img = image_or_path

        img, meta = self.preprocess_image_with_meta(img, auto_crop_desk=auto_crop_desk, auto_orient=auto_orient)
        proc_w, proc_h = meta["proc_size"]
        orig_w, orig_h = meta["orig_size"]
        coord_info = meta["coord_info"]
        red_margin_x = meta["red_margin_x"]

        do_verify_180 = self.check_upside_down if verify_180 is None else verify_180
        flipped_180 = False
        if do_verify_180:
            if progress_callback:
                progress_callback(5, 100, "Checking page orientation...")
            img, flipped_180 = self.verify_upright_orientation(img)

        if progress_callback:
            progress_callback(10, 100, "Segmenting handwriting lines...")

        raw_results = self._recognizer.read_page(img)

        if isinstance(raw_results, tuple) and len(raw_results) == 2:
            page_transcript, line_records = raw_results
        elif isinstance(raw_results, list):
            line_records = raw_results
            page_transcript = ""
        else:
            line_records = [raw_results]
            page_transcript = ""

        total_lines = len(line_records)
        lines_data = []
        full_text_lines = []
        total_corrections = 0

        for idx, line_item in enumerate(line_records):
            if progress_callback:
                pct = 20 + int((idx / max(1, total_lines)) * 75)
                progress_callback(pct, 100, f"Reading line {idx + 1} of {total_lines}...")

            if isinstance(line_item, dict):
                raw_line_text = str(line_item.get('text', '')).strip()
                confidence = float(line_item.get('confidence', 1.0))
                box = line_item.get('box', None)
                skew = float(line_item.get('skew', 0.0))
            else:
                raw_line_text = getattr(line_item, 'text', str(line_item)).strip()
                confidence = getattr(line_item, 'confidence', 1.0)
                box = getattr(line_item, 'box', None)
                skew = getattr(line_item, 'skew', 0.0)

            if not raw_line_text or raw_line_text.startswith("{'text'") or raw_line_text.startswith("[{'text'"):
                continue

            # Filter out stray border/margin noise boxes (e.g. top dark edge strip or residual left-margin speck)
            if isinstance(box, dict):
                bx = float(box.get("x", 0))
                by = float(box.get("y", 0))
                bw = float(box.get("w", 0))
                bh = float(box.get("h", 0))
                clean_len = len(raw_line_text.replace(" ", "").replace("'", "").replace('"', ""))

                # 1. Tiny 1-2 char sliver hugging the top/bottom paper edge
                if (by < 18 or (by + bh) > proc_h - 12) and clean_len <= 2 and bh < 60:
                    continue

                # 2. Tiny 1-2 char noise blob strictly inside the far-left binder-hole margin (left of red margin line)
                if red_margin_x is not None and (bx + bw) < (red_margin_x - 10) and clean_len <= 3 and bw < proc_w * 0.12:
                    continue

                # 3. Single stray character box smaller than 4% width on extreme left/right edge
                if clean_len <= 1 and (bx < proc_w * 0.06 or (bx + bw) > proc_w * 0.96) and bw < proc_w * 0.08:
                    continue

            # Strip single isolated phantom edge letters caused by thin paper border strokes
            # e.g. trailing ' ן' or leading 'ן ' / 'ך ' separated by space
            import re as _re
            raw_line_text = _re.sub(r'^[ןך]\s+', '', raw_line_text)
            raw_line_text = _re.sub(r'\s+[ןך]$', '', raw_line_text)
            raw_line_text = raw_line_text.strip()
            if not raw_line_text:
                continue

            if learning_engine:
                clean_text, applied = learning_engine.apply_corrections(raw_line_text)
                total_corrections += len(applied)
            else:
                clean_text = raw_line_text
                applied = []

            # Map bounding box from preprocessed/warped OCR coordinates back to displayed image pixels!
            mapped_box = box
            if isinstance(box, dict):
                if flipped_180:
                    box = {
                        "x": int(proc_w - box.get("x", 0) - box.get("w", 0)),
                        "y": int(proc_h - box.get("y", 0) - box.get("h", 0)),
                        "w": int(box.get("w", 0)),
                        "h": int(box.get("h", 0))
                    }
                mapped_box = _map_box_to_original(box, coord_info, orig_w, orig_h)

            lines_data.append({
                'index': len(lines_data),
                'text': clean_text,
                'raw_text': raw_line_text,
                'confidence': confidence,
                'box': mapped_box,
                'skew': skew,
                'applied': applied
            })
            if clean_text:
                full_text_lines.append(clean_text)

        if progress_callback:
            progress_callback(100, 100, "Done!")

        return {
            'lines': lines_data,
            'full_text': "\n".join(full_text_lines),
            'corrections_applied': total_corrections,
            'image_size': (orig_w, orig_h)
        }
