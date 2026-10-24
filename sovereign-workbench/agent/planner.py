"""
Agent Loop Orchestrator for Karyalaya AI.

Implements Plan → Act → Observe → Reflect with:
  - Multi-turn conversation history carried across user messages
  - Deterministic required-field validation after scan_ingest (triggers CLARIFYING_QUESTION)
  - LLM-based contradiction detection when the same equipment tag appears in both the
    current document and prior deliverables (Fix 10)
  - Iterative draft revision via revise_draft action
  - SOP-grounded recommendation advisory
  - Source attribution: doc_search results carry citation strings that are collected
    and passed into doc_generator as sop_citations (Fix 4)
  - Template-aware drafting: template_search is called before doc_generator to inject
    structural summaries and style examples into the prompt (Fix 2)
  - Hard cap of MAX_ITERATIONS per turn (conversation across turns is not capped)

ENFORCEMENT: finalize_official_document is excluded from imports and from _execute_tool.
             The agent has no code path to that function.
"""

import os
import sys
import json
import re
from datetime import datetime
from typing import Dict, Any, List, Generator, Optional

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from router.classifier import ModelRouter
from agent.tools.file_io import read_workspace_file, write_workspace_file, list_workspace_files
from agent.tools.code_sandbox import execute_python_code
from agent.tools.doc_search import search_knowledge_base
from agent.tools.template_search import search_templates
from agent.tools.equipment_history import (
    lookup_equipment_history,
    extract_equipment_tags_from_text,
)
from agent.tools.doc_generator import generate_approval_note
from agent.tools.spreadsheet import create_excel_report
from ingestion.vlm_reader import ingest_document_scan

# finalize_official_document is deliberately NOT imported here.

MAX_ITERATIONS = 8

# ---------------------------------------------------------------------------
# Required-field definitions per document type.
# ---------------------------------------------------------------------------
REQUIRED_FIELDS: Dict[str, Dict[str, List[str]]] = {
    "approval_note": {
        "title":           ["title", "subject", "re:", "regarding", "approval note", "inspection note"],
        "ref_number":      ["ref", "reference no", "ref no", "document no", "file no", "no.", "#"],
        "plant_unit":      ["unit", "plant", "facility", "station", "section", "site", "area"],
        "inspection_date": ["date", "inspected on", "inspection date", "dated", "on:"],
        "findings":        ["finding", "observation", "noted", "issue", "defect", "compliance", "check"],
    }
}

CONFIDENCE_THRESHOLD = 0.75

TOOL_STATUS: Dict[str, str] = {
    "scan_ingest":      "Reading and extracting text from uploaded document...",
    "doc_search":       "Searching SOP knowledge base for relevant clauses...",
    "template_search":  "Retrieving style templates from past approved documents...",
    "equipment_history":"Looking up prior inspection history for equipment tag...",
    "file_read":        "Reading workspace file...",
    "file_write":       "Saving file to workspace...",
    "file_list":        "Listing workspace files...",
    "code_sandbox":     "Running Python code in isolated Docker sandbox...",
    "doc_generator":    "Drafting the document...",
    "spreadsheet":      "Generating Excel report...",
    "revise_draft":     "Revising draft based on your feedback...",
}

FIELD_FRIENDLY: Dict[str, str] = {
    "title":           "document title or subject",
    "ref_number":      "reference or file number",
    "plant_unit":      "plant or facility unit name",
    "inspection_date": "inspection date",
    "findings":        "inspection findings or observations",
}


def check_required_fields(
    extracted_text: str,
    confidence: float,
    doc_type: str = "approval_note",
) -> List[str]:
    """
    Checks extracted text against the required field list for the given document type.

    Returns a list of issue tokens:
      - "__low_confidence__"  if confidence < CONFIDENCE_THRESHOLD
      - field name strings    for each required field whose indicator keywords
                              are absent from the extracted text

    This is deterministic — the LLM is not involved in the trigger decision.
    """
    issues: List[str] = []

    if confidence < CONFIDENCE_THRESHOLD:
        issues.append("__low_confidence__")

    text_lower = extracted_text.lower()
    for field, keywords in REQUIRED_FIELDS.get(doc_type, {}).items():
        if not any(kw in text_lower for kw in keywords):
            issues.append(field)

    return issues


def build_clarifying_question(
    issues: List[str],
    confidence: float,
    contradiction_notes: Optional[Dict[str, str]] = None,
) -> str:
    """
    Constructs a specific clarifying question from the detected issue list.

    Each issue type produces a distinct, typed explanation so the human understands
    the nature of the gap — not just that one exists:
      - __low_confidence__: OCR quality problem
      - __contradiction___{tag}: LLM-detected value discrepancy between current doc and history
      - field name (absent): field completely missing from document
    """
    parts: List[str] = []
    contradiction_notes = contradiction_notes or {}

    if "__low_confidence__" in issues:
        pct = int(confidence * 100)
        parts.append(
            f"OCR quality is low ({pct}%) — extracted values may be misread scans; "
            "please verify critical readings against the physical document"
        )

    for issue in issues:
        if issue == "__low_confidence__":
            continue
        if issue.startswith("__contradiction__"):
            tag  = issue.replace("__contradiction__", "").lstrip("_")
            note = contradiction_notes.get(tag, "values appear inconsistent")
            parts.append(
                f"The current document and a prior inspection of '{tag}' appear inconsistent: "
                f"{note}. Please confirm which reading is correct"
            )
        else:
            field_name = FIELD_FRIENDLY.get(issue, issue)
            parts.append(f"'{field_name}' could not be located in the document at all")

    if not parts:
        return (
            "Some required information could not be extracted from the document. "
            "Could you provide more details?"
        )

    issues_text = "; ".join(parts)
    return (
        f"Before I proceed, I need to flag some gaps in the uploaded document: {issues_text}. "
        "Could you confirm or provide the missing information so I can draft an accurate report?"
    )


class AgentOrchestrator:
    def __init__(self):
        self.router = ModelRouter()

    def _execute_tool(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dispatches a tool call. finalize_official_document is intentionally absent.
        Adding it here would bypass the human-confirmation enforcement gate.
        """
        try:
            if tool_name == "doc_search":
                # Always default to active-only retrieval unless caller explicitly overrides
                where = args.get("where", {"status": "active"})
                return search_knowledge_base(
                    query=args.get("query", ""),
                    top_k=args.get("top_k", 3),
                    where=where,
                )
            elif tool_name == "template_search":
                return search_templates(
                    query=args.get("query", "approval note format"),
                    top_k=args.get("top_k", 2),
                    summaries_only=args.get("summaries_only", False),
                )
            elif tool_name == "equipment_history":
                return lookup_equipment_history(tag=args.get("tag", ""))
            elif tool_name == "file_read":
                return read_workspace_file(file_path=args.get("file_path", ""))
            elif tool_name == "file_write":
                return write_workspace_file(
                    file_path=args.get("file_path", ""),
                    content=args.get("content", ""),
                )
            elif tool_name == "file_list":
                return list_workspace_files(subfolder=args.get("subfolder", ""))
            elif tool_name == "code_sandbox":
                return execute_python_code(code_string=args.get("code", ""))
            elif tool_name == "doc_generator":
                return generate_approval_note(
                    title=args.get("title", "Inspection Approval Note"),
                    ref_number=args.get("ref_number", "REF-2026-001"),
                    plant_unit=args.get("plant_unit", "Refinery Unit"),
                    inspection_date=args.get("inspection_date", "2026-09-23"),
                    findings=args.get("findings", ["Physical inspection complete"]),
                    sop_reference=args.get("sop_reference", "Per SOP guidelines"),
                    recommendation=args.get("recommendation", "Recommended for approval"),
                    filename=args.get("filename", "Approval_Note.docx"),
                    sop_citations=args.get("sop_citations", []),
                )
            elif tool_name == "spreadsheet":
                return create_excel_report(
                    sheet_name=args.get("sheet_name", "Sheet1"),
                    headers=args.get("headers", ["ID", "Item", "Status"]),
                    rows=args.get("rows", []),
                    filename=args.get("filename", "Report.xlsx"),
                )
            elif tool_name == "scan_ingest":
                return ingest_document_scan(file_path=args.get("file_path", ""))
            else:
                return {"status": "error", "error": f"Unknown tool: {tool_name}"}
        except Exception as e:
            return {"status": "error", "error": f"Tool execution failure: {str(e)}"}

    def _run_contradiction_check(
        self,
        model_name: str,
        current_excerpt: str,
        tag: str,
        history_matches: List[Dict[str, Any]],
    ) -> Optional[str]:
        """
        Asks the existing reasoning model whether the current document's statement
        about an equipment tag is consistent with prior inspection records.

        Returns the discrepancy description string if inconsistent, or None if consistent.
        Uses the same model_name already selected for this turn — no new model needed.
        """
        if not history_matches:
            return None

        # Collect up to 3 historical excerpts for the comparison
        historical_excerpts = []
        for match in history_matches[:3]:
            fname = match.get("filename", "unknown")
            for excerpt in match.get("excerpts", [])[:2]:
                historical_excerpts.append(f"[{fname}]: {excerpt}")

        if not historical_excerpts:
            return None

        prompt = (
            f"Equipment tag: {tag}\n\n"
            f"Current document states:\n\"{current_excerpt}\"\n\n"
            f"Prior inspection records state:\n"
            + "\n".join(historical_excerpts)
            + "\n\nAre these consistent? If not, describe the specific discrepancy in one sentence."
            " Respond with a JSON object only: {\"consistent\": true/false, \"discrepancy\": \"...\"}"
        )
        system = (
            "You compare inspection readings across documents. "
            "Respond only with valid JSON: {\"consistent\": bool, \"discrepancy\": string}."
        )
        try:
            raw = self.router.generate(
                model_name=model_name,
                prompt=prompt,
                system_prompt=system,
                temperature=0.0,
            )
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if m:
                result = json.loads(m.group(0))
                if not result.get("consistent", True):
                    return result.get("discrepancy", "values appear inconsistent")
        except Exception:
            pass
        return None

    def _call_revision_llm(
        self,
        model_name: str,
        current_payload: Dict[str, Any],
        feedback: str,
    ) -> Dict[str, Any]:
        """
        Asks the LLM to update specific draft fields based on human feedback.
        Merges the response over the existing payload so unmentioned fields are preserved.
        Falls back to the original payload on any parse failure.
        """
        prompt = (
            f"Current draft (JSON):\n{json.dumps(current_payload, indent=2)}\n\n"
            f"Human reviewer feedback: \"{feedback}\"\n\n"
            "Return ONLY a JSON object with updated values for the fields the feedback requires changing. "
            "Keys must be a subset of: title, ref_number, plant_unit, inspection_date, "
            "findings (list of strings), sop_reference, recommendation, target_filename, sop_citations. "
            "Do not change fields not mentioned in the feedback. Respond with valid JSON only."
        )
        system = (
            "You update official document draft fields based on human reviewer feedback. "
            "Return only valid JSON. Preserve all unchanged fields."
        )
        try:
            raw = self.router.generate(
                model_name=model_name,
                prompt=prompt,
                system_prompt=system,
                temperature=0.05,
            )
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            if m:
                updated = json.loads(m.group(0))
                merged  = {**current_payload, **updated}
                if isinstance(merged.get("findings"), str):
                    merged["findings"] = [merged["findings"]]
                return merged
        except Exception:
            pass
        return current_payload

    def run_task(
        self,
        user_prompt: str,
        uploaded_file_path: Optional[str] = None,
        conversation_history: Optional[List[Dict]] = None,
        current_draft_payload: Optional[Dict] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Runs one agent turn (up to MAX_ITERATIONS steps).

        Yields structured event dicts consumed by the SSE stream in app.py:
          ROUTER, PLAN, STATUS, ACT, OBSERVE, CODE_OUTPUT,
          DRAFT_READY, CLARIFYING_QUESTION, FINAL_ANSWER, STUCK_STATE, ERROR
        """
        history = list(conversation_history or [])
        task_type, model_cfg, route_log = self.router.classify_request(
            user_prompt, has_image=bool(uploaded_file_path)
        )
        model_name = model_cfg["name"]

        yield {
            "phase":      "ROUTER",
            "content":    route_log,
            "task_type":  task_type,
            "model_used": model_name,
        }

        # Build conversation context for the LLM
        context_lines: List[str] = []
        for msg in history[:-1]:
            role = msg.get("role", "user").upper()
            context_lines.append(f"[{role}]: {msg.get('content', '')}")
        if current_draft_payload:
            context_lines.append(
                f"\n[ACTIVE DRAFT — PENDING REVISION OR APPROVAL]:\n"
                f"{json.dumps(current_draft_payload, indent=2)}"
            )
        if uploaded_file_path:
            context_lines.append(f"[UPLOADED FILE]: {uploaded_file_path}")

        system_prompt = (
            "You are Karyalaya AI — an air-gapped government intelligence assistant serving "
            "government, defence, and PSU operations. You help officers with document drafting, "
            "compliance checks, data calculations, and operational recommendations.\n\n"
            "ADVISORY RULE: When you identify a finding that may implicate an SOP clause, "
            "use doc_search to retrieve relevant SOP context, then provide a grounded advisory: "
            "'Based on [SOP name/clause], this finding may require [specific action or escalation to role].' "
            "Ground recommendations in retrieved SOP text, not general assumptions.\n\n"
            "RETRIEVAL RULE: Always include \"where\": {\"status\": \"active\"} in all doc_search "
            "calls. This prevents retrieval of superseded documents. When searching for drafting "
            "templates, also include \"doc_type\": \"template\" in the filter.\n\n"
            "TEMPLATE RULE: When drafting any document, call template_search first. "
            "Inject retrieved structural_summary chunks into your planning context to match "
            "section order and tone. Use retrieved style_chunks as formatting examples.\n\n"
            "CITATION RULE: Collect citation strings from all doc_search results and pass them "
            "as the sop_citations list argument when calling doc_generator. Each citation must "
            "include: source (filename), section (from the §section field), excerpt (key clause text).\n\n"
            "HARD BOUNDARY: You are an advisor and drafter — never a decision-maker or approver. "
            "You can draft, recommend, calculate, and flag issues. You must NEVER finalize, "
            "approve, or auto-submit any document. Every output requires explicit human sign-off. "
            "Never use 'finalize' as an action. Only 'doc_generator' creates documents.\n\n"
            "AVAILABLE TOOLS:\n"
            "1.  scan_ingest(file_path) — Extract text/data from a scanned document or image.\n"
            "2.  doc_search(query, top_k, where) — Search local SOP knowledge base. "
            "Always include where={\"status\":\"active\"}.\n"
            "3.  template_search(query, top_k, summaries_only) — Retrieve past approved documents "
            "as style/structure templates. Call before doc_generator.\n"
            "4.  equipment_history(tag) — Search finalized deliverables for prior inspection "
            "findings on a specific equipment tag.\n"
            "5.  file_read(file_path) — Read a file from workspace.\n"
            "6.  file_write(file_path, content) — Write a text file to workspace.\n"
            "7.  file_list(subfolder) — List workspace files.\n"
            "8.  code_sandbox(code) — Execute Python in an isolated Docker sandbox (--network none).\n"
            "9.  doc_generator(title, ref_number, plant_unit, inspection_date, findings, "
            "sop_reference, recommendation, filename, sop_citations) — Generate AI-drafted .docx "
            "for human review. sop_citations is a list of {source, section, excerpt} dicts.\n"
            "10. spreadsheet(sheet_name, headers, rows, filename) — Generate Excel report.\n"
            "11. revise_draft(feedback) — Revise the active draft using human feedback. "
            "Only use when an active draft exists.\n"
            "12. clarify(question) — Ask the human a clarifying question. Use ONLY when a required "
            "field is missing OR extraction confidence is below 0.75.\n\n"
            "RESPONSE FORMAT — valid JSON only:\n"
            '{"plan": "...", "action": "tool_name or final_answer", '
            '"action_input": {...}, "final_answer": "...", "reflection": "..."}'
        )

        loop_history = list(context_lines)
        loop_history.append(f"[CURRENT USER MESSAGE]: {user_prompt}")

        # Tracks doc_search citations accumulated across steps for sop_citations injection
        accumulated_citations: List[Dict[str, str]] = []

        step = 1
        while step <= MAX_ITERATIONS:
            prompt = (
                "\n".join(loop_history)
                + f"\n\nIteration {step}/{MAX_ITERATIONS}. "
                "Respond with your PLAN, ACTION, ACTION_INPUT, REFLECTION in JSON."
            )

            try:
                raw = self.router.generate(
                    model_name=model_name,
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=0.1,
                )
            except Exception as e:
                yield {"phase": "ERROR", "step": step, "content": f"Model error: {e}"}
                break

            # Parse JSON from model response
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            action_data: Optional[Dict] = None
            if m:
                try:
                    action_data = json.loads(m.group(0))
                except Exception:
                    pass
            if not action_data:
                action_data = {
                    "plan":         "Respond directly",
                    "action":       "final_answer",
                    "action_input": {},
                    "final_answer": raw,
                    "reflection":   "Direct response.",
                }

            plan         = action_data.get("plan", "Executing step")
            action       = action_data.get("action", "final_answer")
            action_input = action_data.get("action_input", {})
            reflection   = action_data.get("reflection", "Step complete.")
            final_answer = action_data.get("final_answer", "")

            yield {
                "phase":      "PLAN",
                "step":       step,
                "plan":       plan,
                "action":     action,
                "reflection": reflection,
            }

            # ── Handle special actions ────────────────────────────────────

            if action in ("final_answer", "") or not action:
                yield {
                    "phase":   "FINAL_ANSWER",
                    "step":    step,
                    "content": final_answer or raw,
                }
                break

            if action == "clarify":
                question = action_input.get("question", str(action_input))
                yield {"phase": "CLARIFYING_QUESTION", "step": step, "question": question}
                break

            if action == "revise_draft":
                feedback = action_input.get("feedback", str(action_input))
                yield {"phase": "STATUS", "step": step, "content": TOOL_STATUS["revise_draft"]}

                if not current_draft_payload:
                    yield {
                        "phase":   "ERROR",
                        "step":    step,
                        "content": "No active draft found to revise.",
                    }
                    break

                updated = self._call_revision_llm(model_name, current_draft_payload, feedback)
                gen = generate_approval_note(
                    title=updated.get("title", "Inspection Approval Note"),
                    ref_number=updated.get("ref_number", "REF-2026-001"),
                    plant_unit=updated.get("plant_unit", "Refinery Unit"),
                    inspection_date=updated.get("inspection_date", "2026-09-23"),
                    findings=updated.get("findings", []),
                    sop_reference=updated.get("sop_reference", "Per SOP guidelines"),
                    recommendation=updated.get("recommendation", "Recommended for approval"),
                    filename=updated.get("target_filename", "Approval_Note.docx"),
                    sop_citations=updated.get("sop_citations", accumulated_citations),
                )
                if gen.get("status") == "draft_created":
                    current_draft_payload = gen["draft_payload"]
                    yield {
                        "phase":        "DRAFT_READY",
                        "step":         step,
                        "draft_payload": current_draft_payload,
                        "draft_file":   gen["draft_file"],
                        "is_revision":  True,
                    }
                else:
                    yield {
                        "phase":   "ERROR",
                        "step":    step,
                        "content": f"Revision failed: {gen.get('error', 'unknown error')}",
                    }
                break

            # ── Standard tool execution ───────────────────────────────────

            yield {
                "phase":   "STATUS",
                "step":    step,
                "content": TOOL_STATUS.get(action, f"Executing {action}..."),
            }
            yield {"phase": "ACT", "step": step, "tool": action, "arguments": action_input}

            observation = self._execute_tool(action, action_input)

            # ── Post-scan_ingest pipeline ──────────────────────────────────
            if action == "scan_ingest":
                extracted  = observation.get("extracted_text", "")
                confidence = float(observation.get("confidence", 1.0))

                # ── Auto equipment history lookup ──────────────────────────
                tags             = extract_equipment_tags_from_text(extracted)
                contradiction_notes: Dict[str, str] = {}

                for tag in tags[:5]:  # cap at 5 tags to avoid blowing the context window
                    yield {
                        "phase":   "STATUS",
                        "step":    step,
                        "content": f"Looking up prior inspection history for {tag}...",
                    }
                    history_result = lookup_equipment_history(tag)
                    if history_result.get("match_count", 0) > 0:
                        # Find the paragraph(s) in current doc mentioning this tag
                        current_excerpts = [
                            line.strip() for line in extracted.split("\n")
                            if re.search(r'\b' + re.escape(tag) + r'\b', line)
                        ]
                        current_excerpt = " ".join(current_excerpts[:2])

                        discrepancy = self._run_contradiction_check(
                            model_name, current_excerpt, tag,
                            history_result.get("matches", []),
                        )
                        if discrepancy:
                            contradiction_notes[tag] = discrepancy

                        # Inject history into loop context regardless
                        history_lines = []
                        for match in history_result.get("matches", [])[:3]:
                            for excerpt in match.get("excerpts", [])[:2]:
                                history_lines.append(
                                    f"  [{match['filename']}]: {excerpt}"
                                )
                        if history_lines:
                            loop_history.append(
                                f"\n[EQUIPMENT HISTORY — {tag}]:\n" + "\n".join(history_lines)
                            )

                # ── Required-field check + contradiction issues ────────────
                issues = check_required_fields(extracted, confidence)
                for tag, _ in contradiction_notes.items():
                    issues.append(f"__contradiction__{tag}")

                if issues:
                    observation["field_issues"] = issues
                    question = build_clarifying_question(
                        issues, confidence, contradiction_notes
                    )
                    yield {"phase": "OBSERVE", "step": step, "tool": action, "observation": observation}
                    yield {"phase": "CLARIFYING_QUESTION", "step": step, "question": question}
                    break

            # ── Accumulate doc_search citations ────────────────────────────
            if action == "doc_search" and observation.get("status") == "success":
                for result in observation.get("results", []):
                    citation = result.get("citation", "")
                    if citation:
                        accumulated_citations.append({
                            "source":  result.get("source", ""),
                            "section": result.get("section", ""),
                            "excerpt": result.get("content", "")[:200],
                        })

            # ── Inject accumulated citations when doc_generator is called ──
            if action == "doc_generator":
                if accumulated_citations and not action_input.get("sop_citations"):
                    action_input["sop_citations"] = accumulated_citations
                    observation = self._execute_tool("doc_generator", action_input)

            # ── Code sandbox output ────────────────────────────────────────
            if action == "code_sandbox":
                yield {
                    "phase":        "CODE_OUTPUT",
                    "step":         step,
                    "code":         action_input.get("code", ""),
                    "stdout":       observation.get("stdout", ""),
                    "stderr":       observation.get("stderr", ""),
                    "exit_code":    observation.get("exit_code", 0),
                    "sandbox_type": observation.get("sandbox_type", ""),
                }

            # ── Draft ready ────────────────────────────────────────────────
            if action == "doc_generator" and observation.get("status") == "draft_created":
                current_draft_payload = observation.get("draft_payload")
                yield {
                    "phase":         "DRAFT_READY",
                    "step":          step,
                    "draft_payload": current_draft_payload,
                    "draft_file":    observation.get("draft_file", ""),
                    "is_revision":   False,
                }

            yield {"phase": "OBSERVE", "step": step, "tool": action, "observation": observation}

            loop_history.append(
                f"\nStep {step}: {action}({json.dumps(action_input)}) → "
                f"{json.dumps(observation)}"
            )
            step += 1

        if step > MAX_ITERATIONS:
            yield {
                "phase":   "STUCK_STATE",
                "step":    step,
                "content": (
                    f"Agent reached the {MAX_ITERATIONS}-step limit. "
                    "Please provide more specific instructions or break the task into smaller steps."
                ),
            }


if __name__ == "__main__":
    agent = AgentOrchestrator()
    for event in agent.run_task("Search SOP knowledge base and summarise the inspection approval guidelines."):
        print(json.dumps(event, indent=2))
