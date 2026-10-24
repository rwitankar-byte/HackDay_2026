# Karyalay AI (कार्यालय AI)
### Air-Gapped Autonomous Intelligence for Government, Defence & PSU Operations
**HackDay 2026 Submission**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Hackathon: HackDay 2026](https://img.shields.io/badge/Hackathon-HackDay%202026-orange.svg)]()
[![Status: Milestone 1 Active](https://img.shields.io/badge/Status-Milestone%201%20Completed-brightgreen.svg)]()
[![Architecture: 100% Air-Gapped](https://img.shields.io/badge/Network-Zero%20Egress%20Air--Gapped-emerald.svg)]()
[![Inference: Local Open-Weight](https://img.shields.io/badge/Inference-Local%20Ollama%2FvLLM-blueviolet.svg)]()

---

## 📌 Project Overview

**Karyalay AI** is a fully self-hosted, air-gapped agentic AI workbench engineered for high-security environments—including defence manufacturing, oil refineries, nuclear facilities, and government public sector undertakings (PSUs).

In sovereign and classified operations, routine knowledge tasks (e.g., verifying hydrostatic valve test reports, cross-referencing plant Standard Operating Procedures, executing data verification scripts, and preparing signed approval notes) cannot touch cloud AI due to strict confidentiality mandates. Staff are left to either perform tedious manual verifications or risk data leaks.

**Karyalay AI** delivers a multimodal, tool-using, agentic AI assistant that runs **100% locally** on internal workstations or private GPU servers with **zero external telemetry and zero outbound network egress**.

---

## 🚀 HackDay 2026 Milestone Roadmap

We are developing Karyalay AI iteratively across dedicated milestones for HackDay 2026:

- [x] **Milestone 1: Project Foundation & Architecture (Current)**
  - [x] Comprehensive System Architecture Blueprint ([`Architecture.md`](Architecture.md))
  - [x] Product Requirements Document & Success Criteria ([`PRD.md`](PRD.md))
  - [x] Phased Milestone Roadmap ([`Phases.md`](Phases.md))
  - [x] Air-Gapped Engineering Rules & Hard Constraints ([`Rules.md`](Rules.md))
  - [x] Initial Dependency Environment Specification ([`requirements.txt`](requirements.txt))
- [ ] **Milestone 2: Local Model Serving & Task Routing Engine**
  - Ollama integration (Google Gemma 4 12B/E4B, Qwen2.5-Coder-7B)
  - Config-driven router (`model_registry.yaml` & task classifier)
- [ ] **Milestone 3: Local Knowledge Base (RAG) & Vector Store**
  - Local ChromaDB vector store
  - Structural chunking & document supersede capabilities for plant SOPs
- [ ] **Milestone 4: Autonomous Plan-Act-Observe-Reflect Agent Core**
  - Multi-turn execution loop with dockerized isolated sandbox (`--network none`)
  - Tooling: file I/O, spreadsheet computation, vector lookup, contradiction detector
- [ ] **Milestone 5: Multimodal Document Ingestion**
  - Local OCR fallback + Vision-Language model for scanned reports & handwritten logs
- [ ] **Milestone 6: Office Deliverable Generation & Human Sign-off**
  - Native `.docx` generation with corporate styling & audit trace export
  - Strict human authorization permission gate
- [ ] **Milestone 7: Real-Time Network Sovereignty Watchdog**
  - Kernel/firewall socket monitoring (`pfctl` / `iptables`) providing live proof of 0 outbound sockets
- [ ] **Milestone 8: Unified Control Room UI & Flagship End-to-End Pipeline**
  - Tactile Neumorphic interface with live SSE stream & end-to-end integration test

---

## 🏗️ Target System Architecture

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
        │ • Google Gemma 4 (12B)  │
        │ • Qwen2.5-Coder-7B      │
        │ • Qwen2-VL-7B (Vision)  │
        │ • Nomic-Embed-Text / BGE│
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

## 📂 Repository Layout (Planned Development Structure)

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
└── sovereign-workbench/                # Core Workbench Package (To be built in upcoming milestones)
    ├── router/                         # Milestone 2: Dynamic model router & configs
    ├── knowledge_base/                 # Milestone 3: Local Chroma vector store & SOP ingest
    ├── agent/                          # Milestone 4: Autonomous plan-act-reflect loop & tools
    ├── ingestion/                      # Milestone 5: OCR & Vision-Language ingestion
    ├── network_monitor/                # Milestone 7: Real-time pfctl/iptables egress watchdog
    └── ui/                             # Milestone 8: FastAPI server & Neumorphic frontend
```

---

## ⚙️ Milestone 1: Environment Setup & Quickstart

### Prerequisites
1. **Operating System**: macOS (Apple Silicon M-Series) or Linux (Ubuntu 22.04+ with GPU / CPU).
2. **Python**: Version `3.10` or higher.
3. **Ollama**: Local open-weight serving daemon ([ollama.ai](https://ollama.ai/)).
4. **Docker Desktop**: For isolated code sandbox execution.

### Setup Instructions

```bash
# 1. Clone the repository
git clone https://github.com/rwitankar-byte/HackDay_2026.git
cd HackDay_2026

# 2. Create and activate a Python virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install initial dependencies
pip install -r requirements.txt

# 4. Pull required local models in Ollama (in preparation for Milestone 2)
ollama pull gemma4:12b           # Primary multimodal reasoning engine (Google Gemma 4)
ollama pull qwen2.5-coder:7b     # Coding & script generation
ollama pull nomic-embed-text     # Local vector embeddings
```

---

## 🔒 Hard Security & Air-Gap Guarantees

- **100% Offline Inference**: All models execute locally via Ollama / vLLM endpoints. Zero external API calls.
- **Docker Egress Isolation**: Sandboxed code execution runs with `--network none`.
- **Operating System Watchdog**: Host firewall rules (`pfctl` / `iptables`) monitor active sockets and verify zero outbound connections.
- **Strict Filesystem Scoping**: File tools are locked to designated workspace directories.
- **Zero External UI Assets**: Frontend utilizes local fonts, styles, and scripts with zero CDN dependencies.

---

## 📜 License

Distributed under the **MIT License**. Open-weight models (Qwen series, Nomic Embed) are governed by their respective licenses.
