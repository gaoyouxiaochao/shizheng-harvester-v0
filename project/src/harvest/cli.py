"""Single entry: python -m harvest"""

from __future__ import annotations

import os
import subprocess
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = Path(__file__).resolve().parents[1]
REQ = ROOT / "project" / "requirements.txt"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def ensure_deps() -> None:
    missing = []
    for mod in ("pymupdf", "pdfplumber"):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if not missing:
        return
    print("installing", missing)
    rc = subprocess.call([sys.executable, "-m", "pip", "install", "-r", str(REQ)])
    if rc != 0:
        raise SystemExit("pip install failed")


def open_index() -> None:
    path = ROOT / "review" / "html" / "index.html"
    if not path.exists():
        print("no review/html/index.html")
        return
    if os.name == "nt":
        os.startfile(str(path))  # type: ignore[attr-defined]
    else:
        webbrowser.open(path.as_uri())


def main() -> int:
    ensure_deps()
    from harvest.pipeline import run_controlled_batch
    from harvest.reports import rebuild

    try:
        summary = run_controlled_batch()
        print("harvested", summary.get("documents_processed"), "docs",
              summary.get("candidate_total"), "candidates")
    except SystemExit as exc:
        if exc.code not in (0, 2, None):
            raise
        print("no new PDFs or batch skipped; rebuilding review from existing output")
        rebuild()
    open_index()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
