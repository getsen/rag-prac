import chromadb
import json
import logging
from typing import List, Dict, Any, Optional

from sentence_transformers import SentenceTransformer

from app.config import get_settings

logger = logging.getLogger(__name__)


class ChromaQueryEngine:
    """Query and retrieve documents from ChromaDB with semantic search."""
    
    def __init__(
        self,
        db_dir: str = None,
        collection: str = None,
        embed_model: str = None,
    ):
        """Initialize the ChromaDB query engine."""
        settings = get_settings()
        
        # Use provided values or fall back to settings
        self.db_dir = db_dir or settings.chroma_db_dir
        self.collection_name = collection or settings.chroma_chunks_collection
        self.embed_model_name = embed_model or settings.chroma_embed_model
        
        self.client = chromadb.PersistentClient(path=self.db_dir)
        self.model = SentenceTransformer(self.embed_model_name)
        self.col = None
    
    def get_collection(self):
        """Get the ChromaDB collection."""
        if self.col is None:
            self.col = self.client.get_collection(name=self.collection_name)
        return self.col
    
    def query(
        self,
        query_text: str,
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
        include_metadata: bool = True,
        include_distances: bool = True,
        include_documents: bool = True,
    ) -> Dict[str, Any]:
        """
        Query the ChromaDB collection with semantic search.
        
        Args:
            query_text: The search query
            n_results: Number of results to return
            where: Optional metadata filter (e.g., {"kind": "step", "has_code": True})
            include_metadata: Include metadata in results
            include_distances: Include distance scores
            include_documents: Include document text
            
        Returns:
            Dictionary with results and metadata
        """
        col = self.get_collection()
        
        # Embed the query
        query_embedding = self.model.encode([query_text], normalize_embeddings=True).tolist()
        
        # Build include list
        include_list = []
        if include_metadata:
            include_list.append("metadatas")
        if include_distances:
            include_list.append("distances")
        if include_documents:
            include_list.append("documents")
        
        # Query ChromaDB
        results = col.query(
            query_embeddings=query_embedding,
            n_results=n_results,
            where=where,
            include=include_list,
        )
        
        return results
    
    def query_with_filtering(
        self,
        query_text: str,
        kind: Optional[str] = None,
        has_code: Optional[bool] = None,
        n_results: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Convenience method to query with common filters.
        
        Args:
            query_text: The search query
            kind: Filter by kind ("section", "narrative", "step")
            has_code: Filter by has_code (True/False)
            n_results: Number of results to return
            
        Returns:
            List of sorted results
        """
        # Build where filter
        where = {}
        if kind is not None:
            where["kind"] = kind
        if has_code is not None:
            where["has_code"] = has_code
        
        where_filter = where if where else None
        
        # Query
        results = self.query(query_text, n_results=n_results, where=where_filter)
        
        # Process and sort results
        rows = []
        if results["metadatas"] and results["metadatas"][0]:
            for md, dist, doc in zip(
                results["metadatas"][0],
                results["distances"][0] if results.get("distances") else [],
                results["documents"][0] if results.get("documents") else [],
            ):
                rows.append({
                    "step_no": md.get("step_no", 10**9),
                    "distance": dist,
                    "metadata": md,
                    "document": doc,
                })
        
        # Sort by step_no
        rows.sort(key=lambda x: x["step_no"])
        
        logger.info(f"Found {len(rows)} results for query: {query_text}")
        return rows
    
    def print_results(self, rows: List[Dict[str, Any]]) -> None:
        """Pretty-print query results."""
        print("\nTop matching steps (ordered):")
        for row in rows:
            print("\n------------------------------")
            print(f"step_no  : {row['step_no']} | distance: {row['distance']:.4f}")
            section_path = json.loads(row["metadata"].get("section_path_json", "[]"))
            print(f"path     : {section_path}")
            print("commands :")
            for cmd in json.loads(row["metadata"].get("commands_json", "[]")):
                print(f"  - {cmd}")


# Legacy function for backward compatibility
def main():
    """Legacy main function for backward compatibility."""
    engine = ChromaQueryEngine()
    
    query_text = "install onboarding agent on linux commands in order"
    
    rows = engine.query_with_filtering(
        query_text,
        kind="step",
        has_code=True,
        n_results=10,
    )
    
    engine.print_results(rows)


if __name__ == "__main__":
    main()
