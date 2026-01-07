import json
from pathlib import Path
import chromadb
from sentence_transformers import SentenceTransformer

DB_DIR = "chroma_db"
COLLECTION = "runbook_chunks"
EMBED_MODEL = "BAAI/bge-small-en-v1.5"


def load_jsonl(path: str):
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)


def main():
    client = chromadb.PersistentClient(path=DB_DIR)
    col = client.get_or_create_collection(name=COLLECTION)

    model = SentenceTransformer(EMBED_MODEL)

    ids, docs, metas = [], [], []
    for r in load_jsonl("out/chunks.jsonl"):
        ids.append(r["id"])
        docs.append(r["text"])
        metas.append(r["metadata"])

    # Embed + add
    embeddings = model.encode(docs, normalize_embeddings=True).tolist()
    col.add(ids=ids, documents=docs, metadatas=metas, embeddings=embeddings)

    print(f"Loaded {len(ids)} records into Chroma at ./{DB_DIR}")


if __name__ == "__main__":
    main()
