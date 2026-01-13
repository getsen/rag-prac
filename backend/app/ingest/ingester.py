import glob
import hashlib
import os
import json
import logging
from typing import Dict, List, Any

import chromadb
from sentence_transformers import SentenceTransformer

from app.chunk.chunk import chunks_from_file
from app.chunk.chunk_json import chunks_from_json_file
from app.config import get_settings

logger = logging.getLogger(__name__)


class DocumentIngester:
    """Handles document ingestion, chunking, embedding, and storage in ChromaDB."""
    
    def __init__(
        self,
        db_dir: str = None,
        chunks_collection: str = None,
        docs_collection: str = None,
        embed_model: str = None,
    ):
        """Initialize the ingester with configuration from settings or parameters."""
        settings = get_settings()
        
        # Use provided values or fall back to settings
        self.db_dir = db_dir or settings.chroma_db_dir
        self.chunks_collection_name = chunks_collection or settings.chroma_chunks_collection
        self.docs_collection_name = docs_collection or settings.chroma_docs_collection
        self.embed_model_name = embed_model or settings.chroma_embed_model
        
        self.client = chromadb.PersistentClient(path=self.db_dir)
        self.model = SentenceTransformer(self.embed_model_name)
        self.chunks_col = None
        self.docs_col = None
        logger.info(f"DocumentIngester initialized with db_dir={self.db_dir}, embed_model={self.embed_model_name}")
    
    @staticmethod
    def file_sha256(path: str) -> str:
        """Calculate SHA256 hash of a file."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(1024 * 1024), b""):
                h.update(block)
        return h.hexdigest()
    
    @staticmethod
    def doc_id_from_path(path: str) -> str:
        """Convert file path to stable document ID."""
        return path.replace("\\", "/")
    
    def ensure_collections(self):
        """Create or get collections from ChromaDB."""
        self.chunks_col = self.client.get_or_create_collection(name=self.chunks_collection_name)
        self.docs_col = self.client.get_or_create_collection(name=self.docs_collection_name)
        return self.chunks_col, self.docs_col
    
    def doc_already_ingested(self, doc_id: str, doc_hash: str) -> bool:
        """Check if document is already ingested with matching hash."""
        res = self.docs_col.get(ids=[doc_id], include=["metadatas"])
        if not res or not res.get("ids"):
            return False
        md = res["metadatas"][0] if res["metadatas"] else None
        return bool(md and md.get("doc_hash") == doc_hash)
    
    def upsert_doc_registry(self, doc_id: str, doc_hash: str, chunk_count: int):
        """Update document registry with ingestion info."""
        self.docs_col.upsert(
            ids=[doc_id],
            documents=[f"registry:{doc_id}"],
            metadatas=[{"doc_hash": doc_hash, "chunk_count": chunk_count}],
        )
    
    def delete_existing_doc_chunks(self, doc_id: str):
        """Delete existing chunks for a document."""
        self.chunks_col.delete(where={"doc_id": doc_id})
    
    def ingest_docs(
        self,
        docs_folder: str = "docs",
        force_reindex_changed: bool = True,
    ) -> Dict[str, Any]:
        """
        Ingest documents from folder:
        - Scans docs_folder for *.md files
        - Chunks, embeds, and stores in ChromaDB
        - Skips documents with matching hash
        - Deletes and re-indexes changed documents if force_reindex_changed=True
        """
        self.ensure_collections()
        
        md_files = sorted(glob.glob(os.path.join(docs_folder, "*.md")))
        json_files = sorted(glob.glob(os.path.join(docs_folder, "*.json")))
        logger.info(f"Found {len(md_files)} markdown files")
        
        if not md_files and not json_files:
            logger.warning(f"No files found in {docs_folder}")
            return {
                "docs_found": 0,
                "docs_ingested": 0,
                "docs_skipped": 0,
                "chunks_upserted": 0,
            }
        
        all_files = md_files + json_files

        docs_ingested = 0
        docs_skipped = 0
        chunks_upserted = 0
        
        for path in all_files:
            try:
                doc_id = self.doc_id_from_path(path)
                doc_hash = self.file_sha256(path)
                
                if self.doc_already_ingested(doc_id, doc_hash):
                    logger.info(f"Skipping already ingested document: {doc_id}")
                    docs_skipped += 1
                    continue
                
                # Delete old chunks if document changed
                if force_reindex_changed:
                    self.delete_existing_doc_chunks(doc_id)
                
                if path.endswith(".md"):
                    # Chunk the markdown document
                    chunks = chunks_from_file(path, procedure_aware=True)
                else:
                    # Chunk the JSON document (procedure_aware not applicable for JSON)
                    chunks = chunks_from_json_file(path)
                
                # Build records for ChromaDB
                ids: List[str] = []
                texts: List[str] = []
                metas: List[dict] = []
                
                for c in chunks:
                    c.doc_id = doc_id
                    
                    ids.append(c.chunk_id)
                    texts.append(c.text)
                    metas.append({
                        "doc_id": c.doc_id,
                        "section_path_str": " > ".join(c.section_path),
                        "section_path_json": json.dumps(c.section_path, ensure_ascii=False),
                        "kind": c.kind,
                        "step_no": int(c.step_no) if c.step_no is not None else -1,
                        "has_code": bool(c.has_code),
                        "commands_json": json.dumps(c.commands or [], ensure_ascii=False),
                        "header_level": int(c.header_level),
                        "start_line": int(c.start_line),
                        "end_line": int(c.end_line),
                    })
                
                # Embed and upsert chunks
                embeddings = self.model.encode(texts, normalize_embeddings=True).tolist()
                self.chunks_col.upsert(ids=ids, documents=texts, metadatas=metas, embeddings=embeddings)
                
                # Update document registry
                self.upsert_doc_registry(doc_id, doc_hash, chunk_count=len(ids))
                
                logger.info(f"Ingested document: {doc_id} with {len(ids)} chunks")
                docs_ingested += 1
                chunks_upserted += len(ids)
                
            except Exception as e:
                logger.error(f"Error ingesting document {path}: {e}")
                continue
        
        return {
            "docs_found": len(md_files),
            "docs_ingested": docs_ingested,
            "docs_skipped": docs_skipped,
            "chunks_upserted": chunks_upserted,
            "db_dir": self.db_dir,
            "embed_model": self.embed_model_name,
        }
