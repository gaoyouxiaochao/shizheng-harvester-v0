"""Deterministic Chinese number / date / money parsers. No LLM."""

from __future__ import annotations

import re
from typing import Any

CN_DIGIT = {
    "零": 0, "〇": 0, "○": 0, "Ｏ": 0,
    "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
}
CN_ORD = {**CN_DIGIT, "十": 10}

SPACE_RE = re.compile(r"[\s\u00a0\u3000]+")
# 2026 年8 月28 日  / 2026年8月28日 / 2026-08-28
DATE_RE = re.compile(
    r"(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"
)
ISO_DATE_RE = re.compile(r"(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})")
NUM_RE = re.compile(r"[-+]?\d{1,3}(?:,\d{3})*(?:\.\d+)?|[-+]?\d+(?:\.\d+)?")
PRICE_RE = re.compile(
    r"(-?\d{1,3}(?:,\d{3})*(?:\.\d+)?|-?\d+(?:\.\d+)?)\s*元\s*/\s*(份|股|权)"
)
WAN_RE = re.compile(
    r"(-?\d{1,3}(?:,\d{3})*(?:\.\d+)?|-?\d+(?:\.\d+)?)\s*万\s*(份|股|股股票期权)?"
)
ORDINAL_RE = re.compile(r"第\s*([一二三四五六七八九十百零\d]+)\s*个")
PERIOD_RE = re.compile(
    r"第\s*([一二三四五六七八九十百零\d]+)\s*期"
)


def squeeze(s: str) -> str:
    return SPACE_RE.sub("", s or "")


def parse_cn_int(token: str) -> int | None:
    token = squeeze(token)
    if not token:
        return None
    if token.isdigit():
        return int(token)
    if token in CN_DIGIT:
        return CN_DIGIT[token]
    # 十 / 十一 / 二十 / 二十一
    if "十" in token:
        if token == "十":
            return 10
        left, _, right = token.partition("十")
        a = CN_DIGIT.get(left, 1 if left == "" else None)
        b = CN_DIGIT.get(right, 0 if right == "" else None)
        if a is None or b is None:
            return None
        return a * 10 + b
    return None


def parse_number(raw: str) -> float | None:
    t = (raw or "").replace(",", "").replace("，", "").strip()
    t = t.replace(" ", "")
    if not t:
        return None
    try:
        return float(t)
    except ValueError:
        return None


def parse_date(text: str) -> str | None:
    if not text:
        return None
    m = DATE_RE.search(text)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{y:04d}-{mo:02d}-{d:02d}"
    m = ISO_DATE_RE.search(squeeze(text))
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{y:04d}-{mo:02d}-{d:02d}"
    return None


def parse_price(text: str) -> dict[str, Any] | None:
    m = PRICE_RE.search(text or "")
    if not m:
        return None
    n = parse_number(m.group(1))
    if n is None:
        return None
    unit = m.group(2)
    share_unit = "share" if unit in ("份", "股", "权") else unit
    return {
        "normalized_numeric_value": n,
        "currency": "CNY",
        "unit": f"元/{unit}",
        "per_share_or_total": "per_share",
        "raw": m.group(0),
    }


def parse_wan_quantity(text: str) -> dict[str, Any] | None:
    m = WAN_RE.search(text or "")
    if not m:
        return None
    n = parse_number(m.group(1))
    if n is None:
        return None
    unit = (m.group(2) or "份").replace("股股票期权", "份")
    return {
        "normalized_numeric_value": n * 10000.0,
        "display_wan": n,
        "unit": unit,
        "scale": "wan",
        "raw": m.group(0),
    }


def parse_ordinal(text: str) -> int | None:
    m = ORDINAL_RE.search(text or "")
    if not m:
        return None
    return parse_cn_int(m.group(1))


def grant_batch_hint(text: str) -> str:
    t = text or ""
    has_res = "预留" in t
    has_first = "首次授予" in t or "首次授予部分" in t
    if has_res and has_first:
        return "FIRST_AND_RESERVED"
    if has_res:
        return "RESERVED"
    if has_first:
        return "FIRST"
    return "UNKNOWN"


def plan_year_hint(text: str) -> str | None:
    m = re.search(r"(20\d{2})\s*年", text or "")
    return m.group(1) if m else None


def exercise_mode_hint(text: str) -> str | None:
    t = text or ""
    if "自主行权" in t:
        return "AUTONOMOUS"
    if "集中行权" in t:
        return "CENTRALIZED"
    return None
