import chromadb
from sentence_transformers import SentenceTransformer
import json

DB_DIR = "chroma_db"
COLLECTION = "runbook_chunks"
EMBED_MODEL = "BAAI/bge-small-en-v1.5"


def main():
    client = chromadb.PersistentClient(path=DB_DIR)
    col = client.get_collection(name=COLLECTION)

    model = SentenceTransformer(EMBED_MODEL)

    query = "install onboarding agent on linux commands in order"
    qemb = model.encode([query], normalize_embeddings=True).tolist()

    # Chroma metadata filter (exact match)
    where = {"kind": "step", "has_code": True}

    res = col.query(
        query_embeddings=qemb,
        n_results=10,
        where=where,
        include=["metadatas", "distances", "documents"],
    )

    # Chroma returns lists-of-lists
    metadatas = res["metadatas"][0]
    distances = res["distances"][0]

    # Sort by step_no for correct sequence
    rows = []
    for md, dist in zip(metadatas, distances):
        rows.append((md.get("step_no", 10**9), dist, md))
    rows.sort(key=lambda x: x[0])

    print("\nTop matching steps (ordered):")
    for step_no, dist, md in rows:
        print("\n------------------------------")
        print(f"step_no : {step_no} | distance: {dist:.4f}")
        print(f"path    : {json.loads(md.get("section_path_json", "[]"))}")
        print("commands:")
        for cmd in (json.loads(md.get("commands_json", "[]"))):
            print(f"  - {cmd}")


if __name__ == "__main__":
    main()
