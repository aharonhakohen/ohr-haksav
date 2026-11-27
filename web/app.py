# -*- coding: utf-8 -*-
"""FastAPI web application for Ohr HaKsav (אור הכתב) online Hebrew handwriting OCR studio."""

from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import re
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Literal, Optional, Tuple
from urllib.parse import quote

import fitz
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from PIL import Image, ImageOps
from pydantic import BaseModel, Field

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.docx_exporter import export_notes_to_docx
from core.ocr_engine import OCREngine
from web.rules import StatelessLearningEngine, extract_corrections, normalize_user_rules

WEB_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))


def _load_app_version() -> str:
    version_file = ROOT_DIR / "version.json"
    if version_file.is_file():
        try:
            data = json.loads(version_file.read_text(encoding="utf-8"))
            return str(data.get("version", "1.4.4"))
        except Exception:
            pass
    return "1.4.4"


APP_VERSION = _load_app_version()
TORAH_TOOLS_HUB_URL = os.environ.get(
    "TORAH_TOOLS_HUB_URL",
    "https://davka-converter-805981380730.us-east1.run.app/",
).strip()
OHR_HAKSAV_WINDOWS_URL = os.environ.get(
    "OHR_HAKSAV_WINDOWS_URL",
    "https://github.com/aharonhakohen/ohr-haksav/releases/latest",
).strip()

MAX_FILE_BYTES = 25 * 1024 * 1024  # 25 MB per uploaded file
MAX_TOTAL_PAGES = 20
ALLOWED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
ALLOWED_UPLOAD_EXTS = ALLOWED_IMAGE_EXTS | {".pdf"}

app = FastAPI(
    title="Ohr HaKsav Online Studio",
    version=APP_VERSION,
    description="Online Hebrew handwriting OCR and Torah proofreading studio powered by Ohr HaKsav.",
)

_ocr_engine: Optional[OCREngine] = None
_engine_init_lock = threading.Lock()
_ocr_run_lock = threading.Lock()


def _get_ocr_engine() -> OCREngine:
    global _ocr_engine
    if _ocr_engine is None:
        with _engine_init_lock:
            if _ocr_engine is None:
                _ocr_engine = OCREngine()
    return _ocr_engine


def _model_checkpoint_exists() -> bool:
    if _ocr_engine is not None:
        return Path(_ocr_engine.checkpoint_path).is_file()
    env_dir = os.environ.get("OHR_HAKSAV_MODEL_DIR") or os.environ.get("KSAV_KOOKER_MODEL_DIR")
    candidates = [
        Path(env_dir) / "mishkefet-v1.pt" if env_dir else None,
        ROOT_DIR / "model_assets" / "mishkefet-v1.pt",
        ROOT_DIR / "models" / "mishkefet-v1.pt",
        Path.home()
        / ".cache/huggingface/hub/models--itayinbar--Mishkefet-v1/snapshots/16380452d62839f369c36f17312c94d5d1af1768/mishkefet-v1.pt",
    ]
    return any(p is not None and p.is_file() for p in candidates)


def _encode_preview_data_url(img: Image.Image, max_dim: int = 1600, quality: int = 82) -> str:
    preview = img.convert("RGB")
    w, h = preview.size
    if max(w, h) > max_dim:
        scale = max_dim / float(max(w, h))
        preview = preview.resize((max(1, int(round(w * scale))), max(1, int(round(h * scale)))), Image.LANCZOS)
    buf = io.BytesIO()
    preview.save(buf, format="JPEG", quality=quality, optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def _apply_cw_rotation(img: Image.Image, rot_deg: int) -> Image.Image:
    deg = rot_deg % 360
    if deg == 90:
        return img.rotate(-90, expand=True)
    if deg == 180:
        return img.rotate(180, expand=True)
    if deg == 270:
        return img.rotate(-270, expand=True)
    return img


def _normalize_box(box: Any, img_w: int, img_h: int) -> Optional[Dict[str, float]]:
    if not isinstance(box, dict) or img_w <= 0 or img_h <= 0:
        return None
    try:
        x = max(0.0, min(1.0, float(box.get("x", 0)) / float(img_w)))
        y = max(0.0, min(1.0, float(box.get("y", 0)) / float(img_h)))
        w = max(0.0, min(1.0 - x, float(box.get("w", 0)) / float(img_w)))
        h = max(0.0, min(1.0 - y, float(box.get("h", 0)) / float(img_h)))
        return {"x": round(x, 5), "y": round(y, 5), "w": round(w, 5), "h": round(h, 5)}
    except (TypeError, ValueError):
        return None


def _prepare_pages_from_uploads(
    uploads: List[Tuple[str, bytes, int]],
    engine: OCREngine,
    split_spread: bool,
    auto_orient: bool,
) -> List[Tuple[str, Image.Image]]:
    """Decode uploaded images/PDFs, apply user rotation, optional RTL spread split, and auto-orient."""
    pages: List[Tuple[str, Image.Image]] = []

    def _enqueue_oriented(title: str, pil_img: Image.Image) -> None:
        if len(pages) >= MAX_TOTAL_PAGES:
            raise HTTPException(
                status_code=400,
                detail=f"Maximum of {MAX_TOTAL_PAGES} pages per web scan exceeded. Use the offline Windows app for larger batches.",
            )
        img_out = pil_img
        if auto_orient:
            img_out, _ = engine.auto_orient_if_sideways(img_out)
        pages.append((title, img_out))

    for fname, raw, rot_deg in uploads:
        ext = Path(fname).suffix.lower()
        stem = Path(fname).stem or "page"
        if ext not in ALLOWED_UPLOAD_EXTS:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {fname}")

        if ext == ".pdf":
            try:
                pdf_doc = fitz.open(stream=raw, filetype="pdf")
            except Exception as exc:
                raise HTTPException(status_code=400, detail=f"Failed to read PDF {fname}: {exc}") from exc

            try:
                if len(pdf_doc) == 0:
                    raise HTTPException(status_code=400, detail=f"PDF {fname} has no pages")
                mat = fitz.Matrix(200.0 / 72.0, 200.0 / 72.0)
                for p_idx in range(len(pdf_doc)):
                    if len(pages) >= MAX_TOTAL_PAGES:
                        raise HTTPException(
                            status_code=400,
                            detail=f"Maximum of {MAX_TOTAL_PAGES} pages per web scan exceeded. Use the offline Windows app for larger batches.",
                        )
                    pix = pdf_doc[p_idx].get_pixmap(matrix=mat, alpha=False)
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    img = _apply_cw_rotation(img, rot_deg)
                    base_title = f"{stem} (Page {p_idx + 1})" if len(pdf_doc) > 1 else stem
                    if split_spread:
                        spread = engine.detect_and_split_two_page_spread(img, force=False)
                        if spread is not None:
                            right_pg, left_pg = spread
                            _enqueue_oriented(f"{base_title} (Right)", right_pg)
                            _enqueue_oriented(f"{base_title} (Left)", left_pg)
                            continue
                    _enqueue_oriented(base_title, img)
            finally:
                pdf_doc.close()
        else:
            try:
                with Image.open(io.BytesIO(raw)) as opened:
                    img = ImageOps.exif_transpose(opened).convert("RGB")
            except Exception as exc:
                raise HTTPException(status_code=400, detail=f"Failed to read image {fname}: {exc}") from exc

            img = _apply_cw_rotation(img, rot_deg)
            if split_spread:
                spread = engine.detect_and_split_two_page_spread(img, force=False)
                if spread is not None:
                    right_pg, left_pg = spread
                    _enqueue_oriented(f"{stem} (Right)", right_pg)
                    _enqueue_oriented(f"{stem} (Left)", left_pg)
                    continue
            _enqueue_oriented(stem, img)

    return pages


class ExtractRulesRequest(BaseModel):
    raw_text: str = ""
    corrected_text: str = ""


class ExportPageItem(BaseModel):
    page_num: int = 1
    title: str = ""
    text: str = ""
    date: str = ""


class ExportDocxRequest(BaseModel):
    pages: List[ExportPageItem] = Field(..., min_length=1)
    document_title: str = "שיעורי תורה וחידושים"
    document_subtitle: str = ""
    author_name: str = ""
    font_name: str = "David"
    layout_mode: Literal["standard", "continuous", "two_column"] = "standard"
    include_page_headers: bool = True


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "version": APP_VERSION,
            "hub_url": TORAH_TOOLS_HUB_URL,
            "windows_download_url": OHR_HAKSAV_WINDOWS_URL,
            "model_available": _model_checkpoint_exists(),
        },
    )


@app.get("/api/health")
async def health() -> JSONResponse:
    return JSONResponse(
        {
            "status": "ok",
            "version": APP_VERSION,
            "model_loaded": _ocr_engine is not None and _ocr_engine.is_ready(),
            "model_available": _model_checkpoint_exists(),
        }
    )


@app.post("/api/ocr/extract-rules")
async def api_extract_rules(payload: ExtractRulesRequest) -> JSONResponse:
    pairs = extract_corrections(payload.raw_text, payload.corrected_text)
    return JSONResponse({"pairs": pairs})


@app.post("/api/ocr/export-docx")
async def api_export_docx(payload: ExportDocxRequest) -> StreamingResponse:
    pages_dicts = [p.model_dump() for p in payload.pages]
    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = Path(tmpdir) / "OhrHaKsav_Notes.docx"
        export_notes_to_docx(
            pages=pages_dicts,
            output_path=str(out_path),
            document_title=payload.document_title,
            document_subtitle=payload.document_subtitle,
            author_name=payload.author_name,
            font_name=payload.font_name or "David",
            layout_mode=payload.layout_mode,
            include_page_headers=payload.include_page_headers,
        )
        docx_bytes = out_path.read_bytes()

    ascii_clean = re.sub(r"[^A-Za-z0-9._-]+", "_", payload.document_title).strip("_") or "OhrHaKsav_Notes"
    utf8_title = (payload.document_title.strip() or "OhrHaKsav_Notes").replace('"', "")
    content_disp = (
        f'attachment; filename="{ascii_clean}.docx"; '
        f"filename*=UTF-8''{quote(utf8_title + '.docx')}"
    )
    return StreamingResponse(
        io.BytesIO(docx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": content_disp},
    )


@app.post("/api/ocr/scan-stream")
async def scan_stream(
    files: List[UploadFile] = File(...),
    rotations: str = Form("[]"),
    clean_looseleaf: bool = Form(True),
    clean_shadows: bool = Form(False),
    high_accuracy: bool = Form(False),
    split_spread: bool = Form(False),
    auto_orient: bool = Form(True),
    user_rules: str = Form("[]"),
) -> StreamingResponse:
    """Stream real-time NDJSON progress and per-page OCR + bounding-box results."""
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    try:
        parsed_rotations = json.loads(rotations) if rotations.strip() else []
        if not isinstance(parsed_rotations, list):
            parsed_rotations = []
    except json.JSONDecodeError:
        parsed_rotations = []

    uploads: List[Tuple[str, bytes, int]] = []
    for idx, up in enumerate(files):
        fname = up.filename or f"page_{idx + 1}.jpg"
        ext = Path(fname).suffix.lower()
        if ext not in ALLOWED_UPLOAD_EXTS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file '{fname}'. Upload JPG, PNG, WebP, BMP, TIFF, or PDF.",
            )
        raw = await up.read()
        if not raw:
            raise HTTPException(status_code=400, detail=f"File '{fname}' is empty")
        if len(raw) > MAX_FILE_BYTES:
            raise HTTPException(status_code=413, detail=f"'{fname}' exceeds 25 MB limit")

        rot_val = 0
        if idx < len(parsed_rotations):
            try:
                rot_val = int(parsed_rotations[idx]) % 360
            except (TypeError, ValueError):
                rot_val = 0
        uploads.append((fname, raw, rot_val))

    stateless_le = StatelessLearningEngine(normalize_user_rules(user_rules))
    engine = _get_ocr_engine()
    prepared_pages = _prepare_pages_from_uploads(
        uploads=uploads,
        engine=engine,
        split_spread=split_spread,
        auto_orient=auto_orient,
    )
    if not prepared_pages:
        raise HTTPException(status_code=400, detail="No pages found in uploaded files")

    async def event_stream() -> AsyncGenerator[bytes, None]:
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[Dict[str, Any] | None] = asyncio.Queue()

        def emit(payload: Dict[str, Any]) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, payload)

        def worker() -> None:
            try:
                total_pages = len(prepared_pages)
                emit(
                    {
                        "type": "progress",
                        "pct": 5,
                        "stage": "Loading Hebrew handwriting recognition model...",
                        "page_index": 0,
                        "total_pages": total_pages,
                    }
                )

                with _ocr_run_lock:
                    engine.load_model()
                    engine.clean_looseleaf = bool(clean_looseleaf)
                    engine.clean_shadows_lines = bool(clean_shadows)
                    engine.check_upside_down = True
                    engine.set_accuracy_mode(bool(high_accuracy))

                    for page_idx, (page_title, pil_img) in enumerate(prepared_pages):
                        slice_start = 8 + int(round((page_idx / total_pages) * 90))
                        slice_span = max(1, int(round(90.0 / total_pages)))

                        def on_page_progress(done: int, total: int, label: str) -> None:
                            frac = done / float(max(1, total))
                            pct = min(98, slice_start + int(round(frac * slice_span)))
                            emit(
                                {
                                    "type": "progress",
                                    "pct": pct,
                                    "stage": f"Page {page_idx + 1}/{total_pages} ({page_title}): {label}",
                                    "page_index": page_idx,
                                    "total_pages": total_pages,
                                }
                            )

                        on_page_progress(0, 100, "Preparing page...")
                        result = engine.recognize_page(
                            pil_img,
                            learning_engine=stateless_le,
                            progress_callback=on_page_progress,
                            auto_crop_desk=True,
                            auto_orient=False,
                            verify_180=True,
                        )

                        img_w, img_h = result.get("image_size", pil_img.size)
                        formatted_lines: List[Dict[str, Any]] = []
                        raw_lines: List[str] = []
                        for line in result.get("lines", []):
                            raw_lines.append(line.get("raw_text", ""))
                            formatted_lines.append(
                                {
                                    "index": line.get("index", len(formatted_lines)),
                                    "text": line.get("text", ""),
                                    "raw_text": line.get("raw_text", ""),
                                    "confidence": round(float(line.get("confidence", 1.0)), 4),
                                    "box": line.get("box"),
                                    "nbox": _normalize_box(line.get("box"), img_w, img_h),
                                    "applied": [list(pair) for pair in line.get("applied", [])],
                                }
                            )

                        emit(
                            {
                                "type": "page_result",
                                "page_index": page_idx,
                                "page_num": page_idx + 1,
                                "title": page_title,
                                "image_data_url": _encode_preview_data_url(pil_img),
                                "image_width": img_w,
                                "image_height": img_h,
                                "lines": formatted_lines,
                                "full_text": result.get("full_text", ""),
                                "raw_text": "\n".join(t for t in raw_lines if t),
                                "corrections_applied": int(result.get("corrections_applied", 0)),
                            }
                        )

                emit(
                    {
                        "type": "done",
                        "pct": 100,
                        "stage": "Scan complete!",
                        "total_pages": len(prepared_pages),
                    }
                )
            except HTTPException as exc:
                emit({"type": "error", "detail": str(exc.detail)})
            except Exception as exc:
                emit({"type": "error", "detail": f"OCR scan failed: {exc}"})
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        task = asyncio.create_task(asyncio.to_thread(worker))
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield (json.dumps(item, ensure_ascii=False) + "\n").encode("utf-8")
        finally:
            await task

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
