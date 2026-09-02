# Resource Safety Policy V1

Encoded in `project/config/resource_safety.json` and enforced by `harvest.resources.ResourceGuard`.

This process must not freeze or crash the workstation. Throttle or pause under pressure.

## Hard limits

| Control | Default | This sandbox |
| --- | ---: | ---: |
| Documents in parallel | 2 | **1** (2 vCPU, leave one core idle) |
| GPU jobs in parallel | 1 | **0** (no GPU) |
| OCR / VLM pages in parallel | 2 | unused (OCR/VLM off) |
| CPU cores used | not all | 1 worker |
| RAM kept free | ≥ 25% | ~0.96 GiB of 3.84 GiB |
| GPU VRAM kept free | ≥ 20% | n/a |
| Retries per document | 1 | 1 |
| Overnight infinite retries | forbidden | forbidden |
| Unbounded worker pools | forbidden | `ThreadPoolExecutor` not used |
| Recursive walk of `D:\` | forbidden | path allowlist only |

Allowlist:

- `D:\grok-pdf-处理`
- `/workspace/grok-pdf-处理`

Forbidden:

- `D:\StockOptionResearch` and any recursive batch over the whole D: drive.

## Batch promotion (mandatory)

Before any batch **> 2 PDFs**:

1. Single-document smoke
2. Verify stability (RAM free ratio, no throttle storm, process still responsive)
3. 2-document mini-batch
4. Only then the 8-case batch

`BatchGate` refuses to skip a step. `ResourceGuard.assert_batch_size_allowed(n>2)` always raises until a caller goes through `BatchGate`.

The 8-case harvest additionally requires `INPUT_MANIFEST_STATUS=FROZEN`. That is currently **NOT_FROZEN**.

## Under pressure

If RAM free ratio < 25%, load1 ≈ all cores, GPU temp ≥ 80 °C, or VRAM headroom < 20%:

- **THROTTLE** (sleep `throttle_sleep_seconds`)
- after 30 consecutive throttles: **PAUSE** the batch with an error, do not spin forever
- do not crash, do not grow the pool

## Telemetry per run

Record when available:

- CPU utilization
- RAM usage / free ratio
- GPU utilization / VRAM / temperature
- processing time (`cpu_seconds`; `gpu_seconds_if_used` is null here)

Temperature is typically **unavailable** on this KVM host.

## Commands

```text
python -m harvest resource-status
python -m harvest smoke
python -m harvest batch -n 8          # refused until smoke + mini + frozen manifest
```
