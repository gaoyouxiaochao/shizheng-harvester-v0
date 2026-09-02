# -*- coding: utf-8 -*-
"""Install pymupdf + pdfplumber for the current python.exe."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REQ = Path(__file__).resolve().parent / "project" / "requirements.txt"


def missing() -> list[str]:
    out = []
    for mod in ("pymupdf", "pdfplumber"):
        try:
            __import__(mod)
        except ImportError:
            out.append(mod)
    return out


def main() -> int:
    need = missing()
    if not need:
        print("deps ok:", sys.executable)
        return 0
    print("missing", need)
    print("install with", sys.executable, "-m pip")
    cmd = [sys.executable, "-m", "pip", "install", "-r", str(REQ)]
    rc = subprocess.call(cmd)
    if rc != 0:
        print("pip failed")
        return rc
    still = missing()
    if still:
        print("still missing", still)
        return 1
    print("deps ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
