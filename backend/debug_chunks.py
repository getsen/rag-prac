#!/usr/bin/env python3
"""Debug script to check what chunks are in the database."""

import json
from app.rag.rag_query import RAGQueryEngine

# Initialize the RAG engine
engine = RAGQueryEngine(db_dir="chroma_db", chunks_collection="runbook_chunks")

# Get the collection
col = engine.client.get_collection(name="runbook_chunks")

# Count total chunks
count = col.count()
print(f"Total chunks in database: {count}")

# Get all metadata to see what's indexed
result = col.get(limit=1000)
print(f"\nChunks related to 'onboarding':")
onboarding_chunks = []
for i, (doc, meta) in enumerate(zip(result['documents'], result['metadatas'])):
    if 'onboarding' in meta.get('source', '').lower():
        onboarding_chunks.append((i, doc, meta))
        print(f"\n{len(onboarding_chunks)}. Source: {meta.get('source')}")
        print(f"   Section: {meta.get('section')}")
        print(f"   Content: {doc[:200]}...")

print(f"\n\nTotal onboarding chunks: {len(onboarding_chunks)}")

print(f"\n\nChunks containing 'prerequisites' (case-insensitive):")
prereq_chunks = []
for i, (doc, meta) in enumerate(zip(result['documents'], result['metadatas'])):
    if 'prerequisite' in doc.lower():
        prereq_chunks.append((i, doc, meta))
        print(f"\n{len(prereq_chunks)}. Source: {meta.get('source')}")
        print(f"   Section: {meta.get('section')}")
        print(f"   Content: {doc[:200]}...")

print(f"\n\nTotal prerequisite chunks: {len(prereq_chunks)}")
