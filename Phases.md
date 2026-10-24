# Phases — Karyalaya AI

## Phase 1 — Model serving + router skeleton
- Install Ollama on the M4 MacBook, pull 2 quantized models (Qwen2.5-Coder-7B, Qwen2.5-14B-Instruct).
- Build `model_registry.yaml` and `classifier.py` — route a request to the right model.
- Prove: send a code prompt and a summarization prompt, log which model handled each.

## Phase 2 — Local knowledge base (RAG)
- Set up Chroma (local file-based), ingest a handful of sample SOPs/manuals.
- Build `doc_search` tool, wire into a basic single-shot Q&A (no agent loop yet).
- Prove: ask a question answerable only from the ingested docs, get a grounded answer.

## Phase 3 — Agent loop + core tools
- Build plan → act → observe → reflect loop.
- Wire up `file_io`, `code_sandbox` (Docker Desktop, `--network none`), `spreadsheet`.
- Prove: multi-step task (e.g. "read this CSV, compute totals, write a summary file") completes without human intervention mid-task.

## Phase 4 — Multimodal ingestion
- Add OCR fallback + vision-language model reader for scans/handwriting/photos.
- Prove: feed a scanned/handwritten sample doc, get accurate extracted text.

## Phase 5 — Deliverable generation
- Build `doc_generator` — docx/pptx/xlsx output from agent-produced content.
- Prove: agent produces a properly formatted approval note as a real .docx file that opens cleanly.

## Phase 6 — Flagship end-to-end demo task
- Wire Phases 2–5 together: scanned inspection report → findings extraction → SOP-grounded drafting → .docx approval note.
- Prove: full pipeline runs start to finish on a sample report.

## Phase 7 — Network sovereignty monitor
- Lock down egress using macOS `pfctl` (deny-all outbound except localhost) plus Docker `--network none` for the sandbox.
- Build live dashboard/log showing real-time outbound connection count.
- Prove: dashboard sits at 0 throughout a full demo run, including a deliberate attempt to reach the internet (should fail/be blocked visibly).

## Phase 8 — UI polish + demo script
- Single UI: chat + upload + live agent trace + network monitor panel, side by side.
- Write and rehearse the demo script: model routing demo → agentic doc task → coding task → multimodal task → network proof, in that order.

## Phase 9 (post-demo, not required for prototype)
- Move off the M4 MacBook onto an org GPU server: swap Ollama → vLLM, Chroma → Qdrant, lift the 7B–14B size cap (32B+ reasoning models become viable).
- Multi-user auth/RBAC, audit logging, model hot-swapping without downtime, scaling to multi-GPU.
- Everything in Phases 1–8 stays free/open-source at this stage too — only the GPU hardware itself is a real cost.
