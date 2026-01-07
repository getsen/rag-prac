import glob
import hashlib
import os
import json
from typing import Dict, List, Any, Tuple

import chromadb
from sentence_transformers import SentenceTransformer

from app.chunk.chunk import chunks_from_file  # your existing function that returns enriched chunks


DB_DIR = "chroma_db"
CHUNKS_COLLECTION = "runbook_chunks"
DOCS_COLLECTION = "runbook_docs"   # registry
EMBED_MODEL = "BAAI/bge-small-en-v1.5"


def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def doc_id_from_path(path: str) -> str:
    # Keep it stable; you can also use relative path from docs root
    return path.replace("\\", "/")


def ensure_collections(client: chromadb.PersistentClient):
    chunks_col = client.get_or_create_collection(name=CHUNKS_COLLECTION)
    docs_col = client.get_or_create_collection(name=DOCS_COLLECTION)
    return chunks_col, docs_col


def doc_already_ingested(docs_col, doc_id: str, doc_hash: str) -> bool:
    """
    Checks registry collection for doc_id. If hash matches, skip.
    """
    res = docs_col.get(ids=[doc_id], include=["metadatas"])
    if not res or not res.get("ids"):
        return False
    md = res["metadatas"][0] if res["metadatas"] else None
    return bool(md and md.get("doc_hash") == doc_hash)


def upsert_doc_registry(docs_col, doc_id: str, doc_hash: str, chunk_count: int):
    docs_col.upsert(
        ids=[doc_id],
        documents=[f"registry:{doc_id}"],  # not used for embedding/querying
        metadatas=[{"doc_hash": doc_hash, "chunk_count": chunk_count}],
    )


def delete_existing_doc_chunks(chunks_col, doc_id: str):
    """
    If a doc changed, delete old chunks for that doc_id.
    Chroma supports delete(where=...).
    """
    chunks_col.delete(where={"doc_id": doc_id})


def ingest_docs_on_start(
    docs_folder: str = "docs",
    force_reindex_changed: bool = True,
) -> Dict[str, Any]:
    """
    - Scans docs_folder for *.md
    - For each doc: if (doc_id, doc_hash) already in registry => skip
      else chunk + embed + upsert. If changed and force_reindex_changed => delete old chunks first.
    Returns stats.
    """
    client = chromadb.PersistentClient(path=DB_DIR)
    chunks_col, docs_col = ensure_collections(client)

    model = SentenceTransformer(EMBED_MODEL)

    md_files = sorted(glob.glob(os.path.join(docs_folder, "*.md")))
    if not md_files:
        return {"docs_found": 0, "docs_ingested": 0, "docs_skipped": 0, "chunks_upserted": 0}

    docs_ingested = 0
    docs_skipped = 0
    chunks_upserted = 0

    for path in md_files:
        doc_id = doc_id_from_path(path)
        doc_hash = file_sha256(path)

        if doc_already_ingested(docs_col, doc_id, doc_hash):
            docs_skipped += 1
            continue

        # doc is new or changed
        if force_reindex_changed:
            delete_existing_doc_chunks(chunks_col, doc_id)

        # chunk the doc (your chunker should set doc_id = path or we set it here)
        chunks = chunks_from_file(path, procedure_aware=True)

        # Build records for Chroma
        ids: List[str] = []
        texts: List[str] = []
        metas: List[dict] = []

        for c in chunks:
            # Ensure doc_id is correct (in case your chunker sets doc_id differently)
            c.doc_id = doc_id

            ids.append(c.chunk_id)
            texts.append(c.text)
            metas.append(
            {
                "doc_id": c.doc_id,
                "section_path_str": " > ".join(c.section_path),   # ✅ string
                # If you still want the array, store it as JSON text:
                "section_path_json": json.dumps(c.section_path, ensure_ascii=False),

                "kind": c.kind,
                "step_no": int(c.step_no) if c.step_no is not None else -1,  # ✅ int
                "has_code": bool(c.has_code),                                  # ✅ bool

                # commands must also be scalar -> store as a single string OR JSON string
                "commands_json": json.dumps(c.commands or [], ensure_ascii=False),

                "header_level": int(c.header_level),
                "start_line": int(c.start_line),
                "end_line": int(c.end_line),
            }
        )

        # Embed + upsert chunks
        embeddings = model.encode(texts, normalize_embeddings=True).tolist()
        chunks_col.upsert(ids=ids, documents=texts, metadatas=metas, embeddings=embeddings)

        # Update registry
        upsert_doc_registry(docs_col, doc_id, doc_hash, chunk_count=len(ids))

        docs_ingested += 1
        chunks_upserted += len(ids)

    return {
        "docs_found": len(md_files),
        "docs_ingested": docs_ingested,
        "docs_skipped": docs_skipped,
        "chunks_upserted": chunks_upserted,
        "db_dir": DB_DIR,
        "embed_model": EMBED_MODEL,
    }
