# Engineering Rules & Air-Gap Mandates — Karyalay AI
**HackDay 2026**

---

## 1. Zero-Trust Air-Gap Constraints (Non-Negotiable)
- **Zero Outbound Sockets**: No external network requests under any circumstance. No telemetry, no auto-update checks, no external API calls, and no CDN-hosted scripts or styles.
- **Zero Cloud Fallbacks**: If a local model fails or runs out of memory, fail gracefully with an explicit error. Never silently fallback to external cloud endpoints.
- **Enforced Docker Sandbox Isolation**: All untrusted or agent-generated scripts must execute in a Docker container started with `--network none`. No exceptions.
- **Strict Filesystem Scoping**: All agent file operations must be jail-scoped to the designated workspace directories. Traversal outside the workspace is strictly forbidden.

---

## 2. Model & Runtime Specifications
- **Local Open-Weight Models**: Ingest and infer exclusively via local instances (served via Ollama / vLLM on `localhost:11434`).
- **Quantization Compliance**: For prototype execution on workstation hardware (Apple Silicon / Linux), models must remain within 7B–14B quantized limits (Q4/Q5 GGUF) to avoid memory starvation.
- **Sequential Resource Management**: Do not parallelize high-memory models (e.g. vision and large reasoning models) concurrently on memory-constrained workstations; route and queue requests deterministically.

---

## 3. Libraries & Dependencies Policy
### Approved:
- **Local Model Serving**: Ollama / vLLM (OpenAI-compatible local endpoints).
- **Document Output**: `python-docx`, `python-pptx`, `openpyxl`.
- **Local Vector Storage**: `chromadb` (embedded persistent mode).
- **Ingestion & OCR**: `Pillow`, `pytesseract`, `PyMuPDF`.
- **Web & Interface**: `fastapi`, `uvicorn`, Vanilla HTML/CSS/JS (embedded locally).

### Prohibited:
- Cloud-bound agent frameworks or libraries with telemetry (e.g., hosted LLM aggregators).
- Remote CDN links (`fonts.googleapis.com`, `cdnjs.cloudflare.com`, etc.)—all web assets must be vendored locally.
- Analytics, telemetry, or remote crash reporting libraries.

---

## 4. Human-in-the-Loop Governance
- The AI agent is authorized to generate **Drafts only**.
- Official documents (`.docx`) must require explicit human confirmation via the control room interface.
- Every deliverable must be accompanied by an immutable audit trace (`[deliverable_name]_trace.md`) capturing all reasoning steps and tool outputs.

---

## 5. Error Handling & Robustness
- Tool executions must encapsulate exceptions and return structured observations rather than unhandled process terminations.
- OCR or visual extraction with confidence below 75% must be explicitly flagged to the user rather than hallucinating technical values.
- Deliverable files must be validated for structural integrity prior to human presentation.
