from typing import Dict, Any
from app.ingest.ingester import DocumentIngester

logger_instance = None


def ingest_docs_on_start(
    docs_folder: str = "docs",
    force_reindex_changed: bool = True,
) -> Dict[str, Any]:
    """Legacy function wrapper for backward compatibility."""
    ingester = DocumentIngester()
    return ingester.ingest_docs(docs_folder, force_reindex_changed)


# Export public API
__all__ = ["DocumentIngester", "ingest_docs_on_start"]
