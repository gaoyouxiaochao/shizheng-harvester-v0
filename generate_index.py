# -*- coding: utf-8 -*-
"""List every review/html/*.html (C01 and X01 alike). No extra packages."""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
HTML = HERE / "review" / "html"
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


def heading(path: Path) -> str:
    text = path.read_text(encoding="utf-8", errors="ignore")[:8000]
    m = re.search(r"<h1>(.*?)</h1>", text, re.S)
    if not m:
        return path.stem
    return re.sub(r"<[^>]+>", "", m.group(1)).strip() or path.stem


def main() -> int:
    HTML.mkdir(parents=True, exist_ok=True)
    pages = sorted(
        p for p in HTML.glob("*.html")
        if p.name.lower() != "index.html"
    )
    cards = []
    for p in pages:
        cid = p.stem
        title = heading(p)
        if cid in META:
            code, name = META[cid]
            title = f"{code} {name}"
        cards.append(
            f'<a class="card" href="{p.name}"><div class="id">{cid}</div>'
            f"<h2>{title}</h2><p>已生成，点击打开</p></a>"
        )
    if not cards:
        cards.append("<p>还没有抽取结果。请先运行 run_harvest.bat</p>")
    html = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
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
<p class="meta">已生成 {len(pages)} 份。X01 起表示文件名未匹配到八案代码，结果仍有效。</p>
<div class="grid">{''.join(cards)}</div>
</body></html>
"""
    dest = HTML / "index.html"
    dest.write_text(html, encoding="utf-8")
    print(str(dest))
    print("pages", len(pages))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
