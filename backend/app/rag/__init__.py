"""rag package - RAG and Adaptive RAG implementations."""

from app.rag.rag_query import RAGQueryEngine, retrieve_chunks, build_context

# Lazy imports for adaptive RAG to avoid circular dependencies
def _get_adaptive_rag_classes():
    from app.rag.adaptive_rag import AdaptiveRAG, get_adaptive_rag
    return AdaptiveRAG, get_adaptive_rag

__all__ = [
    "RAGQueryEngine",
    "retrieve_chunks",
    "build_context",
]
