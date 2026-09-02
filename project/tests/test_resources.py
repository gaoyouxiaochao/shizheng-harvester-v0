import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

from harvest.resources import BatchGate, ResourceGuard, ResourcePolicy


def test_two_core_host_caps_docs_parallel_at_one():
    p = ResourcePolicy(max_docs_parallel=2, leave_cpu_core_idle=True)
    assert p.effective_docs_parallel(ncpu=2) == 1
    assert p.effective_docs_parallel(ncpu=8) == 2


def test_gpu_absent_jobs_zero():
    p = ResourcePolicy(max_gpu_jobs_parallel=1)
    assert p.effective_gpu_jobs(gpu_present=False) == 0
    assert p.effective_gpu_jobs(gpu_present=True) == 1


def test_batch_gate_promotion():
    g = BatchGate()
    g.allow(1)
    try:
        g.allow(2)
        raise AssertionError("mini batch must wait for smoke")
    except RuntimeError:
        pass
    g.smoke_1_ok = True
    g.allow(2)
    try:
        g.allow(8)
        raise AssertionError("full batch must wait for mini")
    except RuntimeError:
        pass
    g.mini_2_ok = True
    g.allow(8)


def test_forbid_d_drive_walk():
    p = ResourcePolicy(
        recursive_scan_d_drive=False,
        path_allowlist=[r"D:\grok-pdf-处理", "/workspace/grok-pdf-处理"],
    )
    try:
        p.assert_path_allowed(r"D:\StockOptionResearch\data\raw")
        raise AssertionError("must refuse research tree")
    except RuntimeError:
        pass
    p.assert_path_allowed("/workspace/grok-pdf-处理/input/pdf")


def test_guard_refuses_batch_gt_2_without_gate():
    g = ResourceGuard(ResourcePolicy(max_docs_parallel=2, leave_cpu_core_idle=True))
    try:
        g.assert_batch_size_allowed(8)
        raise AssertionError("must refuse 8")
    except RuntimeError:
        pass
    g.assert_batch_size_allowed(1)


def test_unbounded_pools_forbidden():
    p = ResourcePolicy(unbounded_worker_pools=True)
    g = ResourceGuard(p)
    try:
        g.map_bounded([1], lambda x: x)
        raise AssertionError("unbounded must fail")
    except RuntimeError:
        pass


def test_map_bounded_one_item():
    g = ResourceGuard()
    out = g.map_bounded([3], lambda x: x * 2)
    assert out == [6]
