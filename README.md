# Karyalay AI (कार्यालय AI)
### Air-Gapped Autonomous Intelligence for Government, Defence & PSU Operations
**HackDay 2026 Submission**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Hackathon: HackDay 2026](https://img.shields.io/badge/Hackathon-HackDay%202026-orange.svg)]()
[![Architecture: 100% Air-Gapped](https://img.shields.io/badge/Network-Zero%20Egress%20Air--Gapped-emerald.svg)]()
[![Inference: Local Open-Weight](https://img.shields.io/badge/Inference-Local%20Ollama%2FvLLM-blueviolet.svg)]()

---

## 📌 Project Overview

**Karyalay AI** is a fully self-hosted, air-gapped agentic AI workbench engineered for high-security environments—including defence manufacturing, oil refineries, nuclear facilities, and government public sector undertakings (PSUs).

In sovereign and classified operations, routine knowledge tasks (e.g., verifying hydrostatic valve test reports, cross-referencing plant Standard Operating Procedures, executing data verification scripts, and preparing signed approval notes) cannot touch cloud AI due to strict confidentiality mandates. Staff are left to either perform tedious manual verifications or risk data leaks.

**Karyalay AI** delivers a multimodal, tool-using, agentic AI assistant that runs **100% locally** on internal workstations or private GPU servers with **zero external telemetry and zero outbound network egress**.

---

## 🏗️ System Architecture

```
                                  ┌────────────────────────┐
                                  │   User Interface (UI)   │
                                  │ (Neumorphic Light/Dark)│
                                  └───────────┬────────────┘
                                              │  HTTP / SSE
                                              ▼
                                  ┌────────────────────────┐
                                  │   FastAPI Web Server   │
                                  └───────────┬────────────┘
                                              │
                     ┌────────────────────────┴────────────────────────┐
                     ▼                                                 ▼
        ┌─────────────────────────┐                       ┌─────────────────────────┐
        │      Model Router       │                       │    Network Watchdog     │
        │ (model_registry.yaml)   │                       │ (pfctl / socket check)  │
        └────────────┬────────────┘                       └────────────┬────────────┘
                     │                                                 │ Live Status
                     ▼                                                 ▼
        ┌─────────────────────────┐                       ┌─────────────────────────┐
        │   Local Model Pool      │                       │   UI Security Badge     │
        │  (Ollama Local Daemon)  │                       │   (0 Outbound Sockets)  │
        ├─────────────────────────┤                       └─────────────────────────┘
        │ • Google Gemma 4 E4B    │
        │ • Qwen2.5-Coder 7B      │
        │ • Qwen2-VL 7B (Fallback)│
        │ • ChromaDB Embeddings   │
        └────────────┬────────────┘
                     │
                     ▼
        ┌───────────────────────────────────────────────────────────┐
        │               Autonomous Agent Loop                       │
        │             (Plan ➔ Act ➔ Observe ➔ Reflect)              │
        └──────┬────────────┬─────────────┬────────────┬────────────┘
               │            │             │            │
               ▼            ▼             ▼            ▼
        ┌──────────┐ ┌────────────┐ ┌───────────┐ ┌─────────────────┐
        │ File I/O │ │ Code Box   │ │ Local RAG │ │ Doc Generator   │
        │ (Scoped) │ │(Docker Net │ │(SOPs/Tmpl/│ │ (.docx / .xlsx) │
        │          │ │   None)    │ │ Equipment)│ │  (Draft/Final)  │
        └──────────┘ └────────────┘ └───────────┘ └────────┬────────┘
                                                           │
                                                           ▼
                                            ┌─────────────────────────────┐
                                            │ Human-in-the-Loop Sign-Off  │
                                            │ (Permission Gate / Review)  │
                                            └──────────────┬──────────────┘
                                                           │
                                                           ▼
                                            ┌─────────────────────────────┐
                                            │ Official Deliverable & Trace│
                                            │   workspace/deliverables/   │
                                            │ (.docx + [name]_trace.md)   │
                                            └─────────────────────────────┘
```

---

## 🔑 Key Features

- **Config-Driven Model Router** — Auto-selects the right open-weight model per task type (code / document reasoning / vision-OCR) via `model_registry.yaml`.
- **Autonomous Agent Loop** — Plans multi-step tasks, calls tools (file read/write, code sandbox, doc search, spreadsheet, doc generation), iterates with plan → act → observe → reflect.
- **Multimodal Ingestion** — Reads scanned PDFs, handwritten notes, photographs, and engineering drawings via local OCR + vision-language model.
- **Real Deliverables** — Outputs actual `.docx`/`.xlsx` files and runnable/verified code, not just chat text.
- **Local Knowledge Base (RAG)** — Grounds answers in the org's own manuals/SOPs/correspondence using ChromaDB local vector store.
- **Sovereignty Proof** — Live network monitor/dashboard showing zero external calls at any point during operation.

---

## 📂 Repository Layout

```
HackDay_2026/
├── README.md                           # Project overview & setup
├── Architecture.md                     # Architectural decisions & component specs
├── PRD.md                              # Product Requirements Document
├── Phases.md                           # Development phases
├── Rules.md                            # Hard engineering & air-gapped constraints
├── requirements.txt                    # Python dependencies
├── .gitignore                          # Git ignore rules
│
└── sovereign-workbench/                # Core Workbench Package
    ├── router/                         # Dynamic model router & configs
    │   ├── classifier.py               # Task classification & model routing
    │   └── model_registry.yaml         # Model → endpoint → params mapping
    ├── knowledge_base/                 # Local ChromaDB vector store & SOP ingest
    │   └── ingest_pipeline.py          # Structural chunking, metadata, supersede
    ├── agent/                          # Autonomous plan-act-reflect loop & tools
    │   ├── planner.py                  # Multi-step agent with contradiction checks
    │   └── tools/
    │       ├── file_io.py              # Scoped file read/write
    │       ├── code_sandbox.py         # Docker --network none sandbox
    │       ├── doc_search.py           # SOP vector retriever with citations
    │       ├── template_search.py      # Approved style templates retriever
    │       ├── equipment_history.py    # Prior deliverables equipment scanner
    │       ├── spreadsheet.py          # Spreadsheet computation
    │       └── doc_generator.py        # DOCX generator with human sign-off
    ├── ingestion/                      # OCR & Vision-Language ingestion
    │   ├── ocr.py                      # PaddleOCR / Tesseract fallback
    │   └── vlm_reader.py              # Vision model for scans/images
    ├── network_monitor/                # Real-time egress watchdog
    │   └── egress_watchdog.py          # pfctl/iptables socket monitoring
    ├── ui/                             # FastAPI server & Neumorphic frontend
    │   ├── app.py                      # SSE backend, uploads, deliverable trace
    │   └── static/
    │       ├── index.html              # Control room UI
    │       ├── style.css               # Neumorphic styling
    │       └── app.js                  # Frontend logic
    └── test_flagship_pipeline.py       # End-to-end integration test
```

---

## ⚙️ Setup & Quickstart

### Prerequisites
1. **Operating System**: macOS (Apple Silicon M-Series) or Linux (Ubuntu 22.04+ with GPU / CPU).
2. **Python**: Version `3.10` or higher.
3. **Ollama**: Local open-weight serving daemon ([ollama.ai](https://ollama.ai/)).
4. **Docker Desktop**: For isolated code sandbox execution.

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/rwitankar-byte/HackDay_2026.git
cd HackDay_2026

# 2. Create and activate a Python virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Pull the required local models via Ollama
ollama pull gemma4:e4b               # Primary multimodal reasoning engine (Google Gemma 4 E4B)
ollama pull qwen2.5-coder:7b         # Code generation & script execution
ollama pull qwen2-vl:7b              # Vision model fallback (optional)

# 5. Start the Ollama server (if not already running)
ollama serve

# 6. Launch the application
cd sovereign-workbench
python -m ui.app
```

### Model Summary

| Task Type | Model | Size | Purpose |
|---|---|---|---|
| Document Reasoning | `gemma4:e4b` | ~4.5 GB | Primary reasoning, SOP matching, drafting, summaries (Google Gemma 4 E4B) |
| Vision / Multimodal | `gemma4:e4b` | ~4.5 GB | Multimodal document inspection, scanned reports, handwriting |
| Code Generation | `qwen2.5-coder:7b` | ~4.7 GB | Script generation, code execution, syntax debugging |
| Vision Fallback | `qwen2-vl:7b` | ~4.7 GB | Secondary vision fallback for complex diagrams |
| Embeddings | ChromaDB default | Built-in | Local vector embeddings for RAG (no separate model pull) |

---

## 🔒 Hard Security & Air-Gap Guarantees

- **100% Offline Inference**: All models execute locally via Ollama endpoints. Zero external API calls.
- **Docker Egress Isolation**: Sandboxed code execution runs with `--network none`.
- **Operating System Watchdog**: Host firewall rules (`pfctl` / `iptables`) monitor active sockets and verify zero outbound connections.
- **Strict Filesystem Scoping**: File tools are locked to designated workspace directories.
- **Zero External UI Assets**: Frontend utilizes local fonts, styles, and scripts with zero CDN dependencies.

---

## 📜 License

Distributed under the **MIT License**. Open-weight models (Qwen series) are governed by their respective licenses.
