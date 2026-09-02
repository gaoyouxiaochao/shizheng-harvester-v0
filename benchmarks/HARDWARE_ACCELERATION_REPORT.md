# Hardware Acceleration Report

Inspection time (UTC): 2026-09-02T16:22:52Z  
Host: Linux KVM sandbox `hds-3cx3e3tt8aj1` (kernel 6.12.8+)  
This is the **Challenger isolation workspace**. It is not the Windows research host.

## Inventory (measured)

| Item | Value | How measured |
| --- | --- | --- |
| CPU model | Intel(R) Xeon(R) Platinum 8481C CPU @ 2.70GHz | `/proc/cpuinfo`, `lscpu` |
| CPU architecture | x86_64, AVX2 + AVX-512 | `lscpu` flags |
| Sockets / cores / threads | 1 socket, 2 cores, 2 threads (1 thread/core) | `lscpu`, `nproc=2` |
| Hypervisor | KVM full virt | `lscpu` |
| RAM total | 4024496 kB ≈ **3.84 GiB** | `/proc/meminfo MemTotal` |
| RAM available at inspect | 3673468 kB ≈ **3.50 GiB** | `MemAvailable` |
| Swap | **0** | `SwapTotal` |
| GPU model(s) | **NONE** | `lspci` GPU class empty; `/dev/nvidia*` absent; `/dev/dri` absent |
| GPU VRAM | **N/A** | no device |
| CUDA | **unavailable** | no `nvidia-smi`, no `nvcc`, no `/usr/local/cuda` |
| cuDNN / TensorRT | **unavailable** | `ldconfig` has no cuda/cudnn/nvinfer |
| DirectML | **N/A** | Windows-only; this host is Linux |
| OpenCL GPU | **unavailable** | no GPU ICD / no DRI |
| Other accelerators | none observed | device nodes + PCI |

Installed document stack at inspect:

| Package | Status |
| --- | --- |
| PyMuPDF (`fitz`) | 1.28.2 |
| pdfplumber | 0.11.10 |
| torch / tensorflow / onnxruntime / paddle / paddleocr | not installed |
| OpenCV, pytesseract, easyocr, ultralytics | not installed |
| Tesseract binary | not installed |

## GPU presence verdict

**No usable GPU exists in this sandbox.**

Therefore:

- GPU latency, VRAM, utilization, and GPU speedup **cannot be measured**.
- No GPU pipeline is selected for any stage.
- This is not a preference against GPU; it is a hardware fact on this host.

If the same code later runs on the Windows research machine with a GPU, re-run this report there. Do not reuse these null GPU numbers as if they were a Windows measurement.

## Stage-by-stage decision

Selection order remains: correctness > auditability > reliability > determinism > maintainability > throughput.

| Stage | Device | Why | GPU comparison |
| --- | --- | --- | --- |
| SHA-256 | CPU | Hashlib is deterministic, already fast, no model | **not measured** — no GPU |
| Native PDF text + word bbox | CPU (PyMuPDF) | Required for exact quote + page + bbox provenance | **not measured** |
| Header/footer, reading order, blocks | CPU | Rule/geometry; GPU would add non-determinism | **not measured** |
| Table extraction | CPU (PyMuPDF `find_tables` + pdfplumber) | Need cell/row/col identity, not a vision guess | **not measured** |
| Chinese date/number/price parse | CPU | Deterministic parsers | N/A |
| Schema / candidate matching | CPU gazetteer + bounded window | Auditability requires exact source text | N/A |
| OCR | **not used by default** | Target filings are born-digital CN announcements; OCR is residual only | no OCR runtime and no GPU |
| Layout neural detector | **not used** | 4 GB RAM / 2 vCPU cannot host a layout model without swapping; no GPU | **not measured** |
| VLM / large semantic model | **optional residual, CPU or remote API, off by default** | Determinism contract forbids silent LLM merge | no local GPU VLM possible |
| Embeddings / retrieval | **not used in v1** | 8-case full-document harvest is smaller than an embedding index | **not measured** |
| Batch document processing | CPU sequential or 2-thread | Only 2 vCPU; GPU batching is unavailable | **not measured** |

## Why GPU is not forced even as a future option on *this* host

Typical GPU-suitable stages (OCR, layout CNN, VLM, embeddings) would require:

1. A GPU + driver + CUDA/DirectML runtime — **absent**
2. Model weights and a framework (torch/onnxruntime-gpu/paddle) — **absent**
3. VRAM headroom — **absent**
4. RAM headroom for CPU fallback of those same models — **~3.8 GiB total, 0 swap**, unsafe for PaddleOCR / layoutparser / a 7B VLM

Installing a GPU stack here would not create a GPU. It would only add operational complexity and non-determinism.

## CPU microbench (synthetic only — not the 8-case harvest)

A 2-page synthetic PDF was generated in memory. It is **not** a governed announcement and is **not** part of `INPUT_MANIFEST`.

| Field | Value |
| --- | --- |
| device_used | cpu |
| cpu_seconds.sha256 | 0.000043 |
| cpu_seconds.native_text | 0.005880 |
| cpu_seconds.table_find | 0.005983 |
| gpu_seconds_if_used | null |
| gpu_model | null |
| peak_vram_mb | null |
| average_gpu_utilization_if_available | null |
| batch_size | 1 |
| pages_processed | 2 |
| documents_processed | 1 |

Raw JSON: `benchmarks/cpu_microbench_synthetic.json`

These numbers only show that PyMuPDF native extract is viable on this CPU. They are **not** `PDF_PROCESSING_SECONDS` for the eight hard cases.

## GPU vs CPU comparison table

| Metric | CPU (measured) | GPU |
| --- | --- | --- |
| Latency | see microbench | **not measured — no device** |
| Quality difference | n/a | n/a |
| VRAM | n/a | n/a |
| GPU utilization | n/a | n/a |
| Memory usage | host ~3.8 GiB total | n/a |
| Batch throughput | 2 vCPU bound | n/a |
| Warm-up cost | none (no model load) | n/a |
| Operational complexity | low (PyMuPDF/pdfplumber already present) | would be high and still blocked |
| Determinism | high if LLM residual stays off | n/a |

**No GPU speedup is reported.**

## Pipeline implication

v1 Challenger extraction stack on this host:

1. **Primary:** PyMuPDF native text + word boxes + dict blocks + `find_tables`
2. **Table cross-check:** pdfplumber
3. **Matching:** deterministic Chinese parsers + full-document gazetteer (no collapse to one event)
4. **OCR:** off unless a page is proven image-only
5. **GPU:** unused
6. **LLM residual:** interface only, default OFF, never silently merged

Re-evaluate GPU **only** after either:

- this sandbox gains a visible NVIDIA/AMD device with working runtime, or
- the same pipeline is executed on the Windows research PC and `nvidia-smi` / DirectML is measured there.

Until then, claiming a GPU-accelerated path would be false.
