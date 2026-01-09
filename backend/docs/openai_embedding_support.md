# OpenAI Embedding Support Implementation

## Overview

Successfully implemented optional OpenAI API-based embeddings as an alternative to local HuggingFace embeddings, with automatic batch processing (max 32 chunks per API call) and enhanced document metadata tracking.

## Changes Made

### New Files Created

#### [embedding_service.py](file:///Users/mk/Desktop/workspace/ai-stuff/langgraph/ai-app/backend/app/services/embedding_service.py)

Created a new embedding service abstraction with:

- **`EmbeddingProvider` Protocol**: Defines interface with `embed_documents()` and `embed_query()` methods
- **`LocalEmbeddingProvider`**: Wrapper for existing SentenceTransformer embeddings (default behavior)
- **`OpenAIEmbeddingProvider`**: New provider for OpenAI API embeddings featuring:
  - Automatic batch processing with configurable batch size (default: 32 chunks)
  - SSO bearer token support for company authentication
  - Custom base URL support for internal company endpoints
  - Comprehensive error handling and logging
- **`get_embedding_provider()` factory**: Returns appropriate provider based on `use_openai_embeddings` flag

### Configuration Updates

#### [config.py](file:///Users/mk/Desktop/workspace/ai-stuff/langgraph/ai-app/backend/app/config.py)

Added OpenAI embedding configuration fields:

- `use_openai_embeddings: bool = False` - Feature flag to enable OpenAI embeddings
- `openai_embedding_model: str = "text-embedding-ada-002"` - Model name
- `openai_embedding_base_url: str | None = None` - Custom base URL for company API
- `openai_embedding_api_key: str | None = None` - API key authentication
- `openai_embedding_sso_token: str | None = None` - SSO bearer token authentication
- `openai_embedding_batch_size: int = 32` - Maximum chunks per API call

### Service Updates

#### [rag_service.py](file:///Users/mk/Desktop/workspace/ai-stuff/langgraph/ai-app/backend/app/services/rag_service.py)

Updated to use the new embedding abstraction:

- Replaced direct `SentenceTransformer` usage with `EmbeddingProvider` protocol
- Updated `initialize()` to use `get_embedding_provider()` factory
- Updated `add_document()` to use `embed_documents()` method
- Updated `search()` to use `embed_query()` method
- Now supports both local and OpenAI embeddings seamlessly

#### [document_service.py](file:///Users/mk/Desktop/workspace/ai-stuff/langgraph/ai-app/backend/app/services/document_service.py)

Enhanced metadata for user-uploaded documents:

- `file_type` - File extension (e.g., ".pdf", ".txt")
- `file_size` - File size in bytes
- `upload_timestamp` - ISO format timestamp of upload
- `content_hash` - MD5 hash for deduplication
- `chunk_index` and `total_chunks` - Chunk position tracking
- `upload_type: "user_upload"` - Distinguishes from auto-loaded docs

#### [document_loader.py](file:///Users/mk/Desktop/workspace/ai-stuff/langgraph/ai-app/backend/app/services/document_loader.py)

Enhanced metadata for auto-loaded documents:

- `file_type` - File extension
- `file_size` - File size in bytes
- `load_timestamp` - ISO format timestamp of loading
- `file_hash` - MD5 hash of file content
- `file_path` - Full path to the file
- `chunk_index` and `total_chunks` - Chunk position tracking
- `upload_type: "auto_load"` - Distinguishes from user uploads

### Example Configuration

#### [.env.embeddings.example](file:///Users/mk/Desktop/workspace/ai-stuff/langgraph/ai-app/backend/.env.embeddings.example)

Created example configuration file showing how to configure OpenAI embeddings.

## How to Use

### Using Local Embeddings (Default)

No configuration changes needed. The system will continue using local SentenceTransformer embeddings:

```bash
# In .env (or leave unset)
USE_OPENAI_EMBEDDINGS=false
```

### Using OpenAI Embeddings

Set the following in your `.env` file:

```bash
# Enable OpenAI embeddings
USE_OPENAI_EMBEDDINGS=true

# Configure the model
OPENAI_EMBEDDING_MODEL=text-embedding-ada-002

# For company internal API
OPENAI_EMBEDDING_BASE_URL=https://your-company-api.example.com/v1

# Authentication (choose one)
OPENAI_EMBEDDING_API_KEY=your-api-key
# OR
OPENAI_EMBEDDING_SSO_TOKEN=your-sso-bearer-token

# Optional: adjust batch size (default is 32)
OPENAI_EMBEDDING_BATCH_SIZE=32
```

## Key Features

### Automatic Batch Processing

When using OpenAI embeddings, documents are automatically batched to comply with API payload limits:

- Default batch size: 32 chunks per API call
- Configurable via `OPENAI_EMBEDDING_BATCH_SIZE`
- Automatic batching happens transparently in `embed_documents()`
- Progress logging shows batch processing: "Embedding batch 1/5 (32 texts)"

### Enhanced Metadata

All documents now include comprehensive metadata for better tracking and reference:

**User Uploads:**
- Source filename, file type, file size
- Upload timestamp
- Content hash for deduplication
- Chunk position (index and total)
- Upload type identifier

**Auto-loaded Documents:**
- Source filename, file type, file size
- Load timestamp
- File hash and full path
- Chunk position (index and total)
- Upload type identifier

This metadata is stored in ChromaDB and returned with search results, providing full context for each retrieved chunk.

## Verification

Import verification passed successfully:

```bash
python3 -c "from app.services.embedding_service import get_embedding_provider; print('Import successful')"
# Output: Import successful
```

## Backward Compatibility

The implementation is fully backward compatible:

- Default behavior unchanged (uses local embeddings)
- Existing documents continue to work
- Feature flag (`use_openai_embeddings`) controls behavior
- No breaking changes to existing APIs
