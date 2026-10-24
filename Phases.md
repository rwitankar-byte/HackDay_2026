# Development Phases — Karyalaya AI

## Phase 1 — Model serving + router skeleton
- Ollama serving local models: `gemma4:e4b` (Google Gemma 4 E4B for document reasoning & multimodal inspection), `qwen2.5-coder:7b` (code generation), and `qwen2-vl:7b` (vision fallback).
- `model_registry.yaml` and `classifier.py` — route a request to the right model based on task type.
- Proof: send a code prompt and a summarization prompt, log which model handled each.

## Phase 2 — Local knowledge base (RAG)
- ChromaDB (local file-based, persistent), with two collections: `karyalaya_sops` and `karyalaya_templates`.
- `doc_search` and `template_search` tools wired into vector retrieval with metadata filtering.
- Structural chunking (tables, section headers, prose) with equipment tag extraction.
- Proof: ask a question answerable only from ingested docs, get a grounded answer with citations.

## Phase 3 — Agent loop + core tools
- Plan → act → observe → reflect loop with multi-turn session history and contradiction detection.
- Tools: `file_io`, `code_sandbox` (Docker Desktop, `--network none`), `spreadsheet`, `equipment_history`.
- Proof: multi-step task (e.g. "read this CSV, compute totals, write a summary file") completes autonomously.

## Phase 4 — Multimodal ingestion
- OCR fallback (PaddleOCR / Tesseract) + `gemma4:e4b` vision-language capabilities for scans/handwriting/photos.
- `vlm_reader.py` with candidate model fallback chain (`gemma4:e4b` → `qwen2-vl:7b` → `llava:7b`).
- Proof: feed a scanned/handwritten sample doc, get accurate extracted text.

## Phase 5 — Deliverable generation
- `doc_generator` — .docx output from agent-produced content with corporate styling.
- Human-in-the-loop sign-off gate before finalising deliverables.
- Proof: agent produces a properly formatted approval note as a real .docx file that opens cleanly.

## Phase 6 — Flagship end-to-end demo task
- Full pipeline: scanned inspection report → `gemma4:e4b` extraction → SOP-grounded drafting via `gemma4:e4b` → .docx approval note.
- `test_flagship_pipeline.py` integration test validates the complete flow.
- Proof: full pipeline runs start to finish on a sample report.

## Phase 7 — Network sovereignty monitor
- Egress lockdown using macOS `pfctl` (deny-all outbound except localhost) plus Docker `--network none` for the sandbox.
- `egress_watchdog.py` with live dashboard showing real-time outbound connection count.
- Proof: dashboard sits at 0 throughout a full demo run, including a deliberate attempt to reach the internet (should fail/be blocked visibly).

## Phase 8 — UI polish + demo script
- Single neumorphic UI: chat + upload + live agent trace + network monitor panel, side by side.
- FastAPI SSE backend streaming agent steps in real time.
- SOP upload, template upload, scan upload, and deliverable download all integrated.

## Phase 9 (future, not required for prototype)
- Move off the M4 MacBook onto an org GPU server: swap Ollama → vLLM, ChromaDB → Qdrant, lift the 7B size cap (32B+ reasoning models become viable).
- Multi-user auth/RBAC, audit logging, model hot-swapping without downtime, scaling to multi-GPU.
- Everything in Phases 1–8 stays free/open-source — only the GPU hardware itself is a real cost.
