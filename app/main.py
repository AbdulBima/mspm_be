"""
Sprint Ops — API
===================
Application factory + entrypoint. Run locally:

    uvicorn app.main:app --reload --port 8000

or, from the repo root, `uvicorn main:app --reload` (see the thin root
main.py).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.indexes import ensure_indexes
from app.db.session import ping

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up (env=%s)", settings.env)
    try:
        await ensure_indexes()
    except Exception:
        logger.exception("Failed to create indexes")
        raise
    logger.info("Startup complete")
    yield
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Sprint Ops API",
        lifespan=lifespan,
        docs_url="/docs" if settings.is_dev else None,
        redoc_url="/redoc" if settings.is_dev else None,
        openapi_url="/openapi.json" if settings.is_dev else None,
    )

    if not settings.cors_origins and not settings.is_dev:
        logger.warning(
            "ALLOWED_ORIGINS is empty outside development — all cross-origin "
            "requests will be rejected until it's set."
        )


    origins = [
        "https://mspmfe.mymently.com",
        "http://localhost:3000",
        "http://localhost:3012",
    ]

    # allow_origins=["*"] combined with allow_credentials=True violates the
    # CORS spec (browsers reject it outright); allow_origin_regex is the
    # correct way to allow "anything" only in development.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_origin_regex=".*" if settings.is_dev else None,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    @app.get("/health", include_in_schema=False)
    async def health() -> JSONResponse:
        # Returns 503 (not always 200) when the DB is unreachable, so a load
        # balancer or orchestrator's readiness probe actually catches it.
        try:
            await ping()
            return JSONResponse({"status": "ok", "db": "connected", "env": settings.env})
        except Exception:
            logger.exception("Health check failed")
            return JSONResponse({"status": "degraded", "db": "unreachable"}, status_code=503)

    @app.get("/", include_in_schema=False)
    async def root() -> dict:
        return {"status": "ok", "service": "sprint-ops"}

    return app


app = create_app()
