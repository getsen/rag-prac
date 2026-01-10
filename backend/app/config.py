"""Configuration settings for the application."""
from typing import Optional, List
from pydantic import ConfigDict
from pydantic_settings import BaseSettings
from pathlib import Path
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings."""
    model_config = ConfigDict(env_file=".env", extra="ignore")
    
    # App settings
    app_name: str = "AI Chat API"
    debug: bool = True
    verbose_llm: bool = False  # Control llama.cpp verbose output (ggml, metal, etc.)
    
    # Provider selection
    provider_type: str = "llamacpp"  # Options: llamacpp, ollama, huggingface, openai
    
    # LLM settings (common across providers)
    temperature: float = 0.7
    max_tokens: int = 512
    
    # OpenAI-specific settings (for company internal GPT-OSS models)
    openai_base_url: str = "https://api.openai.com/v1"  # Override for company internal endpoint
    openai_model: str = "gpt-3.5-turbo"  # Model name (e.g., "gpt-oss-20b" for internal)
    openai_api_key: Optional[str] = None  # API key (optional if using SSO token)
    openai_sso_token: Optional[str] = None  # SSO bearer token for company authentication
    
    # LlamaCPP-specific settings
    model_path: str = str(Path(__file__).parent.parent / "models" / "model.gguf")
    n_ctx: int = 4096  # Context window size
    n_gpu_layers: int = 0  # Set to -1 for full GPU offload, 0 for CPU only
    n_threads: int = 4
    
    # Ollama-specific settings
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama2"  # Default model name
    
    # HuggingFace-specific settings
    hf_model_name: str = "gpt2"  # HuggingFace model identifier
    hf_api_token: Optional[str] = None  # Optional API token for private models
    
    # ChromaDB settings
    data_dir: str = str(Path(__file__).parent.parent / "data")
    chroma_persist_dir: str = str(Path(__file__).parent.parent / "data" / "chroma")
    collection_name: str = "documents"
    
    # Embedding settings
    embedding_model: str = "all-MiniLM-L6-v2"
    
    # ChromaDB embedding settings
    chroma_db_dir: str = "chroma_db"
    chroma_chunks_collection: str = "runbook_chunks"
    chroma_docs_collection: str = "runbook_docs"
    chroma_embed_model: str = "BAAI/bge-small-en-v1.5"  # Embedding model for ChromaDB
    
    # OpenAI Embedding settings (optional, for company internal embedding models)
    use_openai_embeddings: bool = False  # Flag to enable OpenAI API embeddings
    openai_embedding_model: str = "text-embedding-ada-002"  # OpenAI embedding model name
    openai_embedding_base_url: Optional[str] = None  # Custom base URL for company internal API
    openai_embedding_api_key: Optional[str] = None  # API key for OpenAI embeddings
    openai_embedding_sso_token: Optional[str] = None  # SSO bearer token for authentication
    openai_embedding_batch_size: int = 32  # Maximum chunks per API call
    
    # OCR settings
    use_ocr: bool = True  # Enable/disable OCR for scanned PDFs
    extract_images: bool = True  # Enable/disable image extraction from PDFs
    ocr_language: str = "eng"  # Tesseract language code
    ocr_dpi: int = 300  # DPI for PDF to image conversion
    
    # CORS settings
    cors_origins: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance for easy access
settings = get_settings()
