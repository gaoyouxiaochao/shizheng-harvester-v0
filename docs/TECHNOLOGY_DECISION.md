# Technology decision

Evaluated for Chinese regulatory PDFs, auditability, determinism, maturity.

| Approach | Decision | Why |
| --- | --- | --- |
| PyMuPDF native text + words/bbox + find_tables | **SELECTED primary** | Mature, exact quotes, page + bbox, born-digital CN announcements extract cleanly |
| pdfplumber tables | **SELECTED secondary** | Cell grids when PyMuPDF tables miss |
| pypdf text-only | Rejected | No bbox / layout |
| MinerU / layout DL | Rejected on this host | Needs GPU/RAM; weaker audit trail |
| PaddleOCR / Tesseract default | Rejected default | Target PDFs are native text; OCR residual only |
| VLM / LLM merge | Rejected default | Non-deterministic; would look like Truth |
| GPU pipelines | Unavailable here | See `benchmarks/HARDWARE_ACCELERATION_REPORT.md` |

Do not optimize solely for these eight examples. Schema is document-complete, then field-complete.
