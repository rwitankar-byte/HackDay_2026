"""
Document Generator Tool for Karyalaya AI.

Responsibilities:
  - generate_approval_note()  — creates an AI draft (PENDING REVIEW). Agent-callable.
  - finalize_official_document() — writes the official .docx. Requires human_confirmed=True.
    Raises PermissionError otherwise. NOT callable by the agent loop (excluded from tool registry).
  - draft_payload_to_html()  — renders draft fields as HTML for inline UI preview.
  - create_approval_note_docx() — internal shared docx builder.

Heading formatting note (diagnosed 2026-09-23):
  The previous implementation used doc.add_heading(text, level=1) which applies Word's
  built-in 'Heading 1' style. The diagnostic showed size=None, bold=None on all heading
  runs — meaning all formatting was inherited from the base template (Normal.dotm), not
  set in code. This causes inconsistent rendering across machines and Word versions, and
  can produce hyperlink-styled headings on some installations.
  Fix: all section headings now use Normal-style paragraphs with fully explicit run
  formatting (font name, size, bold, colour), bypassing Word's built-in heading styles.
  The sign-off block previously used \\n inside a single run (which python-docx silently
  ignores); it now uses separate add_paragraph() calls.
"""

import os
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from typing import Dict, Any, List, Optional

WORKSPACE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "workspace")
)
DELIVERABLES_DIR = os.path.join(WORKSPACE_DIR, "deliverables")

_HEADING_COLOR_OFFICIAL = RGBColor(0, 70, 127)
_HEADING_COLOR_DRAFT    = RGBColor(140, 80, 0)
_LABEL_BG               = "F2F2F2"  # light grey for table label column
_BODY_FONT              = "Calibri"
_BODY_SIZE              = Pt(11)
_HEADING_SIZE           = Pt(12)


def _set_cell_bg(cell, hex_color: str) -> None:
    """Shades a table cell background with the given hex colour (e.g. 'F2F2F2')."""
    tc   = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd  = OxmlElement("w:shd")
    shd.set(qn("w:val"),   "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"),  hex_color)
    tcPr.append(shd)


def _set_table_border(table) -> None:
    """Adds a thin outer border to a table."""
    tbl   = table._tbl
    tblPr = tbl.find(qn("w:tblPr"))
    if tblPr is None:
        tblPr = OxmlElement("w:tblPr")
        tbl.insert(0, tblPr)
    borders = OxmlElement("w:tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:val"),   "single")
        el.set(qn("w:sz"),    "4")
        el.set(qn("w:space"), "0")
        el.set(qn("w:color"), "CCCCCC")
        borders.append(el)
    tblPr.append(borders)


def _add_section_heading(doc: Document, text: str, color: RGBColor) -> None:
    """
    Adds a section heading as a Normal paragraph with fully explicit run formatting.

    Deliberately avoids Word's built-in Heading styles. Diagnostic on 2026-09-23
    confirmed: the previous Heading 1 paragraphs had size=None and bold=None on
    their runs — all formatting was inherited from the machine's base template.
    This replacement sets every property explicitly so output is consistent across
    machines and Word versions, regardless of what Normal.dotm contains.
    """
    p = doc.add_paragraph()
    p.style = doc.styles["Normal"]
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after  = Pt(4)
    # Thin top rule via paragraph border
    pPr  = p._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    top  = OxmlElement("w:top")
    top.set(qn("w:val"),   "single")
    top.set(qn("w:sz"),    "4")
    top.set(qn("w:space"), "1")
    top.set(qn("w:color"), "DDDDDD")
    pBdr.append(top)
    pPr.append(pBdr)
    run = p.add_run(text)
    run.bold           = True
    run.font.name      = _BODY_FONT
    run.font.size      = _HEADING_SIZE
    run.font.color.rgb = color


def create_approval_note_docx(
    title: str,
    ref_number: str,
    plant_unit: str,
    inspection_date: str,
    findings: List[str],
    sop_reference: str,
    recommendation: str,
    target_path: str,
    is_official: bool = False,
    sop_citations: Optional[List[Dict[str, str]]] = None,
) -> str:
    """Builds and saves an approval note .docx at target_path. Returns the saved path."""
    doc = Document()

    # ── Document-level font defaults ───────────────────────────────────────────
    # Explicitly override the Normal style font so every paragraph picks up Calibri 11pt
    # regardless of what Normal.dotm on the running machine specifies.
    normal           = doc.styles["Normal"]
    normal.font.name = _BODY_FONT
    normal.font.size = _BODY_SIZE

    for section in doc.sections:
        section.top_margin    = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin   = Inches(1.1)
        section.right_margin  = Inches(1.1)

    heading_color = _HEADING_COLOR_OFFICIAL if is_official else _HEADING_COLOR_DRAFT

    # ── Organization header ────────────────────────────────────────────────────
    org_p           = doc.add_paragraph()
    org_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    org_r           = org_p.add_run("GOVERNMENT OF INDIA — SOVEREIGN OPERATIONS UNIT")
    org_r.bold           = True
    org_r.font.name      = _BODY_FONT
    org_r.font.size      = Pt(10)
    org_r.font.color.rgb = RGBColor(80, 80, 80)

    sub_p           = doc.add_paragraph()
    sub_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub_r           = sub_p.add_run("KARYALAYA AI ASSISTED DOCUMENT — FOR OFFICIAL USE ONLY")
    sub_r.font.name      = _BODY_FONT
    sub_r.font.size      = Pt(8)
    sub_r.font.color.rgb = RGBColor(160, 160, 160)
    sub_r.italic         = True

    # Thin coloured horizontal rule
    rule_p   = doc.add_paragraph()
    rule_pPr = rule_p._p.get_or_add_pPr()
    rule_bdr = OxmlElement("w:pBdr")
    bot      = OxmlElement("w:bottom")
    bot.set(qn("w:val"),   "single")
    bot.set(qn("w:sz"),    "6")
    bot.set(qn("w:space"), "1")
    bot.set(qn("w:color"), "003366" if is_official else "8C5000")
    rule_bdr.append(bot)
    rule_pPr.append(rule_bdr)

    # ── Document status banner ─────────────────────────────────────────────────
    banner_text = (
        "OFFICIAL INSPECTION APPROVAL NOTE" if is_official
        else "DRAFT INSPECTION APPROVAL NOTE — PENDING HUMAN SIGN-OFF"
    )
    banner_p           = doc.add_paragraph()
    banner_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    banner_p.paragraph_format.space_before = Pt(10)
    banner_r           = banner_p.add_run(banner_text)
    banner_r.bold           = True
    banner_r.font.name      = _BODY_FONT
    banner_r.font.size      = Pt(14)
    banner_r.font.color.rgb = heading_color

    doc.add_paragraph().paragraph_format.space_after = Pt(4)

    # ── Metadata table ─────────────────────────────────────────────────────────
    # Explicit column widths (2.2" / 3.8") prevent ragged layout regardless of value length.
    table           = doc.add_table(rows=4, cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit   = False
    _set_table_border(table)

    col_widths = [Inches(2.2), Inches(3.8)]
    for row in table.rows:
        for i, cell in enumerate(row.cells):
            cell.width = col_widths[i]

    for idx, (label, val) in enumerate([
        ("Document Title:",       title),
        ("Reference No.:",        ref_number),
        ("Plant / Facility Unit:", plant_unit),
        ("Inspection Date:",       inspection_date),
    ]):
        row        = table.rows[idx]
        label_cell = row.cells[0]
        value_cell = row.cells[1]
        _set_cell_bg(label_cell, _LABEL_BG)

        label_r           = label_cell.paragraphs[0].add_run(label)
        label_r.bold      = True
        label_r.font.name = _BODY_FONT
        label_r.font.size = _BODY_SIZE

        value_r           = value_cell.paragraphs[0].add_run(val)
        value_r.font.name = _BODY_FONT
        value_r.font.size = _BODY_SIZE

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # ── Section 1: Findings ────────────────────────────────────────────────────
    _add_section_heading(doc, "1. Key Inspection Findings", heading_color)
    for finding in findings:
        item   = doc.add_paragraph(style="List Bullet")
        item_r = item.add_run(finding)
        item_r.font.name = _BODY_FONT
        item_r.font.size = _BODY_SIZE

    # ── Section 2: SOP Grounding ───────────────────────────────────────────────
    _add_section_heading(doc, "2. SOP Grounding & Reference", heading_color)
    sop_p = doc.add_paragraph()
    sop_r = sop_p.add_run(sop_reference)
    sop_r.font.name = _BODY_FONT
    sop_r.font.size = _BODY_SIZE

    # ── Section 3: Recommendation ──────────────────────────────────────────────
    _add_section_heading(doc, "3. Recommendation & Next Steps", heading_color)
    rec_p = doc.add_paragraph()
    rec_r = rec_p.add_run(recommendation)
    rec_r.font.name = _BODY_FONT
    rec_r.font.size = _BODY_SIZE

    # ── Section 4: SOP Citations table (rendered when citations are provided) ──
    if sop_citations:
        _add_section_heading(doc, "4. Source References", heading_color)
        cit_table           = doc.add_table(rows=1 + len(sop_citations), cols=3)
        cit_table.alignment = WD_TABLE_ALIGNMENT.LEFT
        cit_table.autofit   = False
        _set_table_border(cit_table)

        cit_widths = [Inches(2.0), Inches(1.5), Inches(2.5)]
        for row in cit_table.rows:
            for i, cell in enumerate(row.cells):
                cell.width = cit_widths[i]

        hdr_row = cit_table.rows[0]
        for col_idx, hdr_text in enumerate(["SOP Document", "Section", "Relevant Clause"]):
            _set_cell_bg(hdr_row.cells[col_idx], _LABEL_BG)
            r           = hdr_row.cells[col_idx].paragraphs[0].add_run(hdr_text)
            r.bold      = True
            r.font.name = _BODY_FONT
            r.font.size = Pt(9)

        for row_idx, cite in enumerate(sop_citations):
            data_row = cit_table.rows[row_idx + 1]
            for col_idx, key in enumerate(["source", "section", "excerpt"]):
                r           = data_row.cells[col_idx].paragraphs[0].add_run(
                    str(cite.get(key, ""))[:200]
                )
                r.font.name = _BODY_FONT
                r.font.size = Pt(9)

        doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # ── Sign-off block ─────────────────────────────────────────────────────────
    # Each line is a separate paragraph — python-docx runs silently ignore \n characters.
    doc.add_paragraph().paragraph_format.space_before = Pt(20)

    if is_official:
        sign_lines = [
            ("Approved & Signed by:", True),
            ("_______________________", False),
            ("Chief Inspection Officer / Unit Head", False),
        ]
    else:
        sign_lines = [
            ("PENDING HUMAN REVIEW & SIGN-OFF", True),
            ("_______________________", False),
            ("Authorized Approver Signature Required", False),
        ]

    for text, bold in sign_lines:
        p           = doc.add_paragraph()
        run         = p.add_run(text)
        run.bold    = bold
        run.font.name = _BODY_FONT
        run.font.size = _BODY_SIZE

    doc.save(target_path)
    return target_path


def generate_approval_note(
    title: str,
    ref_number: str,
    plant_unit: str,
    inspection_date: str,
    findings: List[str],
    sop_reference: str,
    recommendation: str,
    filename: str = "Approval_Note.docx",
    sop_citations: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """
    Creates an AI-drafted approval note in workspace/deliverables/ as a DRAFT.
    Returns a draft_payload dict that must be passed to finalize_official_document()
    after explicit human confirmation. This function is safe to call from the agent loop.
    """
    try:
        os.makedirs(DELIVERABLES_DIR, exist_ok=True)
        draft_filename = f"DRAFT_{filename}"
        draft_path     = os.path.join(DELIVERABLES_DIR, draft_filename)

        create_approval_note_docx(
            title=title,
            ref_number=ref_number,
            plant_unit=plant_unit,
            inspection_date=inspection_date,
            findings=findings,
            sop_reference=sop_reference,
            recommendation=recommendation,
            target_path=draft_path,
            is_official=False,
            sop_citations=sop_citations or [],
        )

        draft_payload = {
            "title":           title,
            "ref_number":      ref_number,
            "plant_unit":      plant_unit,
            "inspection_date": inspection_date,
            "findings":        findings,
            "sop_reference":   sop_reference,
            "recommendation":  recommendation,
            "target_filename": filename,
            "sop_citations":   sop_citations or [],
        }

        return {
            "status":                  "draft_created",
            "requires_human_approval": True,
            "message":                 "AI Draft generated. Human sign-off required before finalizing.",
            "draft_file":              draft_filename,
            "draft_payload":           draft_payload,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def finalize_official_document(
    draft_payload: Dict[str, Any],
    *,
    human_confirmed: bool,
) -> Dict[str, Any]:
    """
    Writes the official .docx deliverable to workspace/deliverables/.

    ENFORCEMENT GATE: raises PermissionError if human_confirmed is not exactly True.
    This function is intentionally excluded from the agent tool registry and is only
    reachable via the /api/approve_draft HTTP endpoint, which supplies human_confirmed=True
    after an explicit user action in the UI.
    """
    if human_confirmed is not True:
        raise PermissionError(
            "Human confirmation is required to finalize an official document. "
            "This function must not be called without explicit human sign-off."
        )

    try:
        os.makedirs(DELIVERABLES_DIR, exist_ok=True)
        filename = draft_payload.get("target_filename", "Official_Approval_Note.docx")
        if not filename.endswith(".docx"):
            filename += ".docx"
        target_path = os.path.join(DELIVERABLES_DIR, filename)

        create_approval_note_docx(
            title=draft_payload.get("title", "Inspection Approval Note"),
            ref_number=draft_payload.get("ref_number", "REF-2026-001"),
            plant_unit=draft_payload.get("plant_unit", "Plant Unit"),
            inspection_date=draft_payload.get("inspection_date", "2026-09-23"),
            findings=draft_payload.get("findings", []),
            sop_reference=draft_payload.get("sop_reference", "Per SOP guidelines"),
            recommendation=draft_payload.get("recommendation", "Approved"),
            target_path=target_path,
            is_official=True,
            sop_citations=draft_payload.get("sop_citations", []),
        )

        return {
            "status":            "success",
            "official_filename": filename,
            "file_path":         target_path,
            "message":           f"Human approval confirmed. Official deliverable '{filename}' created.",
        }
    except PermissionError:
        raise
    except Exception as e:
        return {"status": "error", "error": str(e)}


def draft_payload_to_html(draft_payload: Dict[str, Any], revision: int = 0) -> str:
    """
    Renders a draft_payload dict as structured HTML for inline browser preview.
    No file I/O — pure string rendering. Used by the /api/chat SSE stream.
    """
    revision_label = (
        f'<span class="revision-label">Revision {revision}</span>'
        if revision > 0
        else '<span class="revision-label">Initial Draft</span>'
    )
    findings      = draft_payload.get("findings", [])
    findings_html = "".join(f"<li>{f}</li>" for f in findings) if findings else "<li>No findings recorded.</li>"

    citations = draft_payload.get("sop_citations", [])
    if citations:
        cite_rows = "".join(
            f"<tr><td>{c.get('source','')}</td><td>{c.get('section','')}</td>"
            f"<td>{c.get('excerpt','')[:180]}</td></tr>"
            for c in citations
        )
        citations_html = f"""
  <div class="doc-section">
    <h3>4. Source References</h3>
    <table class="doc-cite-table">
      <thead><tr><th>SOP Document</th><th>Section</th><th>Relevant Clause</th></tr></thead>
      <tbody>{cite_rows}</tbody>
    </table>
  </div>"""
    else:
        citations_html = ""

    return f"""<div class="doc-preview">
  <div class="doc-header">
    <div class="doc-org-header">Government of India — Sovereign Operations Unit</div>
    <div class="doc-status-bar">
      <span class="doc-draft-tag">AI DRAFT — PENDING HUMAN SIGN-OFF</span>
      {revision_label}
    </div>
    <div class="doc-title">{draft_payload.get("title", "Inspection Approval Note")}</div>
  </div>
  <table class="doc-meta-table">
    <tr><th>Reference No.</th><td>{draft_payload.get("ref_number", "—")}</td></tr>
    <tr><th>Plant / Unit</th><td>{draft_payload.get("plant_unit", "—")}</td></tr>
    <tr><th>Inspection Date</th><td>{draft_payload.get("inspection_date", "—")}</td></tr>
  </table>
  <div class="doc-section">
    <h3>1. Key Inspection Findings</h3>
    <ul>{findings_html}</ul>
  </div>
  <div class="doc-section">
    <h3>2. SOP Grounding &amp; Reference</h3>
    <p>{draft_payload.get("sop_reference", "—")}</p>
  </div>
  <div class="doc-section">
    <h3>3. Recommendation</h3>
    <p>{draft_payload.get("recommendation", "—")}</p>
  </div>
  {citations_html}
  <div class="doc-signoff">
    <p>PENDING HUMAN REVIEW &amp; SIGN-OFF</p>
    <div class="signoff-line">___________________________</div>
    <p class="signoff-role">Authorized Approver Signature Required</p>
  </div>
</div>"""
