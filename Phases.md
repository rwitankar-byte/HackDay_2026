# HackDay 2026 Milestone Delivery Plan — Karyalay AI

## Milestone 1: Project Kickoff & Foundation Architecture (Completed / Active)
- Define problem statement, operational scenarios, and air-gapped constraints.
- Formulate high-level system architecture and component design (`Architecture.md`).
- Document Product Requirements Document (`PRD.md`) and evaluation criteria.
- Establish hard engineering rules and sovereignty mandates (`Rules.md`).
- Specify initial environment dependencies (`requirements.txt`) and setup instructions.

---

## Milestone 2: Model Serving & Routing Infrastructure (Upcoming)
- Setup local inference server (Ollama) with quantized open-weight models (**Google Gemma 4 12B/E4B**, `Qwen2.5-Coder-7B`, `Qwen2-VL-7B`).
- Implement declarative model registry (`model_registry.yaml`).
- Develop intelligent task classifier (`router/classifier.py`) for automated intent-to-model routing.
- **Verification**: Route coding prompts and document reasoning prompts, confirming correct model allocation via logs.

---

## Milestone 3: Local Knowledge Base (RAG) & Vector Storage (Upcoming)
- Configure local file-based vector storage via ChromaDB.
- Build document ingestion pipeline with structural chunking and metadata enrichment (`knowledge_base/ingest_pipeline.py`).
- Implement SOP supersede functionality to deprecate obsolete standards.
- Build `doc_search` retrieval tool with citation tracking.
- **Verification**: Ingest plant SOPs and demonstrate grounded document Q&A without cloud connectivity.

---

## Milestone 4: Autonomous Plan-Act-Observe-Reflect Agent Loop (Upcoming)
- Implement autonomous multi-step reasoning orchestrator (`agent/planner.py`).
- Develop core execution tools:
  - `file_io`: Scoped workspace reader/writer.
  - `code_sandbox`: Docker execution sandbox with `--network none`.
  - `spreadsheet`: Tabular calculation and CSV/Excel aggregation.
- Build reflection and contradiction detection against historical equipment records.
- **Verification**: Complete multi-step data processing task without human intervention mid-flight.

---

## Milestone 5: Multimodal Document Ingestion (Upcoming)
- Integrate local OCR fallback (Tesseract/PaddleOCR) for quick text extraction.
- Implement Vision-Language Model interpreter (`ingestion/vlm_reader.py`) for handwritten logs and diagram interpretation.
- Surface low-confidence visual warnings for unreadable scans.
- **Verification**: Ingest low-quality scanned inspection sheets and extract structured technical parameters.

---

## Milestone 6: Office Deliverable Generation & Sign-Off Governance (Upcoming)
- Build `doc_generator` using `python-docx` with corporate typography, metadata tables, and citation appendices.
- Enforce cryptographic permission gates: AI agent is restricted to generating review drafts.
- Implement human-in-the-loop authorization workflow that finalizes official documents and writes execution audit traces (`_trace.md`).
- **Verification**: Generate valid, beautifully formatted `.docx` approval notes with accompanying trace logs.

---

## Milestone 7: Real-Time Network Sovereignty Watchdog (Upcoming)
- Implement background host monitor (`network_monitor/egress_watchdog.py`) inspecting socket activity via `pfctl` (macOS) or `iptables` (Linux).
- Provide real-time socket statistics and egress alert triggers.
- **Verification**: Maintain zero outbound connections across a complete execution pipeline.

---

## Milestone 8: Control Room UI & Flagship End-to-End Pipeline (Upcoming)
- Develop responsive, tactile Neumorphic control room interface (FastAPI + Vanilla CSS/JS).
- Feature live Server-Sent Events (SSE) streaming for agent reasoning steps, model routing, and socket monitor.
- Implement inline document previews, deliverable search filters, and template upload modules.
- **Verification**: Execute end-to-end flagship workflow (Scan ➔ VLM ➔ RAG ➔ Sandbox ➔ Draft ➔ Sign-off ➔ Deliverable).

---

## Milestone 9: Enterprise GPU Cluster Scaling (Post-Hackathon)
- Transition model serving from Ollama to high-throughput vLLM cluster.
- Migrate ChromaDB to distributed Qdrant vector cluster.
- Unlock 32B–72B reasoning models (`Qwen2.5-72B`, `DeepSeek-R1-Distill`).
- Integrate air-gapped LDAP/Active Directory RBAC and Hardware Security Module (HSM) digital signatures.
