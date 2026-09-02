"""Single-document smoke test. Synthetic PDF unless INPUT_MANIFEST is frozen."""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pymupdf

from harvest.resources import BatchGate, ResourceGuard, sample_cpu_util

ROOT = Path(__file__).resolve().parents[3]


def _synthetic_pdf_bytes() -> bytes:
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 72), "RESOURCE SMOKE — not a governed announcement")
    page.insert_text((72, 108), "行权价格 12.35元/份")
    page.insert_text((72, 136), "期权公允价值 3.27元/份 不得与行权价格合并")
    data = doc.tobytes()
    doc.close()
    return data


def run_single_document_smoke(*, synthetic: bool = True) -> dict[str, Any]:
    gate = BatchGate()
    gate.allow(1)
    guard = ResourceGuard()
    cpu0 = sample_cpu_util(0.15)
    before = guard.snapshot(cpu_util=cpu0)
    t0 = time.perf_counter()
    with guard.document_slot():
        guard.wait_until_safe()
        if not synthetic:
            status_path = ROOT / "input" / "manifests" / "INPUT_MANIFEST_STATUS.json"
            status = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else {}
            if status.get("INPUT_MANIFEST_STATUS") != "FROZEN":
                raise RuntimeError("refusing non-synthetic smoke: INPUT_MANIFEST is not FROZEN")
        raw = _synthetic_pdf_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        doc = pymupdf.open(stream=raw, filetype="pdf")
        pages = doc.page_count
        words = 0
        text_len = 0
        for p in doc:
            words += len(p.get_text("words"))
            text_len += len(p.get_text("text") or "")
        doc.close()
    cpu_seconds = time.perf_counter() - t0
    cpu1 = sample_cpu_util(0.15)
    after = guard.snapshot(cpu_util=cpu1)
    out = {
        "ok": True,
        "kind": "single_document_smoke",
        "synthetic": True,
        "not_eight_case_benchmark": True,
        "device_used": "cpu",
        "cpu_seconds": round(cpu_seconds, 6),
        "gpu_seconds_if_used": None,
        "gpu_model": None,
        "peak_vram_mb": None,
        "average_gpu_utilization_if_available": None,
        "batch_size": 1,
        "pages_processed": pages,
        "documents_processed": 1,
        "pdf_sha256": digest,
        "word_boxes": words,
        "text_len": text_len,
        "effective_docs_parallel": guard.docs_parallel,
        "throttle_events": guard.throttle_events,
        "cpu_util_before": before.cpu_util,
        "cpu_util_after": after.cpu_util,
        "ram_free_ratio_before": before.ram_free_ratio,
        "ram_free_ratio_after": after.ram_free_ratio,
        "load1_after": after.load1,
        "gpu": after.gpu,
        "temperature": None,
        "temperature_note": "KVM sandbox does not expose CPU/GPU package temperature",
        "run_at": datetime.now(timezone.utc).isoformat(),
    }
    dest = ROOT / "timing" / "batch" / "resource_smoke_1doc.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / "logs" / "resource_smoke_1doc.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return out
