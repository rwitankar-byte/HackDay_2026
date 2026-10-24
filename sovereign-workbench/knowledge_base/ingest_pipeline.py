"""
Local RAG Ingestion Pipeline for Karyalaya AI.

Two collections:
  karyalaya_sops       — Plant SOPs and technical references (Fix 3/4/6)
  karyalaya_templates  — Past approved documents used as style/structure templates (Fix 2)

Chunking strategy (Fix 3):
  1. Tables (lines starting with |) → kept as single intact chunks
  2. Section headers (numbered, markdown, ALL-CAPS-COLON) → each starts a new chunk
  3. Prose fallback → paragraph-boundary split, soft 400-char limit with 50-char overlap

Metadata stored per chunk:
  source, chunk_index, chunk_type, section_header, doc_type, equipment_tags, status

supersede_document() (Fix 6) marks all chunks from a given file as status=superseded.
ingest_templates()   (Fix 2) also extracts a structural summary via the LLM router.
"""

import os
import re
import glob
import chromadb
from typing import Dict, Any, List, Optional, Tuple

BASE_DIR      = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SOPS_DIR      = os.path.join(BASE_DIR, "workspace", "sops")
TEMPLATES_DIR = os.path.join(BASE_DIR, "workspace", "templates")
VECTOR_DB_DIR = os.path.join(os.path.dirname(__file__), "vector_store")

_EQUIP_TAG_RE = re.compile(r'\b[A-Z]{1,3}-\d{2,4}-?[A-Z]?\b')
_SECTION_RE   = re.compile(
    r'^(\d+[\.\d]*\.?\s+[A-Z]|#{1,3}\s|[A-Z][A-Z\s]{4,}:)', re.MULTILINE
)
_TABLE_LINE_RE = re.compile(r'^\s*\|.+\|', re.MULTILINE)


def get_chroma_client() -> chromadb.PersistentClient:
    """Initializes local persistent Chroma DB client."""
    os.makedirs(VECTOR_DB_DIR, exist_ok=True)
    return chromadb.PersistentClient(path=VECTOR_DB_DIR)


def extract_text_from_pdf(file_path: str) -> str:
    """
    Extracts plain text from a PDF using PyMuPDF.
    Falls back to an empty string on any extraction error.
    """
    try:
        import pymupdf  # PyMuPDF >= 1.24
        text_parts = []
        with pymupdf.open(file_path) as doc:
            for page in doc:
                text_parts.append(page.get_text())
        return "\n\n".join(text_parts).strip()
    except Exception as e:
        print(f"[INGEST WARNING] PDF extraction failed for {file_path}: {e}")
        return ""


def _extract_equipment_tags(text: str) -> str:
    """Returns a comma-separated string of unique equipment tags found in text."""
    tags = sorted(set(_EQUIP_TAG_RE.findall(text)))
    return ",".join(tags)


def chunk_text_structural(
    text: str,
    doc_type: str = "sop",
    chunk_size: int = 400,
    overlap: int = 50,
) -> List[Tuple[str, Dict[str, str]]]:
    """
    Structural chunker that respects document boundaries.

    Returns a list of (chunk_text, metadata_dict) tuples. Each metadata dict
    contains: chunk_type, section_header, doc_type, equipment_tags, status.

    Strategy:
      1. Extract table blocks (pipe-delimited lines) as single intact chunks.
         Splitting a table mid-row produces meaningless, misleading fragments.
      2. Split remaining text at section-header boundaries, attaching the header
         to its body so retrieval always returns the header alongside its content.
      3. Prose fallback: split at paragraph breaks (double newline), with soft
         400-char limit and 50-char overlap to preserve sentence context.
    """
    chunks: List[Tuple[str, Dict[str, str]]] = []
    current_header = ""

    def _make_meta(chunk_type: str, header: str, content: str) -> Dict[str, str]:
        return {
            "chunk_type":     chunk_type,
            "section_header": header[:120],
            "doc_type":       doc_type,
            "equipment_tags": _extract_equipment_tags(content),
            "status":         "active",
        }

    # ── Step 1: Isolate table blocks ──────────────────────────────────────────
    # Split text around table blocks, keeping them intact.
    table_split = re.split(r'(\n(?:\s*\|.+\|\s*\n)+)', text)
    non_table_parts: List[str] = []
    for part in table_split:
        stripped = part.strip()
        if not stripped:
            continue
        if _TABLE_LINE_RE.match(stripped):
            chunks.append((stripped, _make_meta("table", current_header, stripped)))
        else:
            non_table_parts.append(part)

    prose = "\n\n".join(non_table_parts)

    # ── Step 2: Split at section headers ──────────────────────────────────────
    # finditer returns all header matches; we use them as split boundaries.
    sections: List[Tuple[str, str]] = []  # (header_text, body_text)
    last_end = 0
    for m in _SECTION_RE.finditer(prose):
        body = prose[last_end:m.start()].strip()
        if body and last_end > 0:
            sections.append((current_header, body))
        current_header = m.group(0).strip()
        last_end = m.end()
    tail = prose[last_end:].strip()
    if tail:
        sections.append((current_header, tail))

    if not sections:
        # No section headers found — treat entire prose as one block
        sections = [(current_header, prose.strip())]

    # ── Step 3: Prose chunks within each section ──────────────────────────────
    for header, body in sections:
        paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
        current_chunk = ""
        for para in paragraphs:
            if len(current_chunk) + len(para) + 2 <= chunk_size:
                current_chunk = (current_chunk + "\n\n" + para).strip()
            else:
                if current_chunk:
                    chunks.append((current_chunk, _make_meta("section", header, current_chunk)))
                    # Overlap: carry end of previous chunk into next
                    current_chunk = current_chunk[-overlap:].strip() + "\n\n" + para
                else:
                    current_chunk = para
        if current_chunk:
            chunks.append((current_chunk, _make_meta("section", header, current_chunk)))

    return chunks if chunks else [(text, _make_meta("prose", "", text))]


def _read_file(file_path: str) -> str:
    """Reads text content from .txt/.md or extracts text from .pdf."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        return extract_text_from_pdf(file_path)
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def ingest_sops(sops_dir: Optional[str] = None) -> Dict[str, Any]:
    """
    Ingests all SOP files from workspace/sops/ into the karyalaya_sops Chroma collection.

    Supports: .txt, .md, .pdf
    Safe to call repeatedly — uses upsert so duplicate chunk IDs are updated, not doubled.
    All chunks receive status='active' and full structural metadata.
    """
    source_dir = sops_dir or SOPS_DIR
    try:
        client     = get_chroma_client()
        collection = client.get_or_create_collection(name="karyalaya_sops")

        sop_files = (
            glob.glob(os.path.join(source_dir, "*.txt")) +
            glob.glob(os.path.join(source_dir, "*.md")) +
            glob.glob(os.path.join(source_dir, "*.pdf"))
        )

        if not sop_files:
            return {
                "status":  "warning",
                "message": f"No SOP files (.txt, .md, .pdf) found in {source_dir}",
            }

        total_chunks     = 0
        files_processed  = 0
        documents        = []
        metadatas        = []
        ids              = []

        for file_path in sop_files:
            filename = os.path.basename(file_path)
            content  = _read_file(file_path)
            if not content:
                print(f"[INGEST WARNING] Skipping {filename}: empty content.")
                continue

            chunk_pairs = chunk_text_structural(content, doc_type="sop")
            for idx, (chunk_text, meta) in enumerate(chunk_pairs):
                meta["source"] = filename
                chunk_id       = f"{filename}_chunk_{idx}"
                documents.append(chunk_text)
                metadatas.append(meta)
                ids.append(chunk_id)
                total_chunks += 1

            files_processed += 1
            print(f"[INGEST] {filename} — {len(chunk_pairs)} chunks")

        if documents:
            collection.upsert(documents=documents, metadatas=metadatas, ids=ids)

        return {
            "status":                "success",
            "files_processed":       files_processed,
            "total_chunks_ingested": total_chunks,
            "vector_store_path":     VECTOR_DB_DIR,
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}


def ingest_templates(
    templates_dir: Optional[str] = None,
    router=None,
) -> Dict[str, Any]:
    """
    Ingests past approved documents as style/structure templates.

    For each file:
      1. Structural chunks are stored in karyalaya_templates with doc_type='template'.
      2. If a router is provided, a single structural summary chunk is extracted via
         the LLM (section order, tone, typical length) and stored with
         chunk_type='structural_summary'. This summary is injected into the drafting
         prompt at generation time to match the template's structure and tone.

    Safe to call repeatedly — upserts by deterministic chunk ID.
    """
    source_dir = templates_dir or TEMPLATES_DIR
    os.makedirs(source_dir, exist_ok=True)

    try:
        client     = get_chroma_client()
        collection = client.get_or_create_collection(name="karyalaya_templates")

        template_files = (
            glob.glob(os.path.join(source_dir, "*.txt")) +
            glob.glob(os.path.join(source_dir, "*.md")) +
            glob.glob(os.path.join(source_dir, "*.pdf"))
        )

        if not template_files:
            return {
                "status":  "warning",
                "message": f"No template files found in {source_dir}",
            }

        total_chunks    = 0
        files_processed = 0
        documents       = []
        metadatas       = []
        ids             = []

        for file_path in template_files:
            filename = os.path.basename(file_path)
            content  = _read_file(file_path)
            if not content:
                print(f"[INGEST WARNING] Skipping template {filename}: empty content.")
                continue

            chunk_pairs = chunk_text_structural(content, doc_type="template")
            for idx, (chunk_text, meta) in enumerate(chunk_pairs):
                meta["source"] = filename
                documents.append(chunk_text)
                metadatas.append(meta)
                ids.append(f"tmpl_{filename}_chunk_{idx}")
                total_chunks += 1

            # ── LLM structural summary (one per document) ─────────────────────
            if router is not None:
                try:
                    summary_prompt = (
                        f"Read this approved document and extract a structural summary.\n"
                        f"Document content (first 3000 chars):\n{content[:3000]}\n\n"
                        "Return ONLY a JSON object with keys: "
                        "\"section_order\" (list of section title strings), "
                        "\"tone\" (1-sentence description, e.g. 'formal, third-person, passive voice'), "
                        "\"approx_length\" (e.g. '400-600 words'). "
                        "No other text."
                    )
                    raw_summary = router.generate(
                        model_name=router.classify_request("document drafting")[1]["name"],
                        prompt=summary_prompt,
                        system_prompt=(
                            "You extract structural summaries from official documents. "
                            "Respond with valid JSON only."
                        ),
                        temperature=0.05,
                    )
                    summary_meta = {
                        "source":         filename,
                        "chunk_type":     "structural_summary",
                        "section_header": "",
                        "doc_type":       "template",
                        "equipment_tags": "",
                        "status":         "active",
                    }
                    documents.append(raw_summary)
                    metadatas.append(summary_meta)
                    ids.append(f"tmpl_{filename}_summary")
                    total_chunks += 1
                    print(f"[INGEST] {filename} — structural summary extracted")
                except Exception as e:
                    print(f"[INGEST WARNING] Structural summary failed for {filename}: {e}")

            files_processed += 1
            print(f"[INGEST] {filename} — {len(chunk_pairs)} chunks")

        if documents:
            collection.upsert(documents=documents, metadatas=metadatas, ids=ids)

        return {
            "status":                "success",
            "files_processed":       files_processed,
            "total_chunks_ingested": total_chunks,
            "vector_store_path":     VECTOR_DB_DIR,
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}


def supersede_document(
    filename: str,
    collection_name: str = "karyalaya_sops",
) -> Dict[str, Any]:
    """
    Marks all chunks from the given filename as status='superseded'.

    Chroma's update() API accepts a list of IDs and a parallel list of metadata
    dicts. Only the 'status' key is changed; all other metadata is preserved by
    fetching the existing records first, then merging.

    Returns the number of chunks updated.
    """
    try:
        client     = get_chroma_client()
        collection = client.get_collection(name=collection_name)

        existing = collection.get(where={"source": filename}, include=["metadatas"])
        ids_to_update = existing.get("ids", [])
        if not ids_to_update:
            return {
                "status":  "warning",
                "message": f"No chunks found for '{filename}' in {collection_name}.",
            }

        updated_metas = []
        for meta in existing.get("metadatas", []):
            m = dict(meta)
            m["status"] = "superseded"
            updated_metas.append(m)

        collection.update(ids=ids_to_update, metadatas=updated_metas)

        return {
            "status":          "success",
            "chunks_updated":  len(ids_to_update),
            "filename":        filename,
            "collection":      collection_name,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


if __name__ == "__main__":
    res = ingest_sops()
    print("SOP Ingestion Result:", res)
