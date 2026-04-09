"""FastAPI application factory for the Daily Summarizer API."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers.config import router as config_router
from src.api.routers.entities import router as entities_router
from src.api.routers.merge_proposals import router as merge_proposals_router
from src.api.routers.pipeline import router as pipeline_router
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
    application.include_router(entities_router, prefix="/api/v1")
    application.include_router(merge_proposals_router, prefix="/api/v1")
    application.include_router(pipeline_router, prefix="/api/v1")
    application.include_router(config_router, prefix="/api/v1")

    @application.on_event("startup")
    async def _startup_cleanup() -> None:
        """Clean up orphaned pipeline runs from previous server instances."""
        import logging

        from src.api.services.pipeline_runner import cleanup_orphaned_runs

        logger = logging.getLogger(__name__)
        try:
            cleaned = cleanup_orphaned_runs()
            if cleaned:
                logger.info("Cleaned up %d orphaned pipeline run(s)", cleaned)
        except Exception as e:
            logger.warning("Orphaned run cleanup failed: %s", e)

    return application


app = create_app()
