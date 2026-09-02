"""Rebuild human review HTML from harvested JSON. No pymupdf required."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
META = {
    "C01": ("603162", "海通发展"),
    "C02": ("603893", "瑞芯微"),
    "C03": ("002134", "天津普林"),
    "C04": ("002463", "沪电股份"),
    "C05": ("603598", "引力传媒"),
    "C06": ("300124", "汇川技术"),
    "C07": ("600186", "莲花控股"),
    "C08": ("600570", "恒生电子"),
}


def _esc(s: Any) -> str:
    t = "" if s is None else str(s)
    return t.replace("&", "&").replace("<", "<").replace(">", ">")


def _load(path: Path) -> Any | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_case_html(case_id: str) -> Path | None:
    cands = _load(ROOT / "candidates" / "json" / f"{case_id}.json")
    if cands is None:
        return None
    price = _load(ROOT / "review" / "reports" / f"{case_id}_PRICE_EVIDENCE_REVIEW.json") or {"rows": []}
    timing = _load(ROOT / "timing" / "per-document" / f"{case_id}.json") or {}
    model = _load(ROOT / "normalized" / "document-model" / f"{case_id}.json") or {}
    code, name = META.get(case_id, (case_id, case_id))
    rows = "".join(
        f"<tr><td>{_esc(c.get('field_name'))}</td>"
        f"<td>{_esc(c.get('normalized_numeric_value_if_safe') or c.get('normalized_value') or '')}</td>"
        f"<td>{_esc(c.get('raw_value'))}</td><td>{_esc(c.get('page_number'))}</td>"
        f"<td>{_esc(c.get('possible_grant_batch_hint'))} {_esc(c.get('possible_exercise_period_hint'))}</td></tr>"
        for c in cands[:200]
    )
    pr = "".join(
        f"<tr><td>{_esc(r.get('Field'))}</td><td>{_esc(r.get('Candidate Value'))}</td>"
        f"<td>{_esc(r.get('Unit'))}</td><td>{_esc(r.get('Page'))}</td>"
        f"<td>{_esc(r.get('Source Text'))}</td><td>{_esc(r.get('Status'))}</td></tr>"
        for r in price.get("rows") or []
    )
    html = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<title>{code} {name} 候选复核</title>
<style>
body{{font-family:"Songti SC",Georgia,serif;background:#f3eee4;color:#141311;margin:0;padding:32px}}
h1{{font-weight:600;font-size:22px}}
.meta{{color:#5c6570;font-size:13px}}
table{{border-collapse:collapse;width:100%;background:#fffdf8;font-size:13px}}
th,td{{border:1px solid #c9c1b2;padding:6px 8px;vertical-align:top}}
th{{background:#ece6d8;text-align:left}}
a{{color:#8e2a24}}
</style></head><body>
<p class="meta"><a href="index.html">返回总览</a> · 拾证 · 候选不等于 Truth</p>
<h1>{code} {name}</h1>
<p class="meta">SHA-256 {_esc(model.get('pdf_sha256'))} · {_esc(model.get('page_count') or timing.get('pages_processed'))} 页 · {len(cands)} 条候选 · CPU {_esc(timing.get('cpu_seconds'))}s</p>
<h2>价格证据</h2>
<table><tr><th>字段</th><th>值</th><th>单位</th><th>页</th><th>原文</th><th>状态</th></tr>{pr}</table>
<h2>全部候选（最多 200）</h2>
<table><tr><th>字段</th><th>归一</th><th>原文</th><th>页</th><th>事件提示</th></tr>{rows}</table>
</body></html>"""
    dest = ROOT / "review" / "html" / f"{case_id}.html"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(html, encoding="utf-8")
    return dest


def write_index() -> Path:
    summary = _load(ROOT / "timing" / "batch" / "LATEST.json") or _load(
        ROOT / "review" / "reports" / "BATCH_SUMMARY.json"
    ) or {}
    cases = summary.get("cases") or []
    if not cases:
        for p in sorted((ROOT / "candidates" / "json").glob("C*.json")):
            cases.append({"case_id": p.stem, "candidate_count": len(_load(p) or []), "page_count": "?", "timing": {"cpu_seconds": 0}})
    cards = []
    for c in cases:
        cid = c["case_id"]
        code, name = META.get(cid, (cid, cid))
        sec = (c.get("timing") or {}).get("cpu_seconds") or 0
        cards.append(
            f'<a class="card" href="{cid}.html"><div class="id">{cid}</div>'
            f"<h2>{code} {name}</h2><p>{c.get('candidate_count')} 条候选 · {c.get('page_count')} 页 · {sec:.2f}s</p></a>"
        )
    html = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>拾证 复核台</title>
<style>
body{{margin:0;background:#f3eee4;color:#141311;font-family:"Songti SC",Georgia,serif;padding:32px}}
h1{{font-weight:600}}
.grid{{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(240px,1fr))}}
.card{{display:block;border:1px solid #c9c1b2;background:#fffdf8;padding:16px;text-decoration:none;color:inherit;border-radius:12px}}
.id{{font-family:ui-monospace,monospace;font-size:12px;color:#5c6570}}
.meta{{color:#5c6570;font-size:13px}}
</style></head><body>
<p class="meta">拾证 · 候选不等于 Truth</p>
<h1>八案复核</h1>
<p class="meta">{_esc(summary.get('run_id') or 'local')} · {_esc(summary.get('candidate_total') or '')} 条候选 · CPU {_esc(summary.get('batch_cpu_seconds'))}s</p>
<div class="grid">{''.join(cards) if cards else '<p>还没有候选结果。请先双击 启动抽取.bat</p>'}</div>
</body></html>"""
    dest = ROOT / "review" / "html" / "index.html"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(html, encoding="utf-8")
    return dest


def rebuild() -> dict[str, Any]:
    written = []
    json_dir = ROOT / "candidates" / "json"
    if json_dir.exists():
        for p in sorted(json_dir.glob("C*.json")):
            path = write_case_html(p.stem)
            if path:
                written.append(str(path))
    index = write_index()
    return {
        "ok": True,
        "index": str(index),
        "cases": written,
        "root": str(ROOT),
    }


if __name__ == "__main__":
    print(json.dumps(rebuild(), ensure_ascii=False, indent=2))
