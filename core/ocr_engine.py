# -*- coding: utf-8 -*-
"""
TorahNotesOCR - Offline Hebrew OCR Engine (v1.4.0)
Wraps the Mishkefet-v1 CTC neural recognizer for Hebrew handwriting,
providing:
- 4-point perspective dewarping ("CamScanner" flatten) & dark-desk cropping
- Shadow lighting normalization & pale blue ruled-line suppression
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


class OCREngine:
    def __init__(self, model_dir: Optional[str] = None):
        self.model_dir = model_dir or self._resolve_model_dir()
        self.checkpoint_path = os.path.join(self.model_dir, "mishkefet-v1.pt")
        self._recognizer = None
        self._is_loaded = False
        self.high_accuracy_mode = False
        self.clean_shadows_lines = False
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

    def crop_document_if_desk(self, img: Image.Image) -> Image.Image:
        """
        Detects if an image is a page photographed on a darker table/desk background.
        First attempts a 4-point perspective dewarp ("CamScanner" flatten) when the
        paper forms a tilted quadrilateral; falls back to an axis-aligned crop.
        """
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
                        # Attempt 4-point perspective flatten if angled trapezoid
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

                            # Only perspective-warp if document is substantial and has noticeable perspective tilt
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
                                warped = cv2.warpPerspective(arr, M, (max_w, max_h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
                                try:
                                    from core.logger import log
                                    log.info(f"Perspective dewarp applied: flattened {w}x{h} -> {max_w}x{max_h}")
                                except Exception:
                                    pass
                                return Image.fromarray(warped)

                        # Fallback: clean bounding-box crop
                        x, y, cw, ch = cv2.boundingRect(largest)
                        pad_x = int((cw / scale) * 0.015)
                        pad_y = int((ch / scale) * 0.015)
                        orig_x = max(0, int(x / scale) - pad_x)
                        orig_y = max(0, int(y / scale) - pad_y)
                        orig_w = min(w - orig_x, int(cw / scale) + 2 * pad_x)
                        orig_h = min(h - orig_y, int(ch / scale) + 2 * pad_y)
                        if orig_w > 0.3 * w and orig_h > 0.3 * h:
                            return img.crop((orig_x, orig_y, orig_x + orig_w, orig_y + orig_h))
        except Exception:
            pass
        return img

    def clean_shadows_and_lines(self, img: Image.Image) -> Image.Image:
        """
        Normalizes uneven desk-lamp lighting/shadows and gently suppresses pale blue/cyan
        looseleaf ruled lines while preserving dark pen and pencil handwriting strokes.
        """
        try:
            rgb = np.array(img.convert("RGB"))

            # 1. Suppress pale blue ruled lines in HSV space (preserve dark blue pen ink by checking V > 135)
            hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
            h_ch, s_ch, v_ch = cv2.split(hsv)
            blue_line_mask = (h_ch >= 88) & (h_ch <= 135) & (s_ch >= 22) & (s_ch <= 160) & (v_ch >= 140)
            cleaned = rgb.copy()
            # Gently blend pale blue lines toward white paper
            cleaned[blue_line_mask] = np.clip(cleaned[blue_line_mask].astype(np.int32) + 55, 0, 255).astype(np.uint8)

            # 2. Morphological background shadow normalization on luminance
            lab = cv2.cvtColor(cleaned, cv2.COLOR_RGB2LAB)
            l_ch, a_ch, b_ch = cv2.split(lab)
            dilated = cv2.dilate(l_ch, np.ones((7, 7), np.uint8))
            bg_img = cv2.medianBlur(dilated, 21)
            diff_img = 255 - cv2.absdiff(l_ch, bg_img)
            norm_l = cv2.normalize(diff_img, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_8UC1)
            # Blend 65% normalized luminance + 35% original luminance so faint pencil strokes stay readable
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
            # Examine center vertical strip [35% .. 65%] of width, ignoring top/bottom 10% margins
            x_start = int(w * 0.35)
            x_end = int(w * 0.65)
            y_start = int(h * 0.10)
            y_end = int(h * 0.90)
            roi = gray[y_start:y_end, x_start:x_end]

            col_means = np.mean(roi, axis=0)
            # Smooth column profile to avoid single-letter spikes
            k = max(5, int(w * 0.01) | 1)
            smooth = np.convolve(col_means, np.ones(k) / k, mode="same")

            min_idx = int(np.argmin(smooth))
            valley_val = float(smooth[min_idx])
            median_val = float(np.median(smooth))

            if force or (median_val - valley_val >= 16.0):
                split_x = x_start + min_idx
                # Hebrew RTL order: Right page first, then Left page!
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

    def verify_upright_orientation(self, img: Image.Image) -> Image.Image:
        """
        Checks if a page is upside-down (180°) by comparing neural OCR confidence on
        up to 2 middle line crops upright vs. rotated 180°.
        """
        try:
            if not self.is_ready():
                return img
            from core.hebocr.page.segment import segment_page

            crops, _, _ = segment_page(img)
            if not crops:
                return img

            # Sample up to 2 substantial middle lines
            mid = len(crops) // 2
            sample = crops[max(0, mid - 1) : min(len(crops), mid + 1)]
            if not sample:
                return img

            _, confs_up = self._recognizer.read(sample, return_confidence=True)
            avg_up = float(np.mean(confs_up)) if confs_up else 0.0

            # Only test 180° flip if upright confidence looks suspiciously low (< 0.72)
            if avg_up >= 0.72:
                return img

            sample_flipped = [c.rotate(180) for c in sample]
            _, confs_flip = self._recognizer.read(sample_flipped, return_confidence=True)
            avg_flip = float(np.mean(confs_flip)) if confs_flip else 0.0

            if avg_flip > avg_up + 0.09:
                try:
                    from core.logger import log
                    log.info(f"Auto-orient 180° fix: Upright conf={avg_up:.2f}, Flipped 180° conf={avg_flip:.2f}. Flipping page upright.")
                except Exception:
                    pass
                return img.rotate(180)
        except Exception:
            pass
        return img

    def preprocess_image(
        self,
        img: Image.Image,
        enhance_contrast: bool = True,
        auto_crop_desk: bool = True,
        auto_orient: bool = True,
        clean_shadows_lines: Optional[bool] = None
    ) -> Image.Image:
        """Cleans and standardizes image for optimal Hebrew handwriting recognition."""
        if img.mode != "RGB":
            img = img.convert("RGB")

        img = ImageOps.exif_transpose(img)

        if auto_orient:
            img, _ = self.auto_orient_if_sideways(img)

        if auto_crop_desk:
            img = self.crop_document_if_desk(img)

        use_clean = self.clean_shadows_lines if clean_shadows_lines is None else clean_shadows_lines
        if use_clean:
            img = self.clean_shadows_and_lines(img)

        if enhance_contrast:
            enhancer = ImageEnhance.Contrast(img)
            img = enhancer.enhance(1.35)
            sharpener = ImageEnhance.Sharpness(img)
            img = sharpener.enhance(1.2)

        return img

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
        Runs full-page segmentation and OCR recognition on an image.
        """
        self.load_model()

        if isinstance(image_or_path, (str, Path)):
            img = Image.open(str(image_or_path))
        else:
            img = image_or_path

        img = self.preprocess_image(img, auto_crop_desk=auto_crop_desk, auto_orient=auto_orient)

        do_verify_180 = self.check_upside_down if verify_180 is None else verify_180
        if do_verify_180:
            if progress_callback:
                progress_callback(5, 100, "Checking page orientation...")
            img = self.verify_upright_orientation(img)

        w, h = img.size

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

            if learning_engine:
                clean_text, applied = learning_engine.apply_corrections(raw_line_text)
                total_corrections += len(applied)
            else:
                clean_text = raw_line_text
                applied = []

            lines_data.append({
                'index': len(lines_data),
                'text': clean_text,
                'raw_text': raw_line_text,
                'confidence': confidence,
                'box': box,
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
            'image_size': (w, h)
        }
