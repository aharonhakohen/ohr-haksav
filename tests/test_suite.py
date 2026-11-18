import os
import sys
import json
import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from ui.i18n import STRINGS
from core.learning_engine import LearningEngine

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
        v1 = json.load(f)["version"]
    with open(os.path.join(BASE_DIR, "public", "version.json"), "r", encoding="utf-8") as f:
        v2 = json.load(f)["version"]
    assert v1 == v2, f"Version mismatch: {v1} != {v2}"

def test_learning_engine_diff():
    """Verify that learning engine extracts word corrections accurately."""
    le = LearningEngine()
    raw = "חשה אמר רבינו תום"
    corr = "משה אמר רבינו תוס"
    learned = le.learn_from_corrections(raw, corr, "test_page")
    learned_dict = dict(learned)
    assert "חשה" in learned_dict
    assert learned_dict["חשה"] == "משה"
    assert "תום" in learned_dict
    assert learned_dict["תום"] == "תוס"

def test_fitz_pdf_rendering():
    """Verify that PyMuPDF renders pages cleanly."""
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=300, height=400)
    page.insert_text((50, 50), "בדיקה", fontname="helv", fontsize=12)
    pix = page.get_pixmap(dpi=150)
    assert pix.width > 0 and pix.height > 0
    doc.close()

if __name__ == "__main__":
    test_i18n_key_parity()
    test_version_consistency()
    test_learning_engine_diff()
    test_fitz_pdf_rendering()
    print("All unit tests in test_suite.py passed successfully!")
