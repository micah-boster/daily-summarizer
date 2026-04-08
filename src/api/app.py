"""FastAPI application factory for the Daily Summarizer API."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers.summaries import router as summaries_router


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    application = FastAPI(
        title="Daily Summarizer API",
        version="0.1.0",
        docs_url="/docs",
    )

    # CORS must be the first middleware added
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000"],
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type"],
        allow_credentials=False,
    )

    application.include_router(summaries_router, prefix="/api/v1")

    return application


app = create_app()
