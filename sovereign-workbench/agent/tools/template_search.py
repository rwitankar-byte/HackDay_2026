"""
Template Search Tool for Karyalaya AI.

Queries the karyalaya_templates Chroma collection for past approved documents
stored as style/structure templates. Returns both:
  - chunk_type='structural_summary'  — LLM-extracted section order + tone (one per doc)
  - chunk_type='section'/'prose'/'table'  — raw content chunks for style examples

Only retrieves status='active' templates (superseded templates are excluded).
"""

import os
import chromadb
from typing import Dict, Any, List, Optional

VECTOR_DB_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "knowledge_base", "vector_store")
)


def search_templates(
    query: str,
    top_k: int = 2,
    summaries_only: bool = False,
) -> Dict[str, Any]:
    """
    Queries karyalaya_templates for style/structure examples.

    Args:
        query:          Natural language query (e.g. 'approval note format').
        top_k:          Maximum results to return.
        summaries_only: If True, only return structural_summary chunks (for prompt injection).

    Returns:
        Dict with keys: status, count, structural_summaries, style_chunks.
        structural_summaries: List of LLM-extracted section-order/tone dicts (one per template doc).
        style_chunks: List of raw content chunks for formatting reference.
    """
    try:
        if not os.path.exists(VECTOR_DB_DIR):
            return {
                "status":               "warning",
                "message":              "Template collection not found. Upload a style template first.",
                "structural_summaries": [],
                "style_chunks":         [],
            }

        from chromadb.config import Settings
        client = chromadb.PersistentClient(
            path=VECTOR_DB_DIR,
            settings=Settings(anonymized_telemetry=False, is_persistent=True)
        )
        try:
            collection = client.get_collection(name="karyalaya_templates")
        except Exception:
            return {
                "status":               "warning",
                "message":              "No templates indexed yet. Upload a past approved document as a style template.",
                "structural_summaries": [],
                "style_chunks":         [],
            }

        count = collection.count()
        if count == 0:
            return {
                "status":               "warning",
                "message":              "Template collection is empty.",
                "structural_summaries": [],
                "style_chunks":         [],
            }

        base_where: Dict[str, Any] = {"status": "active"}

        # ── Retrieve structural summaries ──────────────────────────────────────
        structural_summaries: List[Dict[str, Any]] = []
        try:
            summary_results = collection.get(
                where={"$and": [{"status": {"$eq": "active"}}, {"chunk_type": {"$eq": "structural_summary"}}]},
                include=["documents", "metadatas"],
            )
            for doc, meta in zip(
                summary_results.get("documents", []),
                summary_results.get("metadatas", []),
            ):
                structural_summaries.append({
                    "source":  meta.get("source", "Unknown"),
                    "summary": doc,
                })
        except Exception:
            pass  # No summaries yet — templates were ingested without router

        if summaries_only:
            return {
                "status":               "success",
                "count":                len(structural_summaries),
                "structural_summaries": structural_summaries,
                "style_chunks":         [],
            }

        # ── Retrieve raw style chunks (similarity search, exclude summaries) ───
        style_chunks: List[Dict[str, Any]] = []
        try:
            chunk_results = collection.query(
                query_texts=[query],
                n_results=min(top_k, count),
                where={"$and": [{"status": {"$eq": "active"}}, {"chunk_type": {"$ne": "structural_summary"}}]},
            )
            docs   = chunk_results.get("documents", [[]])[0]
            metas  = chunk_results.get("metadatas", [[]])[0]
            for doc, meta in zip(docs, metas):
                style_chunks.append({
                    "content": doc,
                    "source":  meta.get("source", "Unknown"),
                    "section": meta.get("section_header", ""),
                })
        except Exception:
            # Fallback: plain query without chunk_type filter if Chroma doesn't support $ne
            try:
                chunk_results = collection.query(
                    query_texts=[query],
                    n_results=min(top_k, count),
                    where=base_where,
                )
                docs  = chunk_results.get("documents", [[]])[0]
                metas = chunk_results.get("metadatas", [[]])[0]
                for doc, meta in zip(docs, metas):
                    if meta.get("chunk_type") != "structural_summary":
                        style_chunks.append({
                            "content": doc,
                            "source":  meta.get("source", "Unknown"),
                            "section": meta.get("section_header", ""),
                        })
            except Exception:
                pass

        return {
            "status":               "success",
            "count":                len(structural_summaries) + len(style_chunks),
            "structural_summaries": structural_summaries,
            "style_chunks":         style_chunks,
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}


if __name__ == "__main__":
    res = search_templates("approval note format inspection findings")
    print("Template Search:", res)
