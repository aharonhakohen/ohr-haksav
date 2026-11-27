# -*- coding: utf-8 -*-
"""Integration and unit tests for the Ohr HaKsav Online Web Studio."""

from __future__ import annotations

import io
import json
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from web.app import app
from web.rules import StatelessLearningEngine, extract_corrections, normalize_user_rules


def _make_synthetic_page_png() -> bytes:
    """Create a realistic synthetic looseleaf page image with dark ink strokes."""
    img = Image.new("RGB", (900, 500), (248, 248, 245))
    draw = ImageDraw.Draw(img)
    # Pale blue ruled lines
    for y in (140, 210, 280):
        draw.line([(40, y), (860, y)], fill=(185, 210, 240), width=2)
    # Vertical red margin line on left
    draw.line([(95, 20), (95, 480)], fill=(215, 95, 105), width=2)
    # Dark ink-like cursive blobs across two lines
    for x in range(220, 740, 28):
        draw.line([(x, 115), (x + 12, 134), (x + 18, 118)], fill=(25, 32, 65), width=4)
        draw.line([(x, 185), (x + 10, 204), (x + 20, 190)], fill=(25, 32, 65), width=4)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_web_home_and_health() -> None:
    client = TestClient(app)
    res_home = client.get("/")
    assert res_home.status_code == 200
    assert "Ohr HaKsav Online" in res_home.text
    assert "Download Windows App (Offline)" in res_home.text

    res_health = client.get("/api/health")
    assert res_health.status_code == 200
    data = res_health.json()
    assert data["status"] == "ok"
    assert data["model_available"] is True


def test_stateless_learning_engine_and_extract() -> None:
    raw_rules = json.dumps([
        {"raw_text": "חשה", "corrected_text": "משה", "count": 2, "is_active": True},
        {"raw_text": "לאפעיל", "corrected_text": "לא_יוחלף", "is_active": False},
    ])
    normalized = normalize_user_rules(raw_rules)
    assert len(normalized) == 2

    le = StatelessLearningEngine(normalized)
    text_out, applied = le.apply_corrections("חשה אמר ביון ברור תום לאפעיל")
    assert "משה" in text_out
    assert "כיון" in text_out
    assert "ברור" in text_out
    assert "תוס'" in text_out
    assert "לאפעיל" in text_out
    assert len(applied) >= 3

    pairs = extract_corrections("חשה אמר רבינו תום", "משה אמר רבינו תוס")
    pair_dict = {p["raw_text"]: p["corrected_text"] for p in pairs}
    assert pair_dict.get("חשה") == "משה"
    assert pair_dict.get("תום") == "תוס"


def test_extract_rules_endpoint() -> None:
    client = TestClient(app)
    res = client.post(
        "/api/ocr/extract-rules",
        json={"raw_text": "בסייד שיעור א", "corrected_text": 'בס"ד שיעור א\''},
    )
    assert res.status_code == 200
    pairs = res.json()["pairs"]
    assert len(pairs) >= 1


def test_export_docx_all_layouts() -> None:
    client = TestClient(app)
    for layout in ("standard", "continuous", "two_column"):
        res = client.post(
            "/api/ocr/export-docx",
            json={
                "pages": [
                    {"page_num": 1, "title": "שיעור א'", "text": 'בס"ד\nהנה יש לחקור בדברי רש"י.', "date": ""},
                    {"page_num": 2, "title": "שיעור ב'", "text": "ועוד יש להקשות מדברי הרמב\"ם.", "date": ""},
                ],
                "document_title": "חידושי תורה",
                "document_subtitle": "בבא קמא",
                "author_name": "תלמיד",
                "font_name": "David",
                "layout_mode": layout,
                "include_page_headers": True,
            },
        )
        assert res.status_code == 200
        assert "application/vnd.openxmlformats-officedocument.wordprocessingml.document" in res.headers["content-type"]
        with zipfile.ZipFile(io.BytesIO(res.content), "r") as zf:
            for name in zf.namelist():
                if name.endswith((".xml", ".rels")):
                    ET.fromstring(zf.read(name))
            doc_xml = zf.read("word/document.xml").decode("utf-8")
            assert "חידושי תורה" in doc_xml
            assert "רש\"י" in doc_xml or "רש&quot;י" in doc_xml
            if layout == "two_column":
                assert 'w:num="2"' in doc_xml


def test_scan_stream_end_to_end() -> None:
    client = TestClient(app)
    png_bytes = _make_synthetic_page_png()
    res = client.post(
        "/api/ocr/scan-stream",
        files=[("files", ("sample_page.png", png_bytes, "image/png"))],
        data={
            "rotations": "[0]",
            "clean_looseleaf": "true",
            "clean_shadows": "false",
            "high_accuracy": "false",
            "split_spread": "false",
            "auto_orient": "true",
            "user_rules": json.dumps([{"raw_text": "טעות", "corrected_text": "תיקון", "is_active": True}]),
        },
    )
    assert res.status_code == 200
    events = [json.loads(line) for line in res.text.strip().splitlines() if line.strip()]
    types = [ev["type"] for ev in events]
    assert "progress" in types
    assert "page_result" in types
    assert "done" in types
    assert "error" not in types

    page_ev = next(ev for ev in events if ev["type"] == "page_result")
    assert page_ev["page_num"] == 1
    assert page_ev["image_data_url"].startswith("data:image/jpeg;base64,")
    assert isinstance(page_ev["lines"], list)
    assert isinstance(page_ev["full_text"], str)
    assert page_ev["image_width"] > 0 and page_ev["image_height"] > 0
