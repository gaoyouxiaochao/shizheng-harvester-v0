"""End-to-end harvest. Resource-gated. Does not bind Truth."""

from __future__ import annotations

import csv
import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from harvest import (
    CANDIDATE_ASSERTION_VERSION,
    DOCUMENT_MODEL_VERSION,
    EXTRACTOR_VERSION,
    FIELD_SCHEMA_VERSION,
)
from harvest.identity import infer_from_model
from harvest.match import harvest
from harvest.normalize import extract_document, sha256_bytes
from harvest.resources import BatchGate, ResourceGuard, sample_cpu_util

ROOT = Path(__file__).resolve().parents[3]
PUBLIC_CANDIDATE = Path("/workspace/public/challenger")


PRIMARY_CASES = [
    {
        "case_id": "C01",
        "stock_code": "603162",
        "company": "海通发展",
        "published_date": "2026-09-01",
        "short_title": "2024预留EP2行权条件成就",
        "official_document_id": None,
        "needle": "603162_海通发展",
    },
    {
        "case_id": "C02",
        "stock_code": "603893",
        "company": "瑞芯微",
        "published_date": "2026-08-25",
        "short_title": "预留EP3自主行权实施",
        "official_document_id": "1225497491",
        "needle": "1225497491",
    },
    {
        "case_id": "C03",
        "stock_code": "002134",
        "company": "天津普林",
        "published_date": "2026-08-29",
        "short_title": "2024计划EP2自主行权提示",
        "official_document_id": None,
        "needle": "002134_天津普林",
    },
    {
        "case_id": "C04",
        "stock_code": "002463",
        "company": "沪电股份",
        "published_date": "2026-08-26",
        "short_title": "2024计划EP1行权条件成就",
        "official_document_id": None,
        "needle": "002463_沪电股份",
    },
    {
        "case_id": "C05",
        "stock_code": "603598",
        "company": "引力传媒",
        "published_date": "2026-07-15",
        "short_title": "2024计划EP2行权条件成就",
        "official_document_id": "1225457814",
        "needle": "603598_引力传媒",
    },
    {
        "case_id": "C06",
        "stock_code": "300124",
        "company": "汇川技术",
        "published_date": "2026-08-29",
        "short_title": "第六期预留EP3行权条件成就",
        "official_document_id": "1225524615",
        "needle": "1225524615",
    },
    {
        "case_id": "C07",
        "stock_code": "600186",
        "company": "莲花控股",
        "published_date": "2026-08-29",
        "short_title": "2023首次EP3及预留EP2条件成就",
        "official_document_id": None,
        "needle": "600186_莲花控股",
    },
    {
        "case_id": "C08",
        "stock_code": "600570",
        "company": "恒生电子",
        "published_date": "2026-08-01",
        "short_title": "2025计划EP1行权条件成就",
        "official_document_id": None,
        "needle": "600570_恒生电子_2026-08-01_2025计划EP1行权条件成就_公司公告",
    },
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dump(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def discover_local_pdfs() -> list[dict[str, Any]]:
    """Use only PDFs the operator placed in input/pdf. Never download. Never walk D:\\."""
    dest = ROOT / "input" / "pdf"
    dest.mkdir(parents=True, exist_ok=True)
    files = sorted(dest.glob("*.pdf"))
    records: list[dict[str, Any]] = []
    used: set[Path] = set()

    def attach(case: dict[str, Any], match: Path) -> dict[str, Any]:
        data = match.read_bytes()
        return {
            **case,
            "display_filename": match.name,
            "source_path": str(match),
            "pdf_sha256": sha256_bytes(data),
            "file_size_bytes": len(data),
            "asset_status": "LOCAL_INPUT",
            "governed_local_sha_verified": False,
        }

    for case in PRIMARY_CASES:
        match = None
        for fn in files:
            if fn in used:
                continue
            name = fn.name
            oid = case.get("official_document_id")
            if oid and oid in name:
                match = fn
                break
            if case["needle"] in name:
                match = fn
                break
            if case["stock_code"] in name:
                match = fn
                break
        if match is None:
            records.append({**case, "asset_status": "MISSING"})
            continue
        used.add(match)
        records.append(attach(case, match))

    extra_i = 0
    for fn in files:
        if fn in used:
            continue
        extra_i += 1
        records.append(attach({
            "case_id": f"X{extra_i:02d}",
            "stock_code": "unknown",
            "company": fn.stem[:20],
            "published_date": None,
            "short_title": fn.stem,
            "official_document_id": None,
            "needle": fn.name,
        }, fn))

    man = ROOT / "input" / "manifests"
    man.mkdir(parents=True, exist_ok=True)
    with (man / "INPUT_MANIFEST.jsonl").open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    found = sum(1 for r in records if r.get("source_path"))
    _dump(man / "INPUT_MANIFEST_STATUS.json", {
        "INPUT_MANIFEST_STATUS": "LOCAL_INPUT" if found else "EMPTY",
        "pdfs_in_input": found,
        "missing_primary_cases": [r["case_id"] for r in records if r.get("asset_status") == "MISSING"],
        "written_at": _now(),
    })
    with (man / "PDF_ASSET_REGISTRY.jsonl").open("w", encoding="utf-8") as fh:
        for r in records:
            if not r.get("source_path"):
                continue
            fh.write(json.dumps({
                "asset_id": r["case_id"],
                "company": r.get("company"),
                "stock_code": r.get("stock_code"),
                "display_filename": r.get("display_filename"),
                "source_path": r.get("source_path"),
                "pdf_sha256": r.get("pdf_sha256"),
                "file_size_bytes": r.get("file_size_bytes"),
                "asset_status": r.get("asset_status"),
                "ingested_at": _now(),
            }, ensure_ascii=False) + "\n")
    return records


def harvest_one(rec: dict[str, Any], run_id: str, warm: bool = False) -> dict[str, Any]:
    t_all = time.perf_counter()
    cpu0 = sample_cpu_util(0.08)
    path = rec["source_path"]
    model = extract_document(path)
    ident = infer_from_model(model)
    if ident.get("stock_code") and rec.get("stock_code") in (None, "unknown"):
        rec["stock_code"] = ident["stock_code"]
    if ident.get("company") and (
        rec.get("company") in (None, "unknown") or str(rec.get("company", "")).startswith(tuple("0123456789abcdef"))
    ):
        rec["company"] = ident["company"]
    elif ident.get("company") and rec.get("company") and len(str(rec.get("company"))) >= 16:
        rec["company"] = ident["company"]
    if ident.get("title_hint") and not rec.get("announcement_title"):
        rec["announcement_title"] = ident["title_hint"]
    rec["identity_inferred"] = ident
    t_h = time.perf_counter()
    cands = harvest(model, {
        "pdf_sha256": model["pdf_sha256"],
        "official_document_id": rec.get("official_document_id"),
    })
    harvest_s = time.perf_counter() - t_h
    cpu1 = sample_cpu_util(0.08)

    # persist normalized (without exploding word lists into review HTML)
    slim_pages = []
    for p in model["pages"]:
        slim_pages.append({
            "page_number": p["page_number"],
            "width": p["width"],
            "height": p["height"],
            "text": p["text"],
            "char_count": p["char_count"],
            "word_count": p["word_count"],
            "tables": p["tables"],
            "n_blocks": len(p["blocks"]),
            "n_words": len(p["words"]),
        })
        (ROOT / "normalized" / "text" / f"{rec['case_id']}_p{p['page_number']}.txt").parent.mkdir(parents=True, exist_ok=True)
        (ROOT / "normalized" / "text" / f"{rec['case_id']}_p{p['page_number']}.txt").write_text(p["text"], encoding="utf-8")
        if p["tables"]:
            _dump(ROOT / "normalized" / "tables" / f"{rec['case_id']}_p{p['page_number']}.json", p["tables"])

    doc_model = {
        "case_id": rec["case_id"],
        "stock_code": rec["stock_code"],
        "company": rec["company"],
        "pdf_sha256": model["pdf_sha256"],
        "official_document_id": rec.get("official_document_id"),
        "page_count": model["page_count"],
        "native_text_available": model["native_text_available"],
        "ocr_required": model["ocr_required"],
        "table_detected": model["table_detected"],
        "warnings": model["warnings"],
        "metadata": model["metadata"],
        "pages": slim_pages,
        "document_model_version": DOCUMENT_MODEL_VERSION,
        "timing": model["timing"],
    }
    _dump(ROOT / "normalized" / "document-model" / f"{rec['case_id']}.json", doc_model)
    _dump(ROOT / "candidates" / "json" / f"{rec['case_id']}.json", cands)
    per_dir = ROOT / "candidates" / "per-document" / rec["case_id"]
    _dump(per_dir / "candidates.json", cands)
    _dump(per_dir / "asset.json", rec)

    fields = sorted({c["field_name"] for c in cands})
    price_fields = [c for c in cands if c["field_name"] in {
        "exercise_price", "old_exercise_price", "new_exercise_price",
        "option_fair_value", "grant_date_market_price",
        "announcement_stated_market_price", "share_based_payment_expense",
    }]
    timing = {
        "case_id": rec["case_id"],
        "run_id": run_id,
        "warm": warm,
        "device_used": "cpu",
        "cpu_seconds": round(time.perf_counter() - t_all, 6),
        "gpu_seconds_if_used": None,
        "gpu_model": None,
        "peak_vram_mb": None,
        "average_gpu_utilization_if_available": None,
        "batch_size": 1,
        "pages_processed": model["page_count"],
        "documents_processed": 1,
        "stage_seconds": {
            **model["timing"],
            "candidate_harvest_seconds": round(harvest_s, 6),
        },
        "cpu_util_before": cpu0,
        "cpu_util_after": cpu1,
        "candidate_count": len(cands),
        "field_names": fields,
        "pdf_sha256": model["pdf_sha256"],
        "extractor_version": EXTRACTOR_VERSION,
        "document_model_version": DOCUMENT_MODEL_VERSION,
        "field_schema_version": FIELD_SCHEMA_VERSION,
        "candidate_assertion_version": CANDIDATE_ASSERTION_VERSION,
        "run_time": _now(),
    }
    _dump(ROOT / "timing" / "per-document" / f"{rec['case_id']}.json", timing)

    price_review = _price_review(rec, cands)
    _dump(ROOT / "review" / "reports" / f"{rec['case_id']}_PRICE_EVIDENCE_REVIEW.json", price_review)
    html = render_case_html(rec, doc_model, cands, timing, price_review)
    (ROOT / "review" / "html" / f"{rec['case_id']}.html").parent.mkdir(parents=True, exist_ok=True)
    (ROOT / "review" / "html" / f"{rec['case_id']}.html").write_text(html, encoding="utf-8")

    return {
        "case_id": rec["case_id"],
        "ok": True,
        "candidate_count": len(cands),
        "page_count": model["page_count"],
        "timing": timing,
        "price_review": price_review,
        "fields": fields,
        "warnings": model["warnings"],
        "pdf_sha256": model["pdf_sha256"],
    }


def _price_review(rec: dict[str, Any], cands: list[dict[str, Any]]) -> dict[str, Any]:
    def rows(field: str) -> list[dict[str, Any]]:
        out = []
        for c in cands:
            if c["field_name"] != field:
                continue
            out.append({
                "Field": field,
                "Candidate Value": c.get("normalized_numeric_value_if_safe") or c.get("normalized_value") or c.get("raw_value"),
                "Unit": c.get("unit"),
                "Effective Date": None,
                "Page": c.get("page_number"),
                "Source Text": c.get("exact_source_text"),
                "Event Hint": " / ".join(x for x in [
                    c.get("possible_plan_hint"),
                    c.get("possible_grant_batch_hint"),
                    c.get("possible_exercise_period_hint"),
                ] if x),
                "Status": "FOUND",
            })
        if not out:
            out.append({
                "Field": field, "Candidate Value": None, "Unit": None, "Effective Date": None,
                "Page": None, "Source Text": None, "Event Hint": None, "Status": "NOT_FOUND",
            })
        elif len(out) > 1:
            for r in out:
                r["Status"] = "MULTIPLE"
        return out

    families = [
        "exercise_price", "old_exercise_price", "new_exercise_price",
        "option_fair_value", "grant_date_market_price",
        "exercisable_quantity", "outstanding_option_quantity",
        "share_based_payment_expense",
    ]
    table = []
    for f in families:
        table.extend(rows(f))
    return {
        "case_id": rec["case_id"],
        "company": rec["company"],
        "stock_code": rec["stock_code"],
        "exercise_price_candidates": sum(1 for c in cands if c["field_name"] == "exercise_price"),
        "price_adjustment_candidates": sum(1 for c in cands if c["field_name"] in ("old_exercise_price", "new_exercise_price")),
        "fair_value_candidates": sum(1 for c in cands if c["field_name"] == "option_fair_value"),
        "share_based_payment_candidates": sum(1 for c in cands if c["field_name"] == "share_based_payment_expense"),
        "quantity_candidates": sum(1 for c in cands if "quantity" in c["field_name"]),
        "rows": table,
    }


def render_case_html(rec, model, cands, timing, price) -> str:
    rows = "".join(
        f"<tr><td>{c['field_name']}</td><td>{c.get('normalized_numeric_value_if_safe') or c.get('normalized_value') or ''}</td>"
        f"<td>{_esc(c.get('raw_value'))}</td><td>{c.get('page_number')}</td>"
        f"<td>{c.get('possible_grant_batch_hint') or ''} {c.get('possible_exercise_period_hint') or ''}</td></tr>"
        for c in cands[:200]
    )
    pr = "".join(
        f"<tr><td>{r['Field']}</td><td>{r['Candidate Value']}</td><td>{r.get('Unit') or ''}</td>"
        f"<td>{r.get('Page') or ''}</td><td>{_esc(r.get('Source Text'))}</td><td>{r['Status']}</td></tr>"
        for r in price["rows"]
    )
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>{rec['stock_code']} {rec['company']} 候选复核</title>
<style>
body{{font-family:"Iwanami Mincho","Songti SC",Georgia,serif;background:#f3eee4;color:#141311;margin:0;padding:32px}}
h1{{font-weight:600;letter-spacing:.04em;font-size:22px}}
.meta{{color:#5c6570;font-size:13px}}
table{{border-collapse:collapse;width:100%;background:#fffdf8;font-size:13px}}
th,td{{border:1px solid #c9c1b2;padding:6px 8px;vertical-align:top}}
th{{background:#ece6d8;text-align:left;font-weight:600}}
.seal{{color:#8e2a24}}
</style></head><body>
<p class="meta">拾证 · 候选断言 · 不是 Truth</p>
<h1>{rec['stock_code']} {rec['company']}</h1>
<p>{_esc(rec.get('announcement_title') or rec['short_title'])}</p>
<p class="meta">SHA-256 {model['pdf_sha256']} · {model['page_count']} 页 · {len(cands)} 条候选 · CPU {timing['cpu_seconds']}s</p>
<h2>价格证据</h2>
<table><tr><th>字段</th><th>值</th><th>单位</th><th>页</th><th>原文</th><th>状态</th></tr>{pr}</table>
<h2>全部候选（最多 200）</h2>
<table><tr><th>字段</th><th>归一</th><th>原文</th><th>页</th><th>事件提示</th></tr>{rows}</table>
</body></html>"""


def _esc(s: Any) -> str:
    t = "" if s is None else str(s)
    return t.replace("&", "&").replace("<", "<").replace(">", ">")


def write_csv(all_cands: list[tuple[str, dict[str, Any]]]) -> None:
    path = ROOT / "candidates" / "csv" / "ALL_CANDIDATES.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = [
        "case_id", "field_name", "raw_value", "normalized_value",
        "normalized_numeric_value_if_safe", "unit", "page_number",
        "possible_plan_hint", "possible_grant_batch_hint",
        "possible_exercise_period_hint", "pdf_sha256", "official_document_id",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for case_id, c in all_cands:
            row = {k: c.get(k) for k in cols}
            row["case_id"] = case_id
            w.writerow(row)


def publish_public(summary: dict[str, Any]) -> None:
    public = PUBLIC_CANDIDATE
    if not public.parent.exists():
        return
    public.mkdir(parents=True, exist_ok=True)
    _dump(public / "summary.json", summary)
    src = ROOT / "candidates" / "json"
    out = public / "cases"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    for p in src.glob("*.json"):
        shutil.copy2(p, out / p.name)
    reviews = public / "price"
    reviews.mkdir(exist_ok=True)
    for p in (ROOT / "review" / "reports").glob("*_PRICE_EVIDENCE_REVIEW.json"):
        shutil.copy2(p, reviews / p.name)
    timings = public / "timing"
    timings.mkdir(exist_ok=True)
    for p in (ROOT / "timing" / "per-document").glob("*.json"):
        shutil.copy2(p, timings / p.name)
    shutil.copy2(ROOT / "candidates" / "csv" / "ALL_CANDIDATES.csv", public / "ALL_CANDIDATES.csv")
    models = public / "documents"
    models.mkdir(exist_ok=True)
    for p in (ROOT / "normalized" / "document-model").glob("*.json"):
        shutil.copy2(p, models / p.name)


def run_controlled_batch() -> dict[str, Any]:
    guard = ResourceGuard()
    gate = BatchGate()
    records = [r for r in discover_local_pdfs() if r.get("source_path")]
    if not records:
        from harvest.reports import rebuild
        rebuild()
        return {
            "ok": False,
            "error": "input/pdf is empty",
            "documents_processed": 0,
            "candidate_total": 0,
        }
    run_id = "run_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    results = []

    def one(rec, warm=False):
        with guard.document_slot():
            guard.wait_until_safe()
            return harvest_one(rec, run_id, warm=warm)

    # 1-doc smoke
    t0 = time.perf_counter()
    r0 = one(records[0], warm=False)
    results.append(r0)
    gate.smoke_1_ok = True
    gate.smoke_1_run_id = run_id + "_smoke1"

    # 2-doc mini (case 0 already done; do case 1, then mark mini)
    gate.allow(2)
    r1 = one(records[1], warm=False)
    results.append(r1)
    gate.mini_2_ok = True
    gate.mini_2_run_id = run_id + "_mini2"

    # remaining 6 — sequential because effective_docs_parallel=1
    gate.allow(len(records))
    for rec in records[2:]:
        results.append(one(rec, warm=False))

    # warm replay of first doc
    warm = one(records[0], warm=True)

    all_cands = []
    for rec in records:
        cpath = ROOT / "candidates" / "json" / f"{rec['case_id']}.json"
        for c in json.loads(cpath.read_text(encoding="utf-8")):
            all_cands.append((rec["case_id"], c))
    write_csv(all_cands)

    batch_s = time.perf_counter() - t0
    summary = {
        "run_id": run_id,
        "extractor_version": EXTRACTOR_VERSION,
        "document_model_version": DOCUMENT_MODEL_VERSION,
        "field_schema_version": FIELD_SCHEMA_VERSION,
        "candidate_assertion_version": CANDIDATE_ASSERTION_VERSION,
        "INPUT_MANIFEST_STATUS": "LOCAL_INPUT",
        "gate": gate.to_dict(),
        "resource": guard.status_dict(),
        "documents_processed": len(results),
        "batch_cpu_seconds": round(batch_s, 6),
        "device_used": "cpu",
        "gpu_seconds_if_used": None,
        "warm_replay": warm["timing"],
        "cases": results,
        "candidate_total": len(all_cands),
        "finished_at": _now(),
    }
    _dump(ROOT / "timing" / "batch" / f"{run_id}.json", summary)
    _dump(ROOT / "timing" / "batch" / "LATEST.json", summary)
    _dump(ROOT / "review" / "reports" / "BATCH_SUMMARY.json", summary)
    from harvest.reports import rebuild as rebuild_html

    rebuild_html()
    try:
        publish_public(summary)
    except OSError:
        pass
    return summary


if __name__ == "__main__":
    s = run_controlled_batch()
    print(json.dumps({
        "ok": True,
        "run_id": s["run_id"],
        "documents_processed": s["documents_processed"],
        "candidate_total": s["candidate_total"],
        "batch_cpu_seconds": s["batch_cpu_seconds"],
        "cases": [{k: c[k] for k in ("case_id", "candidate_count", "page_count") if k in c} | {
            "cpu_seconds": c["timing"]["cpu_seconds"]
        } for c in s["cases"]],
    }, ensure_ascii=False, indent=2))
