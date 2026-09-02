"""Rebuild human review HTML from harvested JSON."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from harvest.identity import infer_from_text

ROOT = Path(__file__).resolve().parents[3]


def _esc(s: Any) -> str:
    t = "" if s is None else str(s)
    return t.replace("&", "&").replace("<", "<").replace(">", ">")


def _load(path: Path) -> Any | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _label(case_id: str, model: dict[str, Any]) -> tuple[str, str]:
    code = str(model.get("stock_code") or "")
    company = str(model.get("company") or "")
    if not code or code == "unknown" or company.startswith(tuple("0123456789abcdef")):
        pages = model.get("pages") or []
        ident = infer_from_text("\n".join((p.get("text") or "") for p in pages[:3]))
        code = ident.get("stock_code") or code or case_id
        company = ident.get("company") or company or "未识别"
        if ident.get("title_hint"):
            model["announcement_title"] = ident["title_hint"]
        model["stock_code"] = code
        model["company"] = company
    return code, company


def write_case_html(case_id: str) -> Path | None:
    cands = _load(ROOT / "candidates" / "json" / f"{case_id}.json")
    if cands is None:
        return None
    price = _load(ROOT / "review" / "reports" / f"{case_id}_PRICE_EVIDENCE_REVIEW.json") or {"rows": []}
    timing = _load(ROOT / "timing" / "per-document" / f"{case_id}.json") or {}
    model_path = ROOT / "normalized" / "document-model" / f"{case_id}.json"
    model = _load(model_path) or {}
    code, name = _label(case_id, model)
    if model_path.exists():
        model_path.write_text(json.dumps(model, ensure_ascii=False, indent=2), encoding="utf-8")
    title = model.get("announcement_title") or ""
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
<title>{_esc(code)} {_esc(name)}</title>
<style>
body{{font-family:"Microsoft YaHei",sans-serif;background:#f3eee4;color:#141311;margin:0;padding:32px}}
h1{{font-weight:600;font-size:22px}}
.meta{{color:#5c6570;font-size:13px}}
table{{border-collapse:collapse;width:100%;background:#fffdf8;font-size:13px}}
th,td{{border:1px solid #c9c1b2;padding:6px 8px;vertical-align:top}}
th{{background:#ece6d8;text-align:left}}
a{{color:#8e2a24}}
</style></head><body>
<p class="meta"><a href="index.html">返回总览</a> · 拾证 · 候选不等于 Truth</p>
<h1>{_esc(code)} {_esc(name)}</h1>
<p class="meta">{_esc(title)}</p>
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
    cards = []
    json_dir = ROOT / "candidates" / "json"
    for p in sorted(json_dir.glob("*.json")):
        cid = p.stem
        model = _load(ROOT / "normalized" / "document-model" / f"{cid}.json") or {}
        timing = _load(ROOT / "timing" / "per-document" / f"{cid}.json") or {}
        cands = _load(p) or []
        code, name = _label(cid, model)
        sec = timing.get("cpu_seconds") or 0
        try:
            sec_s = f"{float(sec):.2f}s"
        except (TypeError, ValueError):
            sec_s = ""
        cards.append(
            f'<a class="card" href="{cid}.html"><div class="id">{cid}</div>'
            f"<h2>{_esc(code)} {_esc(name)}</h2>"
            f"<p>{len(cands)} 条候选 · {_esc(model.get('page_count') or timing.get('pages_processed') or '')} 页 · {sec_s}</p></a>"
        )
    html = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>拾证 复核台</title>
<style>
body{{margin:0;background:#f3eee4;color:#141311;font-family:"Microsoft YaHei",sans-serif;padding:32px}}
h1{{font-weight:600}}
.grid{{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(240px,1fr))}}
.card{{display:block;border:1px solid #c9c1b2;background:#fffdf8;padding:16px;text-decoration:none;color:inherit;border-radius:12px}}
.id{{font-family:Consolas,monospace;font-size:12px;color:#5c6570}}
.meta{{color:#5c6570;font-size:13px}}
</style></head><body>
<p class="meta">拾证 · 候选不等于 Truth</p>
<h1>复核总览</h1>
<p class="meta">{len(cards)} 份文档。哈希文件名会从公告正文识别证券代码/简称。</p>
<div class="grid">{''.join(cards) if cards else '<p>把 PDF 放进 input\\pdf，然后双击 run.bat</p>'}</div>
</body></html>"""
    dest = ROOT / "review" / "html" / "index.html"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(html, encoding="utf-8")
    return dest


def rebuild() -> dict[str, Any]:
    written = []
    json_dir = ROOT / "candidates" / "json"
    if json_dir.exists():
        for p in sorted(json_dir.glob("*.json")):
            path = write_case_html(p.stem)
            if path:
                written.append(str(path))
    index = write_index()
    return {"ok": True, "index": str(index), "cases": written}
