"""
FastAPI Backend for Karyalaya AI.

Endpoints:
  GET  /                    — Web UI
  POST /api/chat            — SSE agent conversation (multi-turn, session-aware)
  POST /api/upload          — Task file upload (scans, photos)
  POST /api/upload_sop      — SOP file upload + immediate re-ingestion
  POST /api/ingest_sops     — Re-index all SOPs in workspace/sops/
  POST /api/approve_draft   — Human sign-off: the ONLY path to finalize_official_document
  GET  /api/deliverables    — List official deliverables
  GET  /api/deliverables/{filename} — Download a deliverable
  GET  /api/network_status  — Egress watchdog status

Session state is kept in memory (SESSIONS dict). Each browser tab gets a UUID session.
"""

import os
import sys
import json
import asyncio
import shutil
import time
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from agent.planner import AgentOrchestrator
from network_monitor.egress_watchdog import get_network_status
from knowledge_base.ingest_pipeline import ingest_sops, ingest_templates, supersede_document
from agent.tools.doc_generator import finalize_official_document, draft_payload_to_html
from agent.tools.file_io import WORKSPACE_DIR

app = FastAPI(title="Karyalaya AI", version="1.0.0")

STATIC_DIR           = os.path.join(os.path.dirname(__file__), "static")
UPLOADS_DIR          = os.path.join(WORKSPACE_DIR, "uploads")
DELIVERABLES_DIR     = os.path.join(WORKSPACE_DIR, "deliverables")
SOPS_UPLOAD_DIR      = os.path.join(WORKSPACE_DIR, "sops")
TEMPLATES_UPLOAD_DIR = os.path.join(WORKSPACE_DIR, "templates")

for d in (STATIC_DIR, UPLOADS_DIR, DELIVERABLES_DIR, SOPS_UPLOAD_DIR, TEMPLATES_UPLOAD_DIR):
    os.makedirs(d, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

orchestrator = AgentOrchestrator()

# In-memory session store: session_id → session dict
# Each session holds: history, current_draft_payload, revision_count, trace_log
SESSIONS: Dict[str, Dict[str, Any]] = {}
_NETWORK_STATUS_CACHE: Dict[str, Any] = {"value": None, "checked_at": 0.0}
_NETWORK_STATUS_TTL = 15.0


class DraftApprovalRequest(BaseModel):
    draft_payload: Dict[str, Any]
    session_id: str = ""


class SupersedeRequest(BaseModel):
    filename: str
    collection_name: str = "karyalaya_sops"


@app.get("/", response_class=HTMLResponse)
def read_root():
    """Serves the web UI."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h3>Karyalaya AI backend is running. index.html not found.</h3>"


@app.get("/api/network_status")
def api_network_status():
    """OS-level egress watchdog status."""
    now = time.monotonic()
    if (_NETWORK_STATUS_CACHE["value"] is None or
            now - _NETWORK_STATUS_CACHE["checked_at"] >= _NETWORK_STATUS_TTL):
        _NETWORK_STATUS_CACHE["value"] = get_network_status()
        _NETWORK_STATUS_CACHE["checked_at"] = now
    return _NETWORK_STATUS_CACHE["value"]


@app.post("/api/chat")
async def api_chat(
    user_message: str = Form(...),
    session_id: str = Form(...),
    uploaded_file: str = Form(None),
):
    """
    Main conversational agent endpoint. Streams SSE events for real-time UI rendering.
    Maintains multi-turn conversation history, draft state, and reasoning trace per session_id.
    """
    # Initialise session on first message
    session = SESSIONS.setdefault(session_id, {
        "history": [],
        "current_draft_payload": None,
        "revision_count": 0,
        "trace_log": [],
    })

    # Append current user turn to history
    session["history"].append({"role": "user", "content": user_message})

    t_user = time.strftime("%H:%M:%S")
    session.setdefault("trace_log", []).append(
        f"## User Prompt\n**Time**: {t_user}  \n**Input**: {user_message}" +
        (f"  \n**Attached File**: `{uploaded_file}`" if uploaded_file else "") + "\n"
    )

    async def sse_generator():
        file_path = os.path.join(UPLOADS_DIR, uploaded_file) if uploaded_file else None

        agent_messages = []  # Collect agent output for history
        step_counter = 1

        for step_data in orchestrator.run_task(
            user_prompt=user_message,
            uploaded_file_path=file_path,
            conversation_history=session["history"],
            current_draft_payload=session.get("current_draft_payload"),
        ):
            phase = step_data.get("phase")
            t_step = time.strftime("%H:%M:%S")

            # Record reasoning trace in Markdown (Fix 8)
            if phase == "ROUTER":
                session["trace_log"].append(
                    f"## Step {step_counter} — Model Routing\n"
                    f"**Time**: {t_step}  \n"
                    f"**Model**: `{step_data.get('model', '')}`  \n"
                    f"**Task Classification**: {step_data.get('task_type', '')}\n"
                )
                step_counter += 1
            elif phase == "PLAN":
                session["trace_log"].append(
                    f"## Step {step_counter} — Plan\n"
                    f"**Time**: {t_step}  \n"
                    f"{step_data.get('content', '')}\n"
                )
                step_counter += 1
            elif phase == "ACT":
                tool_name = step_data.get("tool_name", "")
                tool_args = step_data.get("tool_args", {})
                session["trace_log"].append(
                    f"## Step {step_counter} — Action: `{tool_name}`\n"
                    f"**Time**: {t_step}  \n"
                    f"**Tool Call**: `{tool_name}({json.dumps(tool_args)})`\n"
                )
                step_counter += 1
            elif phase == "CODE_OUTPUT":
                out = step_data.get("output", "")
                session["trace_log"].append(
                    f"## Step {step_counter} — Observation\n"
                    f"**Time**: {t_step}  \n"
                    f"```\n{out}\n```\n"
                )
                step_counter += 1

            # Update session draft state and inject HTML preview
            if phase == "DRAFT_READY":
                payload = step_data.get("draft_payload", {})
                is_revision = step_data.get("is_revision", False)

                if is_revision:
                    session["revision_count"] += 1

                session["current_draft_payload"] = payload
                step_data["revision_count"] = session["revision_count"]
                step_data["preview_html"] = draft_payload_to_html(
                    payload, revision=session["revision_count"]
                )
                agent_messages.append(
                    f"[DRAFT {'REVISED' if is_revision else 'CREATED'} — Revision {session['revision_count']}]"
                )
                session["trace_log"].append(
                    f"## Step {step_counter} — Draft Generated\n"
                    f"**Time**: {t_step}  \n"
                    f"**Title**: {payload.get('title', 'Approval Note')}  \n"
                    f"**Equipment**: {payload.get('equipment_id', 'N/A')}  \n"
                    f"**Revision**: {session['revision_count']}\n"
                )
                step_counter += 1

            elif phase == "FINAL_ANSWER":
                ans = step_data.get("content", "")
                agent_messages.append(ans)
                session["trace_log"].append(
                    f"## Final Answer\n"
                    f"**Time**: {t_step}  \n"
                    f"{ans}\n"
                )

            elif phase == "CLARIFYING_QUESTION":
                q = step_data.get("question", "")
                agent_messages.append(f"[CLARIFYING QUESTION]: {q}")
                session["trace_log"].append(
                    f"## Clarifying Question\n"
                    f"**Time**: {t_step}  \n"
                    f"{q}\n"
                )

            yield f"data: {json.dumps(step_data)}\n\n"
            await asyncio.sleep(0.03)

        # Record agent response in history for next turn
        if agent_messages:
            session["history"].append({
                "role": "agent",
                "content": " | ".join(agent_messages),
            })

    return StreamingResponse(sse_generator(), media_type="text/event-stream")


@app.post("/api/upload")
async def api_upload_file(file: UploadFile = File(...)):
    """Uploads a scan or task document to workspace/uploads/."""
    try:
        safe_name = os.path.basename(file.filename or "upload.bin")
        dest = os.path.join(UPLOADS_DIR, safe_name)
        with open(dest, "wb") as buf:
            shutil.copyfileobj(file.file, buf)
        return {
            "status": "success",
            "filename": safe_name,
            "filepath": dest,
            "message": f"Uploaded {file.filename}",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/upload_sop")
async def api_upload_sop(file: UploadFile = File(...)):
    """
    Accepts a SOP file (.pdf, .txt, .md), saves it to workspace/sops/,
    and immediately re-ingests the entire SOP directory into Chroma.
    """
    allowed = {".pdf", ".txt", ".md"}
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Accepted: .pdf, .txt, .md",
        )
    try:
        safe_name = os.path.basename(file.filename or "reference" + ext)
        dest = os.path.join(SOPS_UPLOAD_DIR, safe_name)
        with open(dest, "wb") as buf:
            shutil.copyfileobj(file.file, buf)

        result = ingest_sops()
        return {
            "status": "success",
            "filename": safe_name,
            "chunks_indexed": result.get("total_chunks_ingested", 0),
            "message": (
                f"'{file.filename}' added to knowledge base — "
                f"{result.get('total_chunks_ingested', 0)} total chunks indexed."
            ),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/upload_template")
async def api_upload_template(files: List[UploadFile] = File(...)):
    """
    Accepts style template files (.pdf, .txt, .md, .docx), saves to workspace/templates/,
    and ingests them into the karyalaya_templates Chroma collection with structural summaries.
    """
    allowed = {".pdf", ".txt", ".md", ".docx"}
    uploaded = []
    try:
        for file in files:
            ext = os.path.splitext(file.filename or "")[1].lower()
            if ext not in allowed:
                continue
            safe_name = os.path.basename(file.filename or "template" + ext)
            dest = os.path.join(TEMPLATES_UPLOAD_DIR, safe_name)
            with open(dest, "wb") as buf:
                shutil.copyfileobj(file.file, buf)
            uploaded.append(safe_name)

        if not uploaded:
            raise HTTPException(
                status_code=400,
                detail="No supported files uploaded. Accepted: .pdf, .txt, .md, .docx",
            )

        result = ingest_templates(templates_dir=TEMPLATES_UPLOAD_DIR, router=orchestrator.router)
        return {
            "status": "success",
            "files_uploaded": uploaded,
            "chunks_indexed": result.get("total_chunks_ingested", 0),
            "message": f"Successfully ingested {len(uploaded)} style template(s).",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/supersede_sop")
def api_supersede_sop(req: SupersedeRequest):
    """
    Marks all chunks belonging to a document as superseded.
    """
    try:
        res = supersede_document(req.filename, collection_name=req.collection_name)
        if res.get("status") == "error":
            raise HTTPException(status_code=500, detail=res.get("error", "Failed to supersede"))
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ingest_sops")
def api_ingest_sops():
    """Triggers full re-ingestion of workspace/sops/ into local Chroma DB."""
    return ingest_sops()


@app.post("/api/approve_draft")
def api_approve_draft(req: DraftApprovalRequest):
    """
    Human Sign-Off endpoint.
    The ONLY code path that calls finalize_official_document(human_confirmed=True).
    Generates the reasoning trace file (_trace.md) and clears the session draft.
    """
    try:
        result = finalize_official_document(req.draft_payload, human_confirmed=True)

        # Write reasoning trace log to deliverables if available (Fix 8)
        if result.get("status") == "success" and result.get("filename"):
            base_name = os.path.splitext(result["filename"])[0]
            trace_filename = f"{base_name}_trace.md"
            trace_path = os.path.join(DELIVERABLES_DIR, trace_filename)
            session = SESSIONS.get(req.session_id)
            trace_entries = session.get("trace_log", []) if session else []

            trace_content = (
                f"# Reasoning & Audit Trace — {result['filename']}\n\n"
                f"**Generated**: {time.strftime('%Y-%m-%d %H:%M:%S')}  \n"
                f"**Document**: `{result['filename']}`  \n"
                f"**Title**: {req.draft_payload.get('title', 'N/A')}  \n"
                f"**Equipment ID**: {req.draft_payload.get('equipment_id', 'N/A')}\n\n"
                f"---\n\n"
            )
            if trace_entries:
                trace_content += "\n\n".join(trace_entries)
            else:
                trace_content += "*(Direct human approval without intermediate steps)*\n"

            try:
                with open(trace_path, "w", encoding="utf-8") as tf:
                    tf.write(trace_content)
                result["trace_filename"] = trace_filename
            except Exception as te:
                print(f"[TRACE WARNING] Could not write trace file: {te}")

        # Clear draft state from session so the next task starts clean
        session = SESSIONS.get(req.session_id)
        if session:
            session["current_draft_payload"] = None
            session["revision_count"] = 0

        return result
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/deliverables")
def api_list_deliverables(q: Optional[str] = Query(None)):
    """Lists available official deliverable files, with optional search query filtering."""
    files = []
    if os.path.exists(DELIVERABLES_DIR):
        for fname in sorted(os.listdir(DELIVERABLES_DIR)):
            if fname.startswith(".") or fname.startswith("DRAFT_"):
                continue
            if q and q.strip().lower() not in fname.lower():
                continue
            fp = os.path.join(DELIVERABLES_DIR, fname)
            base_name, ext = os.path.splitext(fname)
            has_trace = False
            if ext.lower() == ".docx":
                trace_candidate = f"{base_name}_trace.md"
                has_trace = os.path.exists(os.path.join(DELIVERABLES_DIR, trace_candidate))

            files.append({
                "name": fname,
                "size": os.path.getsize(fp),
                "created": os.path.getctime(fp),
                "is_trace": fname.endswith("_trace.md"),
                "trace_name": f"{base_name}_trace.md" if has_trace else None,
            })
    return {"deliverables": files}


@app.get("/api/deliverables/{filename}")
def api_download_deliverable(filename: str):
    """Serves a deliverable file for download."""
    safe_name = os.path.basename(filename)
    fp = os.path.join(DELIVERABLES_DIR, safe_name)
    if os.path.exists(fp):
        media_type = "text/markdown" if safe_name.endswith(".md") else "application/octet-stream"
        return FileResponse(path=fp, filename=safe_name, media_type=media_type)
    raise HTTPException(status_code=404, detail=f"File '{filename}' not found.")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
