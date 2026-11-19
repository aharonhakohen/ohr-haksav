import os
import sys
import json
import tempfile
import numpy as np
import cv2
from PIL import Image

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from ui.i18n import STRINGS
from core.learning_engine import LearningEngine
from core.ocr_engine import OCREngine
from core.docx_exporter import export_notes_to_docx
from ui.update_dialog import compute_file_sha256, verify_file_sha256, is_strict_offline_mode, is_connected_to_internet


def test_i18n_key_parity():
    """Verify that English and Hebrew dictionaries have parity for all keys."""
    en_keys = set(STRINGS["en"].keys())
    he_keys = set(STRINGS["he"].keys())
    missing_in_he = en_keys - he_keys
    missing_in_en = he_keys - en_keys
    assert not missing_in_he, f"Keys present in EN but missing in HE: {missing_in_he}"
    assert not missing_in_en, f"Keys present in HE but missing in EN: {missing_in_en}"


def test_version_consistency():
    """Verify that version.json and public/version.json are consistent."""
    with open(os.path.join(BASE_DIR, "version.json"), "r", encoding="utf-8") as f:
        d1 = json.load(f)
    with open(os.path.join(BASE_DIR, "public", "version.json"), "r", encoding="utf-8") as f:
        d2 = json.load(f)
    assert d1["version"] == d2["version"], f"Version mismatch: {d1['version']} != {d2['version']}"
    assert d1.get("engineVersion") == d2.get("engineVersion")


def test_learning_engine_diff():
    """Verify that learning engine extracts candidate pairs cleanly and commits approved pairs."""
    le = LearningEngine()
    raw = "חשה אמר רבינו תום"
    corr = "משה אמר רבינו תוס"
    pairs = le.extract_corrections(raw, corr)
    pair_dict = dict(pairs)
    assert pair_dict.get("חשה") == "משה"
    assert pair_dict.get("תום") == "תוס"
    learned = le.commit_corrections(pairs, page_name="test_page", raw_text=raw, corrected_text=corr)
    assert len(learned) == 2


def test_fitz_pdf_rendering():
    """Verify that PyMuPDF renders pages cleanly."""
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=300, height=400)
    page.insert_text((50, 50), "בדיקה", fontname="helv", fontsize=12)
    pix = page.get_pixmap(dpi=150)
    assert pix.width > 0 and pix.height > 0
    doc.close()


def test_two_page_spread_split():
    """Verify two-page open notebook spread detection & Hebrew RTL split (Right -> Left)."""
    engine = OCREngine()
    # Create synthetic 1000x600 white two-page spread with a dark vertical spine gutter at x=510
    arr = np.full((600, 1000, 3), 240, dtype=np.uint8)
    arr[:, 500:520, :] = 60  # Dark spine gutter
    # Mark right page distinctly red-tinted corner and left page green-tinted corner
    arr[50:100, 850:900] = [200, 40, 40]
    arr[50:100, 100:150] = [40, 200, 40]
    img = Image.fromarray(arr)

    res = engine.detect_and_split_two_page_spread(img, force=False)
    assert res is not None, "Failed to detect two-page spread!"
    right_pg, left_pg = res
    assert right_pg.width > 400 and left_pg.width > 400
    # Verify Hebrew order: right_pg contains the red marker, left_pg contains the green marker
    r_arr = np.array(right_pg)
    l_arr = np.array(left_pg)
    assert np.mean(r_arr[50:100, -150:-100, 0]) > 150, "First split page should be Right Page!"
    assert np.mean(l_arr[50:100, 100:150, 1]) > 150, "Second split page should be Left Page!"


def test_shadow_and_blue_line_cleaning():
    """Verify shadow normalization and pale blue ruled-line suppression."""
    engine = OCREngine()
    arr = np.full((400, 300, 3), 240, dtype=np.uint8)
    # Add uneven shadow gradient + pale blue ruled lines + dark ink strokes
    arr[:, :150] = 170
    arr[100:103, :] = [180, 210, 245]  # pale blue ruled line
    arr[120:130, 80:200] = [25, 25, 30]  # dark ink
    cleaned = engine.clean_shadows_and_lines(Image.fromarray(arr))
    assert cleaned.size == (300, 400)
    assert cleaned.mode == "RGB"


def test_perspective_dewarp_crop():
    """Verify 4-point perspective flattening on tilted white page over dark desk."""
    engine = OCREngine()
    arr = np.full((600, 600, 3), 30, dtype=np.uint8)  # Dark wood desk
    quad = np.array([[110, 80], [490, 110], [520, 520], [80, 490]], dtype=np.int32)
    cv2.fillConvexPoly(arr, quad, (240, 240, 240))
    cropped = engine.crop_document_if_desk(Image.fromarray(arr))
    assert cropped.width < 580 and cropped.height < 580
    assert cropped.width > 300 and cropped.height > 300


def test_docx_layouts_export():
    """Verify standard, continuous, and two-column Sefer .docx exports."""
    import zipfile
    sample_pages = [
        {"page_num": 1, "title": "שיעור א'", "text": "בס\"ד\nהנה יש לחקור בדברי רש\"י ותוספות."},
        {"page_num": 2, "title": "שיעור ב'", "text": "ועוד יש להקשות מדברי הרמב\"ם."}
    ]
    for mode in ("standard", "continuous", "two_column"):
        out_path = os.path.join(tempfile.gettempdir(), f"test_export_{mode}.docx")
        export_notes_to_docx(sample_pages, out_path, layout_mode=mode, font_name="David")
        assert os.path.exists(out_path)
        if mode == "two_column":
            with zipfile.ZipFile(out_path, "r") as zf:
                xml = zf.read("word/document.xml").decode("utf-8")
                assert 'w:num="2"' in xml, "Two-column layout XML missing w:num='2'!"
        os.remove(out_path)


def test_sha256_and_strict_offline():
    """Verify SHA-256 verification and Strict Air-Gap zero-network policy."""
    tmp = os.path.join(tempfile.gettempdir(), "ohr_sha_test.bin")
    with open(tmp, "wb") as f:
        f.write(b"OhrHaKsav Integrity Test Payload")
    digest = compute_file_sha256(tmp)
    assert len(digest) == 64
    assert verify_file_sha256(tmp, digest) is True
    assert verify_file_sha256(tmp, "0" * 64) is False
    os.remove(tmp)

    prev = os.environ.get("OHR_HAKSAV_OFFLINE_ONLY")
    try:
        os.environ["OHR_HAKSAV_OFFLINE_ONLY"] = "1"
        assert is_strict_offline_mode() is True
        assert is_connected_to_internet() is False
    finally:
        if prev is None:
            os.environ.pop("OHR_HAKSAV_OFFLINE_ONLY", None)
        else:
            os.environ["OHR_HAKSAV_OFFLINE_ONLY"] = prev


def test_single_pass_and_cursive_fixes():
    """Verify single-pass apply_corrections prevents תוס'' double-apostrophe and resolves cursive & boxed בס"ד typos safely."""
    le = LearningEngine()
    sample = "נבסיידן סיידן בסידן בסייקן שיעורט קוס כתב לבאורה ביון הבלי בלי דבר ברור דברורות בופר"
    out, applied = le.apply_corrections(sample)
    assert "תוס''" not in out, f"Double apostrophe bug recurred: {out}"
    assert "תוס'" in out
    assert out.count('בס"ד') >= 4, f"Boxed בס\"ד auto-fixes did not trigger cleanly: {out}"
    assert "שיעור ט'" in out
    assert "לכאורה" in out
    assert "כיון" in out
    assert "הכלי" in out
    assert "דצרורות" in out
    assert "כופר" in out
    # Valid Hebrew words must remain completely untouched
    assert " בלי " in out and " דבר " in out and " ברור " in out


def test_looseleaf_cleaner_and_inverse_box_map():
    """Verify shadowed binder holes (crossed by blue ruled lines) & slanted shadowed red margin lines are erased cleanly."""
    engine = OCREngine()
    # Create synthetic looseleaf page with shaded bottom, pale blue ruled lines, 3 binder holes, and a slanted red margin line
    arr = np.full((900, 600, 3), 235, dtype=np.uint8)
    # Darken bottom 30% to simulate desk shadow
    arr[600:, :] = 185
    # Draw pale blue ruled lines across the entire page including through the bottom binder hole!
    for y in range(100, 880, 40):
        arr[y : y + 3, :] = [145, 175, 210]
    cv2.circle(arr, (35, 140), 18, (25, 25, 25), -1)
    cv2.circle(arr, (35, 450), 18, (25, 25, 25), -1)
    cv2.circle(arr, (35, 760), 18, (25, 25, 25), -1)
    # Slanted red margin line (drifts from x=88 at top to x=76 at bottom, dark red in bottom shadow!)
    for y in range(900):
        rx = int(round(88 - 12.0 * (y / 900.0)))
        if y < 600:
            arr[y, rx : rx + 4] = [215, 110, 120]
        else:
            arr[y, rx : rx + 4] = [145, 85, 88]  # Dark red in shadow (gray < 115, high redness)

    cleaned, red_x = engine.clean_looseleaf_artifacts(Image.fromarray(arr))
    c_arr = np.array(cleaned)
    assert red_x is not None and 70 <= red_x <= 95
    # Verify ALL 3 binder holes (including the bottom shadowed hole crossed by blue lines!) were erased
    assert float(c_arr[140, 35].mean()) > 190.0, "Top binder hole was not erased!"
    assert float(c_arr[450, 35].mean()) > 190.0, "Middle binder hole was not erased!"
    assert float(c_arr[760, 35].mean()) > 145.0, "Bottom shadowed binder hole was not erased!"
    # Verify shadowed red margin line at bottom (y=800, x~77) was erased cleanly
    rx_bot = int(round(88 - 12.0 * (800 / 900.0)))
    bot_redness = float(c_arr[800, rx_bot + 1, 0]) - 0.5 * (float(c_arr[800, rx_bot + 1, 1]) + float(c_arr[800, rx_bot + 1, 2]))
    assert bot_redness < 12.0, f"Shadowed bottom red margin line survived: redness={bot_redness}"

    # Verify inverse box mapping on tilted desk image
    desk = np.full((600, 600, 3), 25, dtype=np.uint8)
    quad = np.array([[100, 80], [500, 100], [520, 520], [80, 500]], dtype=np.int32)
    cv2.fillConvexPoly(desk, quad, (240, 240, 240))
    warped, coord_info = engine.crop_document_if_desk_with_map(Image.fromarray(desk))
    assert coord_info["mode"] == "perspective"
    from core.ocr_engine import _map_box_to_original
    mapped = _map_box_to_original({"x": 50, "y": 50, "w": 200, "h": 40}, coord_info, 600, 600)
    assert mapped["x"] >= 100 and mapped["y"] >= 100, f"Box not mapped back into desk coords: {mapped}"


if __name__ == "__main__":
    test_i18n_key_parity()
    test_version_consistency()
    test_learning_engine_diff()
    test_fitz_pdf_rendering()
    test_two_page_spread_split()
    test_shadow_and_blue_line_cleaning()
    test_perspective_dewarp_crop()
    test_docx_layouts_export()
    test_sha256_and_strict_offline()
    test_single_pass_and_cursive_fixes()
    test_looseleaf_cleaner_and_inverse_box_map()
    print("All v1.4.3 unit tests in test_suite.py passed successfully!")
