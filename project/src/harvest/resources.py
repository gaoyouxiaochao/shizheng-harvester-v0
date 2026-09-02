"""Resource safety: bounded workers, RAM/GPU headroom, throttle instead of crash."""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterator, TypeVar

T = TypeVar("T")
U = TypeVar("U")

POLICY_PATH = Path(__file__).resolve().parents[2] / "config" / "resource_safety.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def cpu_count() -> int:
    n = os.cpu_count() or 1
    return max(1, int(n))


def meminfo() -> dict[str, int]:
    out: dict[str, int] = {}
    try:
        with open("/proc/meminfo", encoding="utf-8") as fh:
            for line in fh:
                parts = line.split()
                if len(parts) >= 2 and parts[0].endswith(":"):
                    key = parts[0][:-1]
                    out[key] = int(parts[1]) * 1024 if parts[1].isdigit() else 0
    except OSError:
        pass
    return out


def loadavg() -> tuple[float, float, float]:
    try:
        a, b, c = os.getloadavg()
        return float(a), float(b), float(c)
    except (OSError, AttributeError):
        return (0.0, 0.0, 0.0)


def cpu_times() -> tuple[int, int]:
    """Return (idle, total) jiffies from /proc/stat cpu line."""
    try:
        with open("/proc/stat", encoding="utf-8") as fh:
            parts = fh.readline().split()
        nums = [int(x) for x in parts[1:] if x.isdigit()]
        if not nums:
            return (0, 0)
        idle = nums[3] + (nums[4] if len(nums) > 4 else 0)
        return idle, sum(nums)
    except (OSError, ValueError):
        return (0, 0)


def sample_cpu_util(interval: float = 0.15) -> float | None:
    i1, t1 = cpu_times()
    time.sleep(max(0.05, interval))
    i2, t2 = cpu_times()
    dt = t2 - t1
    if dt <= 0:
        return None
    busy = 1.0 - ((i2 - i1) / dt)
    return max(0.0, min(1.0, busy))


def gpu_snapshot() -> dict[str, Any]:
    """This sandbox has no GPU. Always report absent rather than guessing."""
    return {
        "present": False,
        "model": None,
        "utilization": None,
        "vram_total_mb": None,
        "vram_used_mb": None,
        "vram_free_ratio": None,
        "temperature_c": None,
        "reason": "no nvidia-smi / no /dev/nvidia / no DirectML on this Linux KVM host",
    }


def ram_snapshot() -> dict[str, Any]:
    info = meminfo()
    total = info.get("MemTotal", 0)
    avail = info.get("MemAvailable", info.get("MemFree", 0))
    free_ratio = (avail / total) if total else None
    return {
        "total_bytes": total,
        "available_bytes": avail,
        "free_ratio": free_ratio,
        "used_bytes": (total - avail) if total else None,
    }


@dataclass
class ResourcePolicy:
    max_docs_parallel: int = 2
    max_gpu_jobs_parallel: int = 1
    max_ocr_vlm_pages_parallel: int = 2
    leave_cpu_core_idle: bool = True
    min_ram_free_ratio: float = 0.25
    min_gpu_vram_free_ratio: float = 0.20
    gpu_temp_pause_c: float = 80.0
    max_retries_per_document: int = 1
    retry_backoff_seconds: float = 2.0
    unbounded_worker_pools: bool = False
    overnight_infinite_retries: bool = False
    recursive_scan_d_drive: bool = False
    path_allowlist: list[str] = field(default_factory=list)
    require_single_doc_smoke_before_batch_gt: int = 2
    require_two_doc_mini_batch_before_full: bool = True
    sample_interval_seconds: float = 0.5
    throttle_sleep_seconds: float = 1.0
    max_consecutive_throttles: int = 30
    pause_if_unresponsive: bool = True

    @classmethod
    def load(cls, path: Path | None = None) -> "ResourcePolicy":
        data = _read_json(path or POLICY_PATH)
        defaults = data.get("defaults") or {}
        known = {k: defaults[k] for k in cls.__dataclass_fields__ if k in defaults}
        return cls(**known)

    def effective_docs_parallel(self, ncpu: int | None = None) -> int:
        n = ncpu if ncpu is not None else cpu_count()
        cap = self.max_docs_parallel
        if self.leave_cpu_core_idle:
            cap = min(cap, max(1, n - 1))
        return max(1, cap)

    def effective_gpu_jobs(self, gpu_present: bool) -> int:
        if not gpu_present:
            return 0
        return max(0, self.max_gpu_jobs_parallel)

    def assert_path_allowed(self, path: str | os.PathLike[str]) -> None:
        if self.recursive_scan_d_drive:
            raise RuntimeError("recursive_scan_d_drive is forbidden by RESOURCE_SAFETY_V1")
        raw = str(path)
        # Never walk the whole D: research tree.
        forbidden_prefixes = (
            r"D:\StockOptionResearch",
            "/mnt/d/StockOptionResearch",
            "D:/StockOptionResearch",
        )
        for pref in forbidden_prefixes:
            if raw.replace("\\", "/").startswith(pref.replace("\\", "/")):
                raise RuntimeError(f"refusing path outside Challenger allowlist: {raw}")
        if not self.path_allowlist:
            return
        ok = False
        norm = raw.replace("\\", "/")
        for allowed in self.path_allowlist:
            if norm.startswith(str(allowed).replace("\\", "/")):
                ok = True
                break
        if not ok:
            raise RuntimeError(f"path not on allowlist: {raw}")


@dataclass
class Sample:
    ts: float
    cpu_util: float | None
    load1: float
    ram_free_ratio: float | None
    ram_available_bytes: int | None
    gpu: dict[str, Any]
    throttled: bool
    reason: str | None


class ResourceGuard:
    def __init__(self, policy: ResourcePolicy | None = None):
        self.policy = policy or ResourcePolicy.load()
        self._gpu = gpu_snapshot()
        self.docs_parallel = self.policy.effective_docs_parallel()
        self.gpu_jobs = self.policy.effective_gpu_jobs(bool(self._gpu.get("present")))
        self.ocr_pages_parallel = min(self.policy.max_ocr_vlm_pages_parallel, self.docs_parallel)
        self._doc_sem = threading.BoundedSemaphore(self.docs_parallel)
        self._gpu_sem = threading.BoundedSemaphore(self.gpu_jobs or 1)
        self._ocr_sem = threading.BoundedSemaphore(max(1, self.ocr_pages_parallel))
        self._lock = threading.Lock()
        self.samples: list[Sample] = []
        self.throttle_events = 0
        self.pause_events = 0

    def snapshot(self, cpu_util: float | None = None) -> Sample:
        ram = ram_snapshot()
        load1, _, _ = loadavg()
        gpu = gpu_snapshot()
        reason = None
        throttled = False
        free = ram.get("free_ratio")
        if free is not None and free < self.policy.min_ram_free_ratio:
            throttled = True
            reason = f"ram_free_ratio={free:.3f} < {self.policy.min_ram_free_ratio}"
        if cpu_util is not None and cpu_util > 0.90 and self.docs_parallel > 1:
            throttled = True
            reason = (reason + "; " if reason else "") + f"cpu_util={cpu_util:.2f}"
        ncpu = cpu_count()
        if load1 > ncpu * 0.95:
            throttled = True
            reason = (reason + "; " if reason else "") + f"load1={load1:.2f}"
        if gpu.get("present"):
            vfree = gpu.get("vram_free_ratio")
            if vfree is not None and vfree < self.policy.min_gpu_vram_free_ratio:
                throttled = True
                reason = (reason + "; " if reason else "") + "vram_headroom"
            temp = gpu.get("temperature_c")
            if temp is not None and temp >= self.policy.gpu_temp_pause_c:
                throttled = True
                reason = (reason + "; " if reason else "") + f"gpu_temp_c={temp}"
        sample = Sample(
            ts=time.time(),
            cpu_util=cpu_util,
            load1=load1,
            ram_free_ratio=free,
            ram_available_bytes=ram.get("available_bytes"),
            gpu=gpu,
            throttled=throttled,
            reason=reason,
        )
        with self._lock:
            self.samples.append(sample)
            if throttled:
                self.throttle_events += 1
        return sample

    def wait_until_safe(self) -> Sample:
        waits = 0
        while True:
            sample = self.snapshot()
            if not sample.throttled:
                return sample
            waits += 1
            if waits > self.policy.max_consecutive_throttles:
                self.pause_events += 1
                raise RuntimeError(
                    "resource pressure persisted; pausing batch instead of crashing "
                    f"({sample.reason})"
                )
            time.sleep(self.policy.throttle_sleep_seconds)

    def document_slot(self) -> "_Slot":
        return _Slot(self._doc_sem, self)

    def map_bounded(
        self,
        items: list[T],
        fn: Callable[[T], U],
        label: str = "docs",
        gate: "BatchGate | None" = None,
    ) -> list[U]:
        """Process items with at most docs_parallel workers. No unbounded pool."""
        if self.policy.unbounded_worker_pools:
            raise RuntimeError("unbounded_worker_pools forbidden")
        n = len(items)
        if n == 0:
            return []
        self.assert_batch_size_allowed(n, label=label, gate=gate)
        out: list[U | None] = [None] * n
        errors: list[BaseException] = []

        def worker(idx: int, item: T) -> None:
            try:
                with self.document_slot():
                    self.wait_until_safe()
                    out[idx] = fn(item)
            except BaseException as exc:  # noqa: BLE001 — collect, don't kill siblings
                errors.append(exc)

        threads: list[threading.Thread] = []
        # Launch at most docs_parallel at a time without a pool executor.
        next_i = 0
        while next_i < n or threads:
            threads = [t for t in threads if t.is_alive()]
            while next_i < n and len(threads) < self.docs_parallel:
                t = threading.Thread(target=worker, args=(next_i, items[next_i]), daemon=False)
                t.start()
                threads.append(t)
                next_i += 1
            if threads:
                threads[0].join(timeout=0.2)
        if errors:
            raise RuntimeError(f"{label} failed: {errors[0]}") from errors[0]
        return [x for x in out if x is not None]  # type: ignore[misc]

    def assert_batch_size_allowed(
        self, n: int, label: str = "docs", gate: "BatchGate | None" = None
    ) -> None:
        if n <= 1:
            return
        if gate is None:
            raise RuntimeError(
                f"refusing {label} batch of {n}: policy requires "
                "1-doc smoke → 2-doc mini-batch → only then continue. "
                "Pass a promoted BatchGate."
            )
        gate.allow(n)

    def status_dict(self) -> dict[str, Any]:
        ram = ram_snapshot()
        return {
            "policy_id": "RESOURCE_SAFETY_V1",
            "cpu_count": cpu_count(),
            "effective_docs_parallel": self.docs_parallel,
            "effective_gpu_jobs": self.gpu_jobs,
            "ocr_vlm_pages_parallel": self.ocr_pages_parallel,
            "ram": ram,
            "loadavg": list(loadavg()),
            "gpu": gpu_snapshot(),
            "throttle_events": self.throttle_events,
            "pause_events": self.pause_events,
            "leave_cpu_core_idle": self.policy.leave_cpu_core_idle,
            "min_ram_free_ratio": self.policy.min_ram_free_ratio,
        }


class _Slot:
    def __init__(self, sem: threading.BoundedSemaphore, guard: ResourceGuard):
        self._sem = sem
        self._guard = guard

    def __enter__(self) -> ResourceGuard:
        self._sem.acquire()
        return self._guard

    def __exit__(self, *exc: object) -> None:
        self._sem.release()


@dataclass
class BatchGate:
    """Promotion: 1 smoke → 2 mini → 8-case. Never skip."""

    smoke_1_ok: bool = False
    mini_2_ok: bool = False
    smoke_1_run_id: str | None = None
    mini_2_run_id: str | None = None

    def allow(self, n: int) -> None:
        if n <= 1:
            return
        if n == 2:
            if not self.smoke_1_ok:
                raise RuntimeError("2-document mini-batch blocked: single-document smoke not verified")
            return
        if not self.smoke_1_ok or not self.mini_2_ok:
            raise RuntimeError(
                f"batch of {n} blocked: need smoke_1_ok and mini_2_ok first "
                f"(smoke_1_ok={self.smoke_1_ok}, mini_2_ok={self.mini_2_ok})"
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def iter_resource_log(samples: list[Sample]) -> Iterator[dict[str, Any]]:
    for s in samples:
        yield asdict(s)
