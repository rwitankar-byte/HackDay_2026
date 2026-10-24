# Architecture — Karyalaya AI

## High-level flow
```
User (UI) 
  → Router (classifies task) 
  → Model Pool (vLLM/Ollama, OpenAI-compatible endpoints)
  → Agent Loop (plan → act → observe → reflect)
       → Tools: file_io, code_sandbox, doc_search (RAG), template_search, equipment_history, spreadsheet, doc_generator
       → Ingestion: OCR + Vision-Language model for scans/images
  → Human Sign-Off Gate
  → Deliverable (.docx) + Reasoning Audit Trace (_trace.md) back to user
  
Network Monitor runs alongside everything, watching the container's egress at OS/firewall level.
```

## Tech stack

### Prototype target: MacBook M4 (16–24GB+ unified memory, no GPU/CUDA)
| Layer | Choice | Why |
|---|---|---|
| Model serving | **Ollama** (Mac-native, Apple Silicon optimized) or MLX | No CUDA needed, runs quantized GGUF models directly on M4 |
| Coder model | Qwen2.5-Coder-7B (Q4/Q5 quantized) | Fits comfortably in 16GB, strong code gen |
| Reasoning model | Qwen2.5-14B-Instruct (Q4 quantized) | Best reasoning quality that fits laptop memory; drop to 7B if RAM-constrained |
| Vision model | Qwen2-VL-7B (quantized) | Reads handwriting, diagrams, scanned docs; heaviest component, needs 16GB+ free |
| Embeddings | BGE-M3 or nomic-embed-text (CPU/MPS) | Local, no external calls, light enough for laptop |
| Vector store | Chroma (local mode, file-based) | Multi-collection (`karyalaya_sops`, `karyalaya_templates`) with metadata filtering |
| OCR fallback | PaddleOCR / Tesseract (CPU) | Cheap first-pass text extraction |
| Agent orchestration | Custom plan-execute-reflect loop | Full control, multi-turn session history, citation accumulation, contradiction detection |
| Code sandbox | Docker Desktop for Mac, network disabled | Isolated, safe execution |
| Doc generation | python-docx, python-pptx, openpyxl | Real Office file output with explicit typography, tables, and SOP citations |
| UI | FastAPI + Vanilla JS/CSS (Neumorphic) | Chat + uploads (SOP/Template/Scan) + live trace + network monitor + deliverables filter |
| Network proof | macOS `pfctl` egress-deny + live connection counter dashboard | Visual, real-time proof of zero external calls |

### Production target (Phase 9, real GPU server)
Swap Ollama → vLLM, Chroma → Qdrant, and lift model size caps (32B+ reasoning model becomes viable). No agent/tool code changes needed — this is exactly why the OpenAI-compatible endpoint abstraction matters.

**Cost note:** everything above is free and open-source (models + tools). No licensing cost on either the laptop prototype or the GPU server version.

## Folder structure
```
sovereign-workbench/
├── router/
│   ├── classifier.py
│   └── model_registry.yaml
├── models/                # served endpoints, not code — config only
├── agent/
│   ├── planner.py         # Autonomous multi-step agent with multi-turn history & contradiction checks
│   └── tools/
│       ├── file_io.py
│       ├── code_sandbox.py
│       ├── doc_search.py       # SOP vector retriever with status filtering and citations
│       ├── template_search.py  # Approved style templates retriever
│       ├── equipment_history.py# Prior deliverables equipment scanner via python-docx
│       ├── spreadsheet.py
│       └── doc_generator.py    # Explicitly styled DOCX generator with human sign-off gate
├── ingestion/
│   ├── ocr.py
│   └── vlm_reader.py
├── knowledge_base/
│   ├── vector_store/
│   └── ingest_pipeline.py     # Structural chunking, metadata tagging, supersede_document()
├── network_monitor/
│   └── egress_watchdog.py
├── ui/
│   ├── app.py                 # FastAPI SSE backend, template uploads, deliverable trace exporter
│   └── static/
│       ├── index.html         # Control room UI with style templates & deliverable search
│       ├── style.css
│       └── app.js
└── docker-compose.yml         # everything on an isolated network, no internet route
```

## Note on Mac deployment specifics
- Ollama runs as a local background service (`ollama serve`) exposing an OpenAI-compatible endpoint on `localhost:11434` — the router treats it exactly like it would treat vLLM.
- Docker Desktop for Mac still supports `--network none` for the code sandbox — egress lockdown works the same way.
- The network monitor uses `pfctl` (macOS's built-in firewall) instead of iptables/nftables, same concept: deny-all egress, live connection count in the UI.

## Key architectural decisions
1. **Router is config-driven, not hardcoded.** `model_registry.yaml` maps task-type → model endpoint → context window/params. Adding a new model = new YAML entry + pulling weights. No code change.
2. **All model access goes through OpenAI-compatible local endpoints.** Keeps the agent code model-agnostic; swapping vLLM for Ollama doesn't touch agent logic.
3. **Code sandbox has its network interface disabled at the Docker level**, not just "the code doesn't call anything." Enforced, not trusted.
4. **RAG is retrieval-only, local.** No hosted embedding APIs. Vector store persists on disk inside the org's server.
5. **Network monitor is a separate process watching the host/container egress**, independent of the app itself — so it can't be silently bypassed by a bug in the agent code.

## Data flow for the flagship demo task (scanned report → approval note)
1. User uploads scanned PDF/image via UI.
2. `ingestion/vlm_reader.py` (or OCR fallback for clean text) extracts findings.
3. Router classifies this as a "document reasoning" task → sends extracted text to reasoning model.
4. Agent plans: extract key findings → check against relevant SOP via `doc_search` (RAG) → draft note → call `doc_generator` to produce .docx.
5. Agent reflects: does the draft cover all required approval-note sections? If not, loop back.
6. Final .docx returned to user; full tool-call trace shown in UI.
7. Network monitor panel shows 0 external connections throughout.
