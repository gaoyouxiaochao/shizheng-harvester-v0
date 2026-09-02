# -*- coding: utf-8 -*-
"""Rewrite X*.html titles from already-normalized page text. No pymupdf."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "project" / "src"))
from harvest.identity import infer_from_text  # noqa: E402

MODELS = HERE / "normalized" / "document-model"
HTML = HERE / "review" / "html"
H1 = re.compile(r"<h1>.*?</h1>", re.S)


def main() -> int:
    n = 0
    for path in sorted(MODELS.glob("*.json")):
        model = json.loads(path.read_text(encoding="utf-8"))
        pages = model.get("pages") or []
        text = "\n".join((p.get("text") or "") for p in pages[:3])
        ident = infer_from_text(text)
        code = ident.get("stock_code") or model.get("stock_code") or "unknown"
        company = ident.get("company") or ""
        if company.startswith(tuple("0123456789abcdef")) or company in ("unknown", ""):
            company = ident.get("company") or "未识别公司"
        title = ident.get("title_hint") or ""
        heading = f"{code} {company}".strip()
        if title:
            heading += f" · {title[:40]}"
        html_path = HTML / f"{path.stem}.html"
        if html_path.exists():
            raw = html_path.read_text(encoding="utf-8")
            raw2, k = H1.subn(f"<h1>{heading}</h1>", raw, count=1)
            if k:
                html_path.write_text(raw2, encoding="utf-8")
        model["stock_code"] = code
        model["company"] = company
        if title:
            model["announcement_title"] = title
        path.write_text(json.dumps(model, ensure_ascii=False, indent=2), encoding="utf-8")
        print(path.stem, heading)
        n += 1
    from generate_index import main as rebuild
    rebuild()
    print("remapped", n)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
