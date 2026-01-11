#!/usr/bin/env python3
"""Force re-index documents to apply chunk enrichment changes."""

import sys
sys.path.insert(0, '/Users/senthilkumar/git/rag-prac/backend')

from app.ingest.ingester import DocumentIngester
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize ingester
ingester = DocumentIngester(
    db_dir="chroma_db",
    chunks_collection="runbook_chunks",
    docs_collection="runbook_docs",
    embed_model="BAAI/bge-large-en-v1.5"
)

# Force re-index
logger.info("Starting force re-index of all documents...")
result = ingester.ingest_docs(docs_folder="docs", force_reindex_changed=True)

logger.info(f"Re-index results: {result}")
print(f"\n✓ Re-indexing complete!")
print(f"  - Docs found: {result['docs_found']}")
print(f"  - Docs ingested: {result['docs_ingested']}")
print(f"  - Chunks upserted: {result['chunks_upserted']}")
