"""Full-document candidate harvest. Keep ambiguity. Never collapse to one event."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from harvest.chinese import (
    exercise_mode_hint,
    grant_batch_hint,
    parse_cn_int,
    parse_date,
    parse_number,
    parse_ordinal,
    parse_price,
    parse_wan_quantity,
    plan_year_hint,
    squeeze,
)

PRICE_EXCLUDE = ("公允价值", "股份支付", "收盘价", "均价", "市价", "授予日股票", "Black-Scholes", "B-S")
FAIR_VALUE_MARK = ("公允价值", "期权价值", "Black-Scholes", "B-S模型", "BS模型")
MARKET_MARK = ("收盘价", "均价", "市价", "交易均价", "授予日股票价格")


def _cid(pdf_sha: str, field: str, page: int, raw: str, bbox: list | None) -> str:
    key = f"{pdf_sha}|{field}|{page}|{raw}|{bbox}"
    return "CAND_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def _window(text: str, start: int, end: int, n: int = 80) -> tuple[str, str]:
    a = max(0, start - n)
    b = min(len(text), end + n)
    return text[a:start], text[end:b]


def _page_for_offset(pages: list[dict[str, Any]], offset: int) -> int:
    cur = 0
    for p in pages:
        nxt = cur + len(p.get("text") or "") + 1
        if offset < nxt:
            return int(p["page_number"])
        cur = nxt
    return pages[-1]["page_number"] if pages else 1


def _word_bbox_near(page: dict[str, Any], snippet: str) -> list[float] | None:
    needle = squeeze(snippet)[:12]
    if not needle:
        return None
    acc = ""
    boxes = []
    for w in page.get("words") or []:
        acc += w["text"]
        boxes.append(w["bbox"])
        if needle in squeeze(acc):
            xs0 = [b[0] for b in boxes[-8:]]
            ys0 = [b[1] for b in boxes[-8:]]
            xs1 = [b[2] for b in boxes[-8:]]
            ys1 = [b[3] for b in boxes[-8:]]
            return [min(xs0), min(ys0), max(xs1), max(ys1)]
        if len(acc) > 80:
            acc = acc[-40:]
            boxes = boxes[-6:]
    return None


def _base(meta: dict[str, Any], field: str, raw: str, page: int, before: str, after: str, extra: dict[str, Any]) -> dict[str, Any]:
    bbox = extra.pop("bbox", None)
    notes = extra.pop("ambiguity_notes", [])
    if not isinstance(notes, list):
        notes = [str(notes)]
    cand = {
        "candidate_id": _cid(meta["pdf_sha256"], field, page, raw, bbox),
        "field_name": field,
        "raw_value": raw.strip(),
        "normalized_value": extra.pop("normalized_value", None),
        "normalized_numeric_value_if_safe": extra.pop("normalized_numeric_value_if_safe", None),
        "currency": extra.pop("currency", None),
        "unit": extra.pop("unit", None),
        "per_share_or_total": extra.pop("per_share_or_total", None),
        "page_number": page,
        "bbox": bbox,
        "table_id": extra.pop("table_id", None),
        "row_label": extra.pop("row_label", None),
        "column_label": extra.pop("column_label", None),
        "exact_source_text": raw.strip(),
        "context_before": before[-80:],
        "context_after": after[:80],
        "possible_plan_hint": extra.pop("possible_plan_hint", None),
        "possible_grant_batch_hint": extra.pop("possible_grant_batch_hint", None),
        "possible_exercise_period_hint": extra.pop("possible_exercise_period_hint", None),
        "adjustment_sequence_hint": extra.pop("adjustment_sequence_hint", None),
        "pdf_sha256": meta["pdf_sha256"],
        "official_document_id": meta.get("official_document_id"),
        "ambiguity_notes": notes,
        "extractor": "deterministic_gazetteer_v1",
        "schema_version": "candidate-assertion-v1",
    }
    cand.update(extra)
    return cand


def _hint_pack(local: str) -> dict[str, Any]:
    ep = parse_ordinal(local) if "行权期" in local else None
    return {
        "possible_plan_hint": plan_year_hint(local),
        "possible_grant_batch_hint": grant_batch_hint(local),
        "possible_exercise_period_hint": f"EP{ep}" if ep else None,
    }


def harvest(model: dict[str, Any], meta: dict[str, Any]) -> list[dict[str, Any]]:
    pages = model["pages"]
    full = model["full_text"]
    cands: list[dict[str, Any]] = []

    def add(field: str, raw: str, start: int, end: int, extra: dict[str, Any]) -> None:
        page = extra.pop("page_number", None) or _page_for_offset(pages, start)
        before, after = _window(full, start, end)
        local = (before + raw + after)
        extra.setdefault("possible_plan_hint", plan_year_hint(local))
        extra.setdefault("possible_grant_batch_hint", grant_batch_hint(local))
        if extra.get("possible_exercise_period_hint") is None:
            ep = parse_ordinal(local) if "行权期" in local else None
            extra["possible_exercise_period_hint"] = f"EP{ep}" if ep else None
        page_obj = next((p for p in pages if p["page_number"] == page), None)
        if page_obj and extra.get("bbox") is None:
            extra["bbox"] = _word_bbox_near(page_obj, raw)
        cands.append(_base(meta, field, raw, page, before, after, extra))

    # Identity from first page header
    p1 = pages[0]["text"] if pages else ""
    m = re.search(r"证券代码[：:]\s*(\d{6})", p1)
    if m:
        add("stock_code", m.group(1), full.find(m.group(0)), full.find(m.group(0)) + len(m.group(0)),
            {"normalized_value": m.group(1)})
    m = re.search(r"证券简称[：:]\s*([^\s\n]{2,12})", p1)
    if m:
        add("company", m.group(1), full.find(m.group(0)), full.find(m.group(0)) + len(m.group(0)),
            {"normalized_value": m.group(1)})
    # title: first long 公告 line
    for line in p1.splitlines():
        s = line.strip()
        if "公告" in s and len(s) >= 8 and "保证" not in s and "编号" not in s:
            idx = full.find(s)
            if idx >= 0:
                atype = "UNKNOWN"
                if "行权条件成就" in s:
                    atype = "EXERCISE_CONDITION_ACHIEVED"
                elif "自主行权实施" in s:
                    atype = "AUTONOMOUS_EXERCISE_IMPLEMENTATION"
                elif "提示性公告" in s and "自主行权" in s:
                    atype = "AUTONOMOUS_EXERCISE_NOTICE"
                elif "调整" in s and "行权价格" in s:
                    atype = "EXERCISE_PRICE_ADJUSTMENT"
                elif "注销" in s:
                    atype = "CANCELLATION"
                add("announcement_title", s, idx, idx + len(s), {"normalized_value": s})
                add("announcement_type_candidate", atype, idx, idx + len(s), {"normalized_value": atype})
                break

    # Plan names
    for m in re.finditer(r"(20\d{2}\s*年(?:第[一二三四五六七八九十\d]+期)?[^\n]{0,20}(?:股票期权|股权激励)[^\n]{0,24}(?:激励计划)?)", full):
        raw = re.sub(r"\s+", "", m.group(1))
        extra = {"normalized_value": raw, "possible_plan_hint": plan_year_hint(raw)}
        add("plan_name", m.group(1), m.start(), m.end(), extra)

    for m in re.finditer(r"第\s*([一二三四五六七八九十\d]+)\s*期[^\n]{0,8}股权激励计划", full):
        n = parse_cn_int(m.group(1))
        add("plan_sequence", m.group(0), m.start(), m.end(), {"normalized_value": n, "normalized_numeric_value_if_safe": n})

    for m in re.finditer(r"(20\d{2})\s*年", full):
        # only near 激励/期权 to reduce noise
        ctx = full[max(0, m.start() - 8): m.end() + 16]
        if any(k in ctx for k in ("激励", "期权", "授予")):
            add("plan_year", m.group(1), m.start(), m.end(), {"normalized_value": m.group(1)})

    # Grant batch labels — keep both
    for m in re.finditer(r"(预留授予(?:部分|股票期权)?|首次授予(?:部分|股票期权)?)", full):
        batch = "RESERVED" if "预留" in m.group(1) else "FIRST"
        add("grant_batch", m.group(1), m.start(), m.end(), {"normalized_value": batch})

    # Exercise periods
    for m in re.finditer(r"第\s*([一二三四五六七八九十\d]+)\s*个行权期", full):
        n = parse_cn_int(m.group(1))
        add("exercise_period_no", m.group(0), m.start(), m.end(), {
            "normalized_value": n,
            "normalized_numeric_value_if_safe": n,
            "possible_exercise_period_hint": f"EP{n}" if n else None,
        })
        add("exercise_period_label", m.group(0), m.start(), m.end(), {"normalized_value": m.group(0).replace(" ", "")})

    # Mode / condition
    for m in re.finditer(r"自主行权", full):
        add("exercise_mode", "自主行权", m.start(), m.end(), {"normalized_value": "AUTONOMOUS"})
    for m in re.finditer(r"集中行权", full):
        add("exercise_mode", "集中行权", m.start(), m.end(), {"normalized_value": "CENTRALIZED"})
    for m in re.finditer(r"行权条件成就", full):
        add("condition_status", "行权条件成就", m.start(), m.end(), {"normalized_value": "ACHIEVED"})
    for m in re.finditer(r"行权条件未成就|未达到行权条件", full):
        add("condition_status", m.group(0), m.start(), m.end(), {"normalized_value": "NOT_ACHIEVED"})

    # Date ranges 2026 年8 月28 日至2027 年8 月20 日
    range_re = re.compile(
        r"(20\d{2}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)\s*[至到\-—]\s*(20\d{2}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)"
    )
    for m in range_re.finditer(full):
        ctx = full[max(0, m.start() - 40): m.end() + 20]
        d0, d1 = parse_date(m.group(1)), parse_date(m.group(2))
        field_s, field_e = "exercise_start_date", "exercise_end_date"
        if "等待期" in ctx:
            field_s, field_e = "waiting_end_date", "waiting_end_date"
        add(field_s, m.group(1), m.start(1), m.end(1), {"normalized_value": d0})
        add(field_e, m.group(2), m.start(2), m.end(2), {"normalized_value": d1})

    for m in re.finditer(r"(?:开始行权|行权起始|可行权日|将于)[^\n]{0,12}(20\d{2}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)", full):
        add("exercise_start_date", m.group(1), m.start(1), m.end(1), {"normalized_value": parse_date(m.group(1))})

    # Prices — keep semantic split
    for m in re.finditer(r"([\d.,]+)\s*元\s*/\s*(份|股)", full):
        ctx = full[max(0, m.start() - 50): m.end() + 30]
        price = parse_price(m.group(0))
        n = price["normalized_numeric_value"] if price else parse_number(m.group(1))
        extra = {
            "normalized_numeric_value_if_safe": n,
            "currency": "CNY",
            "unit": f"元/{m.group(2)}",
            "per_share_or_total": "per_share",
        }
        if any(k in ctx for k in FAIR_VALUE_MARK):
            add("option_fair_value", m.group(0), m.start(), m.end(), extra)
        elif any(k in ctx for k in MARKET_MARK):
            if "授予日" in ctx:
                add("grant_date_market_price", m.group(0), m.start(), m.end(), extra)
            else:
                add("announcement_stated_market_price", m.group(0), m.start(), m.end(), extra)
        elif "调整前" in ctx or "原行权价格" in ctx:
            extra["adjustment_sequence_hint"] = "OLD"
            add("old_exercise_price", m.group(0), m.start(), m.end(), extra)
        elif "调整后" in ctx or "现调整为" in ctx:
            extra["adjustment_sequence_hint"] = "NEW"
            add("new_exercise_price", m.group(0), m.start(), m.end(), extra)
        elif "行权价格" in ctx or "行权价" in ctx:
            add("exercise_price", m.group(0), m.start(), m.end(), extra)
        else:
            extra["ambiguity_notes"] = ["price_without_row_label"]
            add("exercise_price", m.group(0), m.start(), m.end(), extra)

    for m in re.finditer(r"行权价格[^\n]{0,12}(?:调整[为至]|现为)[^\n]{0,8}([\d.,]+)\s*元", full):
        n = parse_number(m.group(1))
        add("new_exercise_price", m.group(0), m.start(), m.end(), {
            "normalized_numeric_value_if_safe": n, "currency": "CNY", "unit": "元/份",
            "per_share_or_total": "per_share", "adjustment_sequence_hint": "NEW",
        })

    if "Black-Scholes" in full or "B-S" in full or "BS模型" in squeeze(full):
        idx = full.find("Black-Scholes")
        if idx < 0:
            idx = full.find("B-S")
        add("valuation_model", "Black-Scholes", idx, idx + 13, {"normalized_value": "Black-Scholes"})

    # Quantities
    qty_pats = [
        (r"(?:拟行权数量|可行权数量|本次[^\n]{0,6}行权数量)[：:为]?\s*([\d.,]+)\s*万\s*份", "exercisable_quantity"),
        (r"(?:获授的?股票期权数量|已获授[^\n]{0,6}数量)[：:为]?\s*([\d.,]+)\s*万\s*份", "outstanding_option_quantity"),
        (r"注销[^\n]{0,10}([\d.,]+)\s*万\s*份", "cancelled_quantity"),
    ]
    for pat, field in qty_pats:
        for m in re.finditer(pat, full):
            q = parse_wan_quantity(m.group(0))
            add(field, m.group(0), m.start(), m.end(), {
                "normalized_numeric_value_if_safe": q["normalized_numeric_value"] if q else parse_number(m.group(1)),
                "unit": "份",
                "per_share_or_total": "total",
            })

    for m in re.finditer(r"(\d+)\s*名激励对象", full):
        n = parse_number(m.group(1))
        add("incentive_object_count", m.group(0), m.start(), m.end(), {
            "normalized_numeric_value_if_safe": n, "normalized_value": n, "unit": "人",
        })

    for m in re.finditer(r"定向发行(?:公司)?(?:A\s*股)?(?:普通股)?股票", full):
        add("share_source", m.group(0), m.start(), m.end(), {"normalized_value": "NEW_ISSUE"})
    for m in re.finditer(r"回购(?:公司)?股票", full):
        add("share_source", m.group(0), m.start(), m.end(), {"normalized_value": "REPURCHASE"})

    for m in re.finditer(r"(不得在下列期间内行权|窗口期|敏感期|定期报告公告前)", full):
        add("window_period_note", m.group(0), m.start(), m.end(), {"normalized_value": m.group(0)})

    # Table cell harvest — preserve row/col
    for p in pages:
        for tab in p.get("tables") or []:
            cells = tab.get("cells") or []
            header = cells[0] if cells else []
            for ri, row in enumerate(cells):
                row_txt = " ".join(str(c or "") for c in row)
                for ci, cell in enumerate(row):
                    val = str(cell or "").strip()
                    if not val:
                        continue
                    col = str(header[ci]).strip() if ci < len(header) else ""
                    extra = {
                        "page_number": p["page_number"],
                        "table_id": tab.get("table_id"),
                        "row_label": row_txt[:80],
                        "column_label": col,
                    }
                    pr = parse_price(val) or parse_price(col + val)
                    if pr and ("行权价格" in row_txt or "行权价格" in col):
                        extra.update({
                            "normalized_numeric_value_if_safe": pr["normalized_numeric_value"],
                            "currency": "CNY", "unit": pr["unit"], "per_share_or_total": "per_share",
                        })
                        field = "option_fair_value" if "公允" in row_txt or "公允" in col else "exercise_price"
                        add(field, val, 0, 0, extra)
                    if "万份" in val or "万 份" in val:
                        q = parse_wan_quantity(val)
                        if q:
                            extra.update({
                                "normalized_numeric_value_if_safe": q["normalized_numeric_value"],
                                "unit": "份", "per_share_or_total": "total",
                            })
                            field = "exercisable_quantity" if "可行权" in (row_txt + col) else "outstanding_option_quantity"
                            add(field, val, 0, 0, extra)

    # Dedup identical candidate_id
    seen = set()
    uniq = []
    for c in cands:
        if c["candidate_id"] in seen:
            continue
        seen.add(c["candidate_id"])
        uniq.append(c)
    return uniq
