# Architecture Specification — Karyalay AI
**HackDay 2026 — Milestone 1**

## High-Level Flow
```
User (UI) 
  → Router (classifies task) 
  → Model Pool (vLLM/Ollama, OpenAI-compatible endpoints)
  → Agent Loop (plan → act → observe → reflect)
       → Tools: file_io, code_sandbox, doc_search (RAG), template_search, equipment_history, spreadsheet, doc_generator
       → Ingestion: OCR + Vision-Language model for scans/images
  → Human Sign-Off Gate
  → Deliverable (.docx) + Reasoning Audit Trace (_trace.md) back to user
  
Network Monitor runs alongside everything, watching host & container egress at OS/firewall level.
```

---

## Tech Stack & Hardware Target

### Prototype Target: MacBook M-Series / Linux Workstation (16–24GB+ Unified Memory)
| Layer | Choice | Rationale |
|---|---|---|
| **Model Serving** | **Ollama** (Apple Silicon / CPU / CUDA) | Local inference engine exposing OpenAI-compatible REST endpoints. |
| **Reasoning Model** | **Google Gemma 4** (12B Unified Multimodal / E4B) | Apache 2.0 open weights, frontier reasoning & tool calling, runs locally on ~16GB unified memory. (Fallback: `Qwen2.5-14B`) |
| **Coder Model** | `Qwen2.5-Coder-7B` (Q4/Q5 quantized) / Gemma 4 Code | High-efficiency code generation fitting comfortably in consumer memory. |
| **Vision & Multimodal** | **Gemma 4 12B** (Encoder-free native multimodal) / `Qwen2-VL-7B` | Direct multimodal ingestion of engineering drawings, handwriting, and scanned inspection sheets. |
| **Embeddings** | `nomic-embed-text` / `BGE-M3` | Local, lightweight embeddings with zero external telemetry. |
| **Vector Store** | `ChromaDB` (local embedded mode) | Multi-collection store (`karyalaya_sops`, `karyalaya_templates`) with metadata filtering. |
| **OCR Fallback** | `PaddleOCR` / `Tesseract` | Fast CPU-based text extraction for clean scans. |
| **Agent Orchestration** | Custom Plan-Act-Observe-Reflect Loop | Deterministic tool execution, citation tracking, and contradiction detection. |
| **Code Sandbox** | Docker Desktop (`--network none`) | Isolated, network-disabled execution environment. |
| **Doc Generation** | `python-docx`, `python-pptx`, `openpyxl` | Programmatic deliverable rendering with corporate typography and citation tables. |
| **UI** | FastAPI + Vanilla JS/CSS (Neumorphic) | Tactile interface with SSE live streams and real-time egress monitor. |
| **Network Proof** | macOS `pfctl` / Linux `iptables` | Kernel-level firewall socket counter verifying 0 outbound calls. |

### Enterprise GPU Target (Future Scaling)
Swap Ollama → vLLM, Chroma → Qdrant cluster, and lift model size caps (32B–72B models). Because all model access uses OpenAI-compatible endpoint specifications, the agent and tool logic require zero refactoring.

---

## Planned Codebase Structure (To be built across Milestones)

```
HackDay_2026/
├── README.md                           # Milestone overview & progress tracking
├── Architecture.md                     # Architectural decisions & component specs
├── PRD.md                              # Product Requirements Document
├── Phases.md                           # Hackathon milestone roadmap
├── Rules.md                            # Hard engineering & air-gapped constraints
├── requirements.txt                    # Python dependencies
├── .gitignore                          # Git ignore rules
│
└── sovereign-workbench/                # Core Workbench Package
    ├── router/                         # Milestone 2: Dynamic model router & configs
    │   ├── classifier.py               # Rule-based & embedding task classifier
    │   └── model_registry.yaml         # Config-driven model endpoints & limits
    ├── knowledge_base/                 # Milestone 3: Local Chroma vector store & SOP ingest
    │   ├── vector_store/               # Local persistent Chroma vector store
    │   └── ingest_pipeline.py          # Structural chunking & supersede_document()
    ├── agent/                          # Milestone 4: Autonomous plan-act-reflect loop & tools
    │   ├── planner.py                  # Agent orchestrator with contradiction checks
    │   └── tools/                      # Scoped toolset (file_io, sandbox, doc_search, docx)
    ├── ingestion/                      # Milestone 5: OCR & Vision-Language ingestion
    │   ├── ocr.py                      # Local OCR fallback
    │   └── vlm_reader.py               # Vision-Language Model interpreter
    ├── network_monitor/                # Milestone 7: Real-time pfctl/iptables egress watchdog
    │   └── egress_watchdog.py          # Socket and firewall watchdog daemon
    └── ui/                             # Milestone 8: FastAPI server & Neumorphic frontend
        ├── app.py                      # FastAPI server & SSE streaming
        └── static/                     # Neumorphic HTML/CSS/JS frontend
```

---

## Key Architectural Decisions

1. **Config-Driven Model Router**: Model endpoints, context windows, and parameters are declared in `model_registry.yaml`. Adding or switching models requires zero agent code changes.
2. **Strict Protocol Abstraction**: All local model calls use standard OpenAI-compatible endpoints (`localhost:11434`), ensuring transparent portability between Ollama, vLLM, and llama.cpp.
3. **Hard-Enforced Sandbox Isolation**: The code execution sandbox has network interfaces disabled at the container level (`--network none`).
4. **Local-Only Persistent Vector Store**: Vector embeddings and metadata indices run on disk locally without any hosted cloud API dependency.
5. **Decoupled Egress Watchdog**: The network monitor operates as an independent daemon polling system firewall states (`pfctl` / `iptables`) to guarantee unbiased audit verification.
