import json
import logging
from pathlib import Path
from typing import List, Dict, Any

import chromadb
from sentence_transformers import SentenceTransformer

from app.config import get_settings

logger = logging.getLogger(__name__)


class ChromaLoader:
    """Loads and manages JSONL data into ChromaDB with embeddings."""
    
    def __init__(
        self,
        db_dir: str = None,
        collection: str = None,
        embed_model: str = None,
    ):
        """Initialize the ChromaDB loader with configuration."""
        settings = get_settings()
        
        # Use provided values or fall back to settings
        self.db_dir = db_dir or settings.chroma_db_dir
        self.collection_name = collection or settings.chroma_chunks_collection
        self.embed_model_name = embed_model or settings.chroma_embed_model
        
        self.client = chromadb.PersistentClient(path=self.db_dir)
        self.model = SentenceTransformer(self.embed_model_name)
        self.col = None
    
    @staticmethod
    def load_jsonl(path: str) -> Any:
        """Load and yield records from a JSONL file."""
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    yield json.loads(line)
    
    def get_collection(self):
        """Get or create the ChromaDB collection."""
        if self.col is None:
            self.col = self.client.get_or_create_collection(name=self.collection_name)
        return self.col
    
    def load_from_jsonl(self, jsonl_path: str) -> Dict[str, Any]:
        """
        Load records from JSONL file and add to ChromaDB with embeddings.
        
        Args:
            jsonl_path: Path to JSONL file
            
        Returns:
            Dictionary with loading statistics
        """
        col = self.get_collection()
        
        ids: List[str] = []
        docs: List[str] = []
        metas: List[dict] = []
        
        # Load records from JSONL
        for r in self.load_jsonl(jsonl_path):
            ids.append(r["id"])
            docs.append(r["text"])
            metas.append(r["metadata"])
        
        if not ids:
            logger.warning(f"No records found in {jsonl_path}")
            return {
                "status": "success",
                "records_loaded": 0,
                "db_dir": self.db_dir,
                "collection": self.collection_name,
            }
        
        # Embed + add to ChromaDB
        logger.info(f"Embedding {len(docs)} documents...")
        embeddings = self.model.encode(docs, normalize_embeddings=True).tolist()
        
        col.add(ids=ids, documents=docs, metadatas=metas, embeddings=embeddings)
        
        logger.info(f"Loaded {len(ids)} records into Chroma at {self.db_dir}/{self.collection_name}")
        
        return {
            "status": "success",
            "records_loaded": len(ids),
            "db_dir": self.db_dir,
            "collection": self.collection_name,
            "embed_model": self.embed_model_name,
        }


# Legacy function for backward compatibility
def main():
    """Legacy main function for backward compatibility."""
    loader = ChromaLoader()
    stats = loader.load_from_jsonl("out/chunks.jsonl")
    print(f"Loading complete: {stats}")


if __name__ == "__main__":
    main()
