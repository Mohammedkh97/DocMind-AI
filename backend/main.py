"""
DocMind AI — Application Entry Point

Hybrid document intelligence system combining OCR, VLM, and LLM-based
structured extraction with deterministic compliance scoring for logistics
document processing and customs compliance automation.

Usage:
    uvicorn main:app --reload
    # or
    python main.py
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.config import get_settings
from core.logging import setup_logging, get_logger
from api.middleware import RequestTrackingMiddleware, create_exception_handlers
from api.routers import extract, compliance


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifecycle."""
    settings = get_settings()
    setup_logging()
    logger = get_logger("main")
    logger.info(
        "application_starting",
        app_name=settings.app_name,
        version=settings.app_version,
        primary_model=settings.primary_model,
        debug=settings.debug,
    )
    yield
    logger.info("application_shutting_down")


def create_app() -> FastAPI:
    """Application factory — creates and configures the FastAPI app."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Hybrid document intelligence API for logistics document extraction "
            "and customs compliance scoring. Combines VLM (Vision-Language Model) "
            "and OCR pipelines with deterministic rule-based compliance evaluation."
        ),
        lifespan=lifespan,
        exception_handlers=create_exception_handlers(),
    )

    # --- CORS ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Custom Middleware ---
    app.add_middleware(RequestTrackingMiddleware)

    # --- Routers ---
    app.include_router(extract.router, tags=["Extraction"])
    app.include_router(compliance.router, tags=["Compliance"])

    # --- Health Check ---
    @app.get("/health", tags=["System"])
    async def health_check():
        return {
            "status": "healthy",
            "version": settings.app_version,
            "model": settings.primary_model,
        }

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )
