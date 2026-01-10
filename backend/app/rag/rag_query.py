# rag_query.py
import json
import logging
import re
from typing import Any, Dict, List, Optional

import chromadb
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

MAX_DISTANCE = 0.35
DEFAULT_TOP_K = 8

class RAGQueryEngine:
    """Orchestrates RAG queries with semantic search and context building."""
    
    def __init__(
        self,
        db_dir: str = "chroma_db",
        chunks_collection: str = "runbook_chunks",
        embed_model: str = "BAAI/bge-large-en-v1.5",
    ):
        """
        Initialize RAGQueryEngine.
        
        Args:
            db_dir: Directory for ChromaDB persistence
            chunks_collection: Name of ChromaDB collection
            embed_model: SentenceTransformer model for embeddings
        """
        self.db_dir = db_dir
        self.chunks_collection = chunks_collection
        self.embed_model = embed_model
        self.client = chromadb.PersistentClient(path=db_dir)
        logger.info(f"RAGQueryEngine initialized with db_dir={db_dir}, collection={chunks_collection}, model={embed_model}")

    @staticmethod
    def _and_where(clauses: List[dict]) -> Optional[dict]:
        """Combine multiple where clauses with AND logic."""
        clauses = [c for c in clauses if c]
        if not clauses:
            return None
        return clauses[0] if len(clauses) == 1 else {"$and": clauses}

    @staticmethod
    def _build_where(kind_filter: Optional[str], require_code: bool) -> Optional[dict]:
        """Build ChromaDB where clause from filters."""
        clauses = []
        if kind_filter:
            clauses.append({"kind": {"$eq": kind_filter}})
        if require_code:
            clauses.append({"has_code": {"$eq": True}})
        return RAGQueryEngine._and_where(clauses)

    @staticmethod
    def _decode_metadata(md: Dict[str, Any]) -> Dict[str, Any]:
        """Decode JSON-serialized metadata fields back to lists."""
        commands = json.loads(md.get("commands_json", "[]"))
        section_path = json.loads(md.get("section_path_json", "[]"))
        return {**md, "commands": commands, "section_path": section_path}

    def _retrieve_semantic_hits(
        self,
        col,
        query: str,
        k: int,
        where: Optional[dict],
    ) -> List[Dict[str, Any]]:
        """Perform vector search with embeddings."""
        logger.debug(f"Performing semantic search for: {query}")
        model = SentenceTransformer(self.embed_model)
        qemb = model.encode([query], normalize_embeddings=True).tolist()

        res = col.query(
            query_embeddings=qemb,
            n_results=k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )

        docs = res["documents"][0] if res.get("documents") else []
        metas = res["metadatas"][0] if res.get("metadatas") else []
        dists = res["distances"][0] if res.get("distances") else []

        hits: List[Dict[str, Any]] = []
        for doc_text, md, dist in zip(docs, metas, dists):
            hits.append(
                {
                    "text": doc_text,
                    "metadata": self._decode_metadata(md),
                    "distance": dist,
                }
            )
        return hits

    def _expand_procedure_steps(
        self,
        col,
        doc_id: str,
        section_path_str: str,
        best_distance: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch all step chunks for a given doc + section, ordered by step_no."""
        logger.debug(f"Expanding procedure steps for doc={doc_id}, section={section_path_str}")
        where_all_steps = self._and_where(
            [
                {"doc_id": {"$eq": doc_id}},
                {"section_path_str": {"$eq": section_path_str}},
                {"kind": {"$eq": "step"}},
            ]
        )

        all_res = col.get(where=where_all_steps, include=["documents", "metadatas"])
        all_docs = all_res.get("documents", []) or []
        all_metas = all_res.get("metadatas", []) or []

        expanded: List[Dict[str, Any]] = []
        for doc_text, md in zip(all_docs, all_metas):
            expanded.append(
                {
                    "text": doc_text,
                    "metadata": self._decode_metadata(md),
                    "distance": best_distance,
                }
            )

        expanded.sort(key=lambda h: int(h["metadata"].get("step_no", 10**9)))
        return expanded

    def retrieve_chunks(
        self,
        query: str,
        k: int = DEFAULT_TOP_K,
    ) -> List[Dict[str, Any]]:
        """
        Orchestrate RAG retrieval:
        1) Semantic search
        2) Relevance gate
        3) Deterministic step expansion (if applicable)
        """
        col = self.client.get_collection(name=self.chunks_collection)

        hits = self._retrieve_semantic_hits(
            col=col,
            query=query,
            k=k,
            where=None,  # 🔥 no filters from UI
        )

        if not hits:
            logger.warning(f"No semantic hits for query: {query}")
            return []

        # 🔒 Relevance gate (CRITICAL)
        best_dist = hits[0]["distance"]
        if best_dist is None or best_dist > MAX_DISTANCE:
            logger.info(
                f"Query '{query}' rejected by distance gate (dist={best_dist})"
            )
            return []

        best_md = hits[0]["metadata"]

        # 🔁 Auto-expand procedures
        if best_md.get("kind") == "step":
            doc_id = best_md.get("doc_id")
            section = best_md.get("section_path_str")
            if doc_id and section:
                return self._expand_procedure_steps(
                    col=col,
                    doc_id=doc_id,
                    section_path_str=section,
                    best_distance=best_dist,
                )

        return hits

    def build_context(self, hits: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Build clean context for the LLM.
        - No source paths
        - No file names
        - No instructions
        """
        context_blocks: List[str] = []
        sources: List[Dict[str, Any]] = []

        for h in hits:
            md = h["metadata"]
            text = h["text"].strip()

            commands = md.get("commands") or []
            if commands:
                block = (
                    f"{text}\n\n"
                    "```bash\n"
                    + "\n".join(commands)
                    + "\n```"
                )
            else:
                block = text

            context_blocks.append(block)

            sources.append(
                {
                    "source": f"{md.get('doc_id')}:{md.get('start_line')}-{md.get('end_line')}",
                    "section": md.get("section_path_str"),
                }
            )

        return {
            "context_text": "\n\n".join(context_blocks),
            "sources": sources,
        }

# Global engine instance for backward compatibility
_rag_engine = RAGQueryEngine()

def retrieve_chunks(
    query: str, k: int = DEFAULT_TOP_K
) -> List[Dict[str, Any]]:
    """Legacy function for backward compatibility."""
    return _rag_engine.retrieve_chunks(
        query=query,
        k=k,
    )

def build_context(hits: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Legacy function for backward compatibility."""
    return _rag_engine.build_context(hits=hits)
