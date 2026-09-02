"""Full-document native PDF normalization with bbox provenance."""

from __future__ import annotations

import hashlib
import time
from collections import Counter
from typing import Any

import pymupdf

try:
    import pdfplumber
except Exception:  # pragma: no cover
    pdfplumber = None


HEADER_Y_MAX = 80
FOOTER_Y_MIN_RATIO = 0.90


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _line_key(text: str) -> str:
    return " ".join((text or "").split())


def extract_document(path: str) -> dict[str, Any]:
    t0 = time.perf_counter()
    raw = open(path, "rb").read()
    t_sha = time.perf_counter()
    digest = sha256_bytes(raw)
    sha_s = time.perf_counter() - t_sha

    t_open = time.perf_counter()
    doc = pymupdf.open(stream=raw, filetype="pdf")
    open_s = time.perf_counter() - t_open

    t_text = time.perf_counter()
    pages: list[dict[str, Any]] = []
    warnings: list[str] = []
    native_chars = 0
    for i, page in enumerate(doc):
        words = []
        for w in page.get_text("words"):
            x0, y0, x1, y1, text, block, line, word_no = w[:8]
            words.append({
                "text": text,
                "bbox": [round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2)],
                "block": int(block),
                "line": int(line),
                "word_no": int(word_no),
            })
        text = page.get_text("text") or ""
        native_chars += len(text)
        dict_page = page.get_text("dict")
        blocks = []
        for b in dict_page.get("blocks", []):
            if b.get("type") != 0:
                continue
            bt = []
            for line in b.get("lines", []):
                lt = "".join(s.get("text", "") for s in line.get("spans", []))
                if lt.strip():
                    bt.append(lt)
            if bt:
                blocks.append({
                    "bbox": [round(x, 2) for x in b.get("bbox", (0, 0, 0, 0))],
                    "text": "\n".join(bt),
                    "n_lines": len(bt),
                })
        tables = []
        try:
            found = page.find_tables()
            for ti, tab in enumerate(found.tables if found else []):
                grid = tab.extract()
                tables.append({
                    "table_id": f"p{i+1}_t{ti+1}",
                    "bbox": [round(x, 2) for x in (tab.bbox or (0, 0, 0, 0))],
                    "n_rows": len(grid),
                    "n_cols": max((len(r) for r in grid), default=0),
                    "cells": grid,
                    "extractor": "pymupdf.find_tables",
                })
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"page {i+1} find_tables: {type(exc).__name__}: {exc}")
        pages.append({
            "page_number": i + 1,
            "width": round(page.rect.width, 2),
            "height": round(page.rect.height, 2),
            "text": text,
            "words": words,
            "blocks": blocks,
            "tables": tables,
            "char_count": len(text),
            "word_count": len(words),
        })
    text_s = time.perf_counter() - t_text

    t_plumb = time.perf_counter()
    plumber_tables = []
    if pdfplumber is not None:
        try:
            with pdfplumber.open(path) as pdf:
                for i, page in enumerate(pdf.pages):
                    for ti, tab in enumerate(page.extract_tables() or []):
                        plumber_tables.append({
                            "table_id": f"plumb_p{i+1}_t{ti+1}",
                            "page_number": i + 1,
                            "cells": tab,
                            "extractor": "pdfplumber",
                        })
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"pdfplumber: {type(exc).__name__}: {exc}")
    plumb_s = time.perf_counter() - t_plumb

    header_footer = _detect_repeating(pages)
    for p in pages:
        p["is_likely_header_footer_lines"] = header_footer.get(p["page_number"], [])

    ocr_required = native_chars < 80
    if ocr_required:
        warnings.append("native_text_sparse; OCR residual not enabled in v1")

    model = {
        "pdf_sha256": digest,
        "file_size_bytes": len(raw),
        "page_count": doc.page_count,
        "metadata": {k: doc.metadata.get(k) for k in ("title", "author", "creator", "producer", "creationDate")},
        "native_text_available": native_chars >= 80,
        "ocr_required": ocr_required,
        "table_detected": any(p["tables"] for p in pages) or bool(plumber_tables),
        "pages": pages,
        "plumber_tables": plumber_tables,
        "warnings": warnings,
        "full_text": "\n".join(p["text"] for p in pages),
        "timing": {
            "sha256_seconds": round(sha_s, 6),
            "open_seconds": round(open_s, 6),
            "native_text_seconds": round(text_s, 6),
            "pdfplumber_seconds": round(plumb_s, 6),
            "normalize_total_seconds": round(time.perf_counter() - t0, 6),
        },
    }
    doc.close()
    return model


def _detect_repeating(pages: list[dict[str, Any]]) -> dict[int, list[str]]:
    if len(pages) < 2:
        return {}
    line_pages: Counter[str] = Counter()
    per_page_lines: dict[int, list[str]] = {}
    for p in pages:
        lines = []
        for raw in (p["text"] or "").splitlines():
            s = _line_key(raw)
            if 1 <= len(s) <= 40:
                lines.append(s)
        per_page_lines[p["page_number"]] = lines
        for s in set(lines):
            line_pages[s] += 1
    thresh = max(2, len(pages) - 1)
    repeating = {s for s, n in line_pages.items() if n >= thresh}
    return {pn: [ln for ln in lines if ln in repeating] for pn, lines in per_page_lines.items()}
