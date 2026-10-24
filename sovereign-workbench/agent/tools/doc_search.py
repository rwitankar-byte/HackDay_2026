"""
Document Search (RAG) Tool for Karyalaya AI.

Queries the local Chroma vector database for grounded SOP and manual information.
Strictly local retrieval — no cloud embeddings.

Changes (Fix 4/5):
  - Returns section_header and doc_type alongside each result.
  - Formats a citation string ("per {source}, §{section}") for agent use.
  - Accepts optional `where` dict for metadata-filtered retrieval (Fix 5).
    Always pass at minimum {"status": "active"} to exclude superseded documents.
"""

import os
import chromadb
from typing import Dict, Any, List, Optional

VECTOR_DB_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "knowledge_base", "vector_store")
)


def search_knowledge_base(
    query: str,
    top_k: int = 3,
    where: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Queries Chroma vector DB for documents matching the query.

    Args:
        query:  Natural language query string.
        top_k:  Maximum number of results to return.
        where:  Optional Chroma metadata filter dict, e.g. {"status": "active"}.
                When None, no filter is applied — caller should pass at minimum
                {"status": "active"} to avoid retrieving superseded documents.

    Returns:
        Dict with keys: status, query, count, results.
        Each result includes: content, source, section, doc_type, chunk_type,
        chunk_index, distance, citation.
    """
    try:
        if not os.path.exists(VECTOR_DB_DIR):
            return {
                "status": "error",
                "error":  f"Vector database not found at {VECTOR_DB_DIR}. Run ingest_pipeline.py first.",
            }

        client = chromadb.PersistentClient(path=VECTOR_DB_DIR)

        try:
            collection = client.get_collection(name="karyalaya_sops")
        except Exception:
            try:
                collection = client.get_collection(name="sovereign_sops")
            except Exception:
                return {
                    "status":  "warning",
                    "message": "SOP collection not populated yet. Run ingest_pipeline.py.",
                    "results": [],
                }

        count = collection.count()
        if count == 0:
            return {"status": "warning", "message": "SOP collection is empty.", "results": []}

        query_kwargs: Dict[str, Any] = {
            "query_texts": [query],
            "n_results":   min(top_k, count),
        }
        if where:
            query_kwargs["where"] = where

        results = collection.query(**query_kwargs)

        matched_docs: List[Dict[str, Any]] = []
        if results and "documents" in results and results["documents"]:
            docs      = results["documents"][0]
            metas     = results.get("metadatas", [[]])[0]
            distances = results.get("distances", [[]])[0] if results.get("distances") else []

            for i in range(len(docs)):
                meta    = metas[i] if i < len(metas) else {}
                source  = meta.get("source", "Unknown")
                section = meta.get("section_header", "")
                # Format citation string for direct agent use in sop_reference / sop_citations
                citation = f"per {source}, §{section}" if section else f"per {source}"
                matched_docs.append({
                    "content":     docs[i],
                    "source":      source,
                    "section":     section,
                    "doc_type":    meta.get("doc_type", "sop"),
                    "chunk_type":  meta.get("chunk_type", "prose"),
                    "chunk_index": meta.get("chunk_index", i),
                    "distance":    distances[i] if i < len(distances) else None,
                    "citation":    citation,
                })

        return {
            "status":  "success",
            "query":   query,
            "count":   len(matched_docs),
            "results": matched_docs,
        }

    except Exception as e:
        return {"status": "error", "error": str(e)}


if __name__ == "__main__":
    res = search_knowledge_base(
        "approval note format pressure testing requirements",
        where={"status": "active"},
    )
    print("Search Results:", res)
