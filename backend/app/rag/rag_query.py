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

def _build_where(kind_filter, require_code):
    clauses = []
    if kind_filter is not None:
        clauses.append({"kind": {"$eq": kind_filter}})
    if require_code:
        clauses.append({"has_code": {"$eq": True}})

    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}

def _and_where(clauses: list[dict]) -> dict:
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}

def retrieve_chunks(
    query: str,
    k: int = 8,
    kind_filter: Optional[str] = None,
    require_code: bool = False,
    section_contains: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Returns list of hits: {text, metadata, distance}
    NOTE: metadata fields are scalars; list fields are stored as JSON strings.
    """
    client = chromadb.PersistentClient(path=DB_DIR)
    col = client.get_collection(name=CHUNKS_COLLECTION)

    model = SentenceTransformer(EMBED_MODEL)
    qemb = model.encode([query], normalize_embeddings=True).tolist()

    where = _build_where(kind_filter, require_code)

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
    for doc, md, dist in zip(docs, metas, dists):
        if section_contains:
            sp = (md.get("section_path_str") or "")
            if section_contains not in sp:
                continue

        # decode json strings back to Python types
        commands = json.loads(md.get("commands_json", "[]"))
        section_path = json.loads(md.get("section_path_json", "[]"))

        hits.append(
            {
                "text": doc,
                "metadata": {
                    **md,
                    "commands": commands,
                    "section_path": section_path,
                },
                "distance": dist,
            }
        )

    # If these are step chunks, order by step_no (so command sequences stay correct)
    if hits and hits[0]["metadata"].get("kind") == "step":
        hits.sort(key=lambda h: int(h["metadata"].get("step_no", 10**9)))

    # ✅ CONTIGUOUS STEP EXPANSION (new)
        best = hits[0]["metadata"]
        doc_id = best.get("doc_id")
        section = best.get("section_path_str")

        # fetch ALL steps from the same doc + section (no embeddings needed)
        where_all_steps = _and_where([
            {"doc_id": {"$eq": doc_id}},
            {"section_path_str": {"$eq": section}},
            {"kind": {"$eq": "step"}},
        ])

        all_res = col.get(
            where=where_all_steps,
            include=["documents", "metadatas"],
        )

        all_docs = all_res.get("documents", []) or []
        all_metas = all_res.get("metadatas", []) or []

        expanded: list[dict] = []
        for doc_text, md in zip(all_docs, all_metas):
            commands = json.loads(md.get("commands_json", "[]"))
            section_path = json.loads(md.get("section_path_json", "[]"))

            expanded.append({
                "text": doc_text,
                "metadata": {**md, "commands": commands, "section_path": section_path},
                "distance": None,  # not applicable (this is not an embedding search)
            })

        expanded.sort(key=lambda h: int(h["metadata"].get("step_no", 10**9)))
        return expanded
    
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
