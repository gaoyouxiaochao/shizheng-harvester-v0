import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from harvest.chinese import grant_batch_hint, parse_cn_int, parse_date, parse_price, parse_wan_quantity


def test_spaced_cn_date():
    assert parse_date("2026 年8 月28 日") == "2026-08-28"
    assert parse_date("2026年8月28日") == "2026-08-28"


def test_price_not_fair_value_unit():
    p = parse_price("本次股票期权行权价格：68.90 元/份")
    assert p and p["normalized_numeric_value"] == 68.9
    assert p["per_share_or_total"] == "per_share"


def test_wan_quantity():
    q = parse_wan_quantity("拟行权数量：16.60 万份")
    assert q and q["normalized_numeric_value"] == 166000.0


def test_ordinal_period():
    assert parse_cn_int("三") == 3
    assert parse_cn_int("十") == 10
    assert parse_cn_int("十二") == 12


def test_batch_hints_not_collapsed():
    assert grant_batch_hint("预留授予第三个行权期") == "RESERVED"
    assert grant_batch_hint("首次授予部分") == "FIRST"
    assert grant_batch_hint("首次授予及预留授予") == "FIRST_AND_RESERVED"
