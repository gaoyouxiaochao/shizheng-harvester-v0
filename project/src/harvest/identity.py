"""Infer stock code / company from announcement text. Hash filenames have no names."""

from __future__ import annotations

import re
from typing import Any

KNOWN = {
    "603162": "海通发展",
    "603893": "瑞芯微",
    "002134": "天津普林",
    "002463": "沪电股份",
    "603598": "引力传媒",
    "300124": "汇川技术",
    "600186": "莲花控股",
    "600570": "恒生电子",
}

CODE_LABEL = re.compile(
    r"(?:证券代码|股票代码|A股代码|股票代码)\s*[：:]\s*(\d{6})"
)
CODE_DOT = re.compile(r"\b(\d{6})\.(?:SH|SZ|BJ|sh|sz|bj)\b")
SHORT_LABEL = re.compile(
    r"(?:证券简称|股票简称)\s*[：:]\s*([^\s，。；;（(]{2,20})"
)
TITLE_HINT = re.compile(r"关于.{4,80}(?:公告|通知)")


def infer_from_text(text: str) -> dict[str, str | None]:
    blob = text or ""
    head = blob[:4000]
    code = None
    m = CODE_LABEL.search(head) or CODE_LABEL.search(blob)
    if m:
        code = m.group(1)
    if not code:
        m = CODE_DOT.search(head)
        if m:
            code = m.group(1)
    if not code:
        for k in KNOWN:
            if k in head:
                code = k
                break
    company = None
    m = SHORT_LABEL.search(head) or SHORT_LABEL.search(blob)
    if m:
        company = m.group(1).strip()
    if code and code in KNOWN:
        company = company or KNOWN[code]
    title = None
    m = TITLE_HINT.search(head)
    if m:
        title = m.group(0).strip()
    return {"stock_code": code, "company": company, "title_hint": title}


def infer_from_model(model: dict[str, Any]) -> dict[str, str | None]:
    pages = model.get("pages") or []
    text = "\n".join((p.get("text") or "") for p in pages[:3])
    if not text.strip():
        text = model.get("full_text") or ""
    return infer_from_text(text)
