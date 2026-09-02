"""Challenger CLI. Refuses unbounded / unfrozen 8-case batches."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = Path(__file__).resolve().parents[1]
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from harvest.resources import BatchGate, ResourceGuard, ResourcePolicy, sample_cpu_util


def cmd_resource_status(_: argparse.Namespace) -> int:
    guard = ResourceGuard()
    cpu = sample_cpu_util(0.2)
    snap = guard.snapshot(cpu_util=cpu)
    payload = {
        **guard.status_dict(),
        "last_sample": {
            "cpu_util": snap.cpu_util,
            "load1": snap.load1,
            "ram_free_ratio": snap.ram_free_ratio,
            "throttled": snap.throttled,
            "reason": snap.reason,
            "gpu": snap.gpu,
        },
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def cmd_smoke(args: argparse.Namespace) -> int:
    """Single-document smoke. Synthetic by default; never walks D:."""
    from harvest.smoke import run_single_document_smoke

    out = run_single_document_smoke(synthetic=not args.frozen_pdf)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out.get("ok") else 2


def cmd_batch(args: argparse.Namespace) -> int:
    n = args.n
    gate = BatchGate(smoke_1_ok=args.smoke_ok, mini_2_ok=args.mini_ok)
    try:
        gate.allow(n)
    except RuntimeError as exc:
        print(json.dumps({"ok": False, "error": str(exc), "gate": gate.to_dict()}, ensure_ascii=False, indent=2))
        return 3
    frozen = (ROOT / "input" / "manifests" / "INPUT_MANIFEST_STATUS.json")
    status = json.loads(frozen.read_text(encoding="utf-8")) if frozen.exists() else {"INPUT_MANIFEST_STATUS": "UNKNOWN"}
    if status.get("INPUT_MANIFEST_STATUS") != "FROZEN":
        print(json.dumps({
            "ok": False,
            "error": "INPUT_MANIFEST is not FROZEN; refusing harvest batch",
            "INPUT_MANIFEST_STATUS": status.get("INPUT_MANIFEST_STATUS"),
            "requested_n": n,
        }, ensure_ascii=False, indent=2))
        return 4
    print(json.dumps({"ok": False, "error": "harvest runner not promoted yet", "requested_n": n}, indent=2))
    return 5


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="harvest", description="Schema-first PDF evidence harvester (Challenger)")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("resource-status")
    s.set_defaults(func=cmd_resource_status)
    s = sub.add_parser("smoke")
    s.add_argument("--frozen-pdf", action="store_true", help="use a frozen manifest PDF (refused if not frozen)")
    s.set_defaults(func=cmd_smoke)
    s = sub.add_parser("batch")
    s.add_argument("-n", type=int, required=True)
    s.add_argument("--smoke-ok", action="store_true")
    s.add_argument("--mini-ok", action="store_true")
    s.set_defaults(func=cmd_batch)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    t0 = time.perf_counter()
    rc = args.func(args)
    # CLI wall time is not PDF_PROCESSING_SECONDS of the 8-case run.
    _ = t0
    return rc
