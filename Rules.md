# Rules — Karyalaya AI

## Hard constraints (never violate)
- **No internet calls, ever.** No web search tool, no external API, no telemetry, no auto-update checks, no CDN-hosted assets in the UI. If a library wants to phone home, vendor it locally or drop it.
- **No cloud model fallback.** If a local model fails, error out and log it. Never silently route to an external API.
- **Code sandbox always runs network-disabled.** No exceptions, no "just this once for pip install" — vendor dependencies ahead of time or use a pre-built image.
- **All file operations stay inside a scoped workspace directory.** No agent tool may read/write outside the designated project/upload folder.

## Libraries — use
- **Ollama** (Mac-native, no CUDA) for model serving on the M4 prototype — vLLM reserved for the future GPU-server deployment
- python-docx, python-pptx, openpyxl for document generation
- PaddleOCR / Tesseract for OCR fallback
- **Chroma** (local file-based mode) for vector storage on the laptop prototype — Qdrant reserved for server deployment
- Docker Desktop for Mac for sandboxing (`--network none`)

## Hardware constraints (M4 MacBook prototype)
- Stay within 7B–14B quantized models (Q4/Q5 GGUF) — nothing larger fits reliably in laptop memory.
- Don't run the vision model and the reasoning model concurrently on a 16GB machine — route/queue requests, don't parallelize model loads.
- No GPU assumptions in code — everything must run on CPU/MPS only.

## Libraries — avoid
- Any SDK that defaults to a cloud endpoint (openai official SDK is fine ONLY when pointed at a local base_url — never leave it on default)
- LangChain's hosted/cloud-only integrations (use local-only components)
- Any "phone home" analytics library in the UI framework

## Error handling
- Every tool call wraps failures and reports them back to the agent loop as an observation, not a crash. Agent should retry or ask the user, not silently fail.
- OCR/VLM extraction failures on a document должны surface as "low confidence, please verify" rather than hallucinated text.
- Doc generation failures must never produce a corrupted file — validate the output file opens before returning it to the user.

## Agent behavior rules
- Always show the plan and tool-call trace to the user — no black-box single response for multi-step tasks.
- Never fabricate SOP/manual content — if `doc_search` returns nothing relevant, say so explicitly rather than guessing.
- Cap agent loop iterations (e.g. 8 steps) to avoid runaway loops; surface a clear "stuck, need input" state if hit.

## Code style
- Simple, lean, industry-standard formatting. No cleverness for its own sake.
- Config over hardcoding wherever a value might change (model names, ports, paths) — put it in YAML/env, not buried in code.
- Every tool function has a single clear responsibility — no god-functions.
