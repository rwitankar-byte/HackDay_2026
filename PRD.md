# Product Requirements Document (PRD) — Karyalay AI
### Air-Gapped Sovereign Intelligence for Government, Defence & PSU Operations
**HackDay 2026 — Milestone 1**

---

## 1. Problem Statement
Critical infrastructure entities—such as refineries, defence manufacturing plants, nuclear power stations, and public sector undertakings (PSUs)—handle highly sensitive operational data daily (hydrostatic valve inspection logs, SOP compliance notes, piping stress calculations, and classified internal code).

Due to strict national security and confidentiality mandates, this data cannot be uploaded to commercial cloud AI services. Consequently, plant officers and technical staff face a stark dilemma:
1. Conduct all data cross-referencing, verification, and note-drafting manually—consuming hundreds of staff-hours.
2. Unsafely paste sensitive excerpts into public cloud chatbots, risking severe data compromise.

**No turnkey, air-gapped, multimodal agentic alternative exists for on-premise deployment today.**

---

## 2. Target Users & Operating Scenarios
- **Plant Inspection Engineers**: Reviewing messy scanned reports, handwritten inspection sheets, and equipment test logs.
- **Compliance & Approval Officers**: Cross-referencing operational findings with official Standard Operating Procedures (SOPs) and drafting formal approval notes.
- **Internal Tooling Developers**: Writing and verifying plant automation scripts in safe, sandboxed environments.
- **Administrative Personnel**: Processing scanned internal correspondence without internet connectivity.

---

## 3. Core Value Proposition
A self-hosted, air-gapped AI workbench that delivers a state-of-the-art agentic experience (autonomous multi-step reasoning, multimodal ingestion, tool use, and deliverable creation) with **100% of data remaining on internal hardware and zero external network egress**.

---

## 4. Key Functional Requirements

1. **Dynamic Task Routing**: Automatically route tasks (code synthesis vs. document reasoning vs. visual inspection) to the optimal quantized local model via a declarative configuration (`model_registry.yaml`).
2. **Autonomous Agent Loop**: Plan multi-step workflows, execute safe local tools (sandboxed Python execution, tabular data calculation, vector search), observe tool feedback, and self-reflect to refine findings.
3. **Multimodal Document Understanding**: Ingest scanned PDFs, photographs, and handwritten logs via local OCR fallback and Vision-Language Models (`Qwen2-VL-7B`).
4. **Structured Local RAG**: Index plant SOPs into local vector storage (ChromaDB) with metadata-aware retrieval, section grounding, and document superseding.
5. **Direct Deliverable Generation**: Produce structured, professionally formatted `.docx` approval notes with explicit corporate typography, tables, and reference citations.
6. **Human-in-the-Loop Governance**: Mandatory human review and sign-off before official document generation, paired with an append-only audit trail (`_trace.md`).
7. **Egress Sovereignty Proof**: Real-time OS firewall watchdog proving zero outbound network connections during operation.

---

## 5. Explicit Non-Goals (Scope Boundaries)
- **No Cloud Fallbacks**: Hard constraint. Zero external API calls.
- **No Multi-User RBAC in Initial Prototype**: Designed as an air-gapped single-workstation/control-room terminal; multi-user directory sync slated for enterprise scaling.
- **No Hosted Cloud Embeddings**: Embeddings must compute locally via quantized open-source models.

---

## 6. Success & Evaluation Criteria
- **Model Routing**: Clean demonstration of prompt routing between coding and reasoning models with transparent logs.
- **End-to-End Pipeline**: Scanned inspection report ➔ automated findings extraction ➔ SOP verification ➔ draft generation ➔ human review ➔ finalized `.docx` deliverable.
- **Code Sandbox**: Python script execution in network-disabled Docker (`--network none`) with automatic error recovery.
- **Network Sovereignty**: Unbroken zero-egress status verified by the live host watchdog throughout testing.
