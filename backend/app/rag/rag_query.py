# rag_query.py
import json
from typing import Any, Dict, List, Optional, Tuple

import chromadb
from sentence_transformers import SentenceTransformer

DB_DIR = "chroma_db"
CHUNKS_COLLECTION = "runbook_chunks"
EMBED_MODEL = "BAAI/bge-small-en-v1.5"


def _looks_like_command_request(q: str) -> bool:
    ql = q.lower()
    keywords = ["commands", "command", "steps", "step by step", "run", "execute", "install", "setup", "onboard"]
    return any(k in ql for k in keywords)

def _and_where(clauses: List[dict]) -> Optional[dict]:
    clauses = [c for c in clauses if c]
    if not clauses:
        return None
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}


def _build_where(kind_filter: Optional[str], require_code: bool) -> Optional[dict]:
    clauses = []
    if kind_filter:
        clauses.append({"kind": {"$eq": kind_filter}})
    if require_code:
        clauses.append({"has_code": {"$eq": True}})
    return _and_where(clauses)


def _decode_metadata(md: Dict[str, Any]) -> Dict[str, Any]:
    """Chroma metadata is scalar-only; decode JSON-serialized fields back to lists."""
    commands = json.loads(md.get("commands_json", "[]"))
    section_path = json.loads(md.get("section_path_json", "[]"))
    return {**md, "commands": commands, "section_path": section_path}


def retrieve_semantic_hits(
    col,
    query: str,
    k: int,
    where: Optional[dict],
) -> List[Dict[str, Any]]:
    """Vector search (embeddings) -> list of hits with decoded metadata."""
    model = SentenceTransformer(EMBED_MODEL)
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
                "metadata": _decode_metadata(md),
                "distance": dist,
            }
        )
    return hits


def expand_procedure_steps(
    col,
    doc_id: str,
    section_path_str: str,
) -> List[Dict[str, Any]]:
    """
    Deterministic fetch of *all step chunks* for a given doc + section, ordered by step_no.
    Uses metadata filtering only (no embeddings).
    """
    where_all_steps = _and_where(
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
                "metadata": _decode_metadata(md),
                "distance": None,  # not applicable
            }
        )

    expanded.sort(key=lambda h: int(h["metadata"].get("step_no", 10**9)))
    return expanded


def retrieve_chunks(
    query: str,
    k: int = 8,
    kind_filter: Optional[str] = None,
    require_code: bool = False,
    section_contains: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Orchestrator:
    1) semantic retrieval
    2) optional section post-filter
    3) if best hit is a step -> expand to full procedure steps for that doc+section
    """
    client = chromadb.PersistentClient(path=DB_DIR)
    col = client.get_collection(name=CHUNKS_COLLECTION)

    where = _build_where(kind_filter, require_code)
    hits = retrieve_semantic_hits(col=col, query=query, k=k, where=where)

    # Optional post-filter for substring match (Chroma where is often exact-match only)
    if section_contains:
        hits = [
            h
            for h in hits
            if section_contains in (h["metadata"].get("section_path_str") or "")
        ]

    if not hits:
        return []

    best = hits[0]["metadata"]
    if best.get("kind") == "step":
        doc_id = best.get("doc_id")
        section = best.get("section_path_str")
        if doc_id and section:
            return expand_procedure_steps(col=col, doc_id=doc_id, section_path_str=section)

    return hits


def build_context(query: str, hits: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Creates a compact context object for prompting the LLM.
    """
    wants_commands = _looks_like_command_request(query)

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

        # When user wants commands, prefer commands list. Otherwise include chunk text.
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
