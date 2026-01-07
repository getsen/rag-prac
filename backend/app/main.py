import logging
from contextlib import asynccontextmanager
import glob
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.ingest import ingest_docs_on_start
from app.chat import chat

from app.config import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    settings = get_settings()

    try:
        stats = ingest_docs_on_start(docs_folder="docs", force_reindex_changed=True)
        print("Startup ingestion:", stats)
       
    except Exception as e:
        logger.error(f"Failed to initialize chunking utilities: {e}")
    # Startup
    logger.info(f"Starting {settings.app_name}...")
    yield

def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    
    app = FastAPI(
        title=settings.app_name,
        description="AI Chat API with ollama, LangGraph, LangChain, and ChromaDB",
        version="1.0.0",
        lifespan=lifespan,
    )
    
    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_origins=[
            "http://localhost:5173",  # Vite default
            "http://127.0.0.1:5173",
        ],
    )

    app.include_router(chat.router)
    
    return app


# Create application instance
app = create_app()

