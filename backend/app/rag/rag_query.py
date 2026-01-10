# rag_query.py
import json
import logging
import re
from typing import Any, Dict, List, Optional

import chromadb
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

COMMAND_INTENT_RE = re.compile(
    r"\b(commands?|steps?|step\s*by\s*step|run|execute|install|setup|deploy|onboard|restart|verify)\b",
    re.IGNORECASE,
)


class RAGQueryEngine:
    """Orchestrates RAG queries with semantic search and context building."""
    
    def __init__(
        self,
        db_dir: str = "chroma_db",
        chunks_collection: str = "runbook_chunks",
        embed_model: str = "BAAI/bge-small-en-v1.5",
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
    def _looks_like_command_request(q: str) -> bool:
        """Check if query is asking for commands/steps."""
        ql = q.lower()
        keywords = ["commands", "command", "steps", "step by step", "run", "execute", "install", "setup", "onboard"]
        return any(k in ql for k in keywords)

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
        k: int = 8,
        kind_filter: Optional[str] = None,
        require_code: bool = False,
        section_contains: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Orchestrate RAG retrieval:
        1) Semantic search
        2) Optional section post-filter
        3) Expand to full procedure steps if applicable
        """
        col = self.client.get_collection(name=self.chunks_collection)

        where = self._build_where(kind_filter, require_code)
        hits = self._retrieve_semantic_hits(col=col, query=query, k=k, where=where)

        logger.info(f"Retrieved {len(hits)} initial hits for query '{query}'")

        # Optional post-filter for substring match
        if section_contains:
            hits = [
                h
                for h in hits
                if section_contains in (h["metadata"].get("section_path_str") or "")
            ]

        if not hits:
            logger.warning(f"No hits found after filtering for query: {query}")
            return []

        best = hits[0]["metadata"]
        if best.get("kind") == "step":
            doc_id = best.get("doc_id")
            section = best.get("section_path_str")
            best_dist = hits[0].get("distance")
            if doc_id and section:
                logger.debug(f"Expanding to full procedure steps")
                return self._expand_procedure_steps(col=col, doc_id=doc_id, section_path_str=section, best_distance=best_dist)

        return hits

    def build_context(self, query: str, hits: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create context object for LLM prompting."""
        wants_commands = self._looks_like_command_request(query)

        sources = []
        context_blocks = []

        for h in hits:
            md = h["metadata"]
            src = f'{md.get("doc_id")}:{md.get("start_line")}-{md.get("end_line")}'
            sources.append(
                {
                    "source": src,
                    "section": md.get("section_path_str"),
                    "kind": md.get("kind"),
                    "step_no": md.get("step_no"),
                    "has_code": md.get("has_code"),
                }
            )

            # Prefer commands list when user wants commands
            if wants_commands and md.get("has_code"):
                cmds = md.get("commands") or []
                if cmds:
                    context_blocks.append(
                        f"Source: {src}\nSection: {md.get('section_path_str')}\n"
                        + "\n".join(f"- {c}" for c in cmds)
                    )
                else:
                    context_blocks.append(f"Source: {src}\n{h['text']}")
            else:
                context_blocks.append(f"Source: {src}\n{h['text']}")

        return {
            "wants_commands": wants_commands,
            "context_text": "\n\n---\n\n".join(context_blocks),
            "sources": sources,
        }

    def decide_mode(self, message: str, hits: list[dict]) -> str:
        """Determine response mode: commands_only or normal."""
        msg_intent = bool(COMMAND_INTENT_RE.search(message))
        has_command_hits = any(
            (h["metadata"].get("kind") == "step"
             and h["metadata"].get("has_code") is True
             and (h["metadata"].get("commands") or []))
            for h in hits
        )

        # Only commands_only when user intent is commands AND we have commands
        if msg_intent and has_command_hits:
            return "commands_only"

        return "normal"


# Global engine instance for backward compatibility
_rag_engine = RAGQueryEngine()


def decide_mode(message: str, hits: list[dict]) -> str:
    """Legacy function for backward compatibility."""
    return _rag_engine.decide_mode(message, hits)


def retrieve_chunks(
    query: str,
    k: int = 8,
    kind_filter: Optional[str] = None,
    require_code: bool = False,
    section_contains: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Legacy function for backward compatibility."""
    return _rag_engine.retrieve_chunks(
        query=query,
        k=k,
        kind_filter=kind_filter,
        require_code=require_code,
        section_contains=section_contains,
    )


def build_context(query: str, hits: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Legacy function for backward compatibility."""
    return _rag_engine.build_context(query=query, hits=hits)
