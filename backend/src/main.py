"""FastAPI application — GraphQL API for the undata registry."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from src.core.logging import get_logger
from src.db.session import Base, engine

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Create database tables on startup (no migrations needed)."""
    from src.models.db import (  # noqa: F401 — register models
        Contribution,
        CurationFlag,
        Element,
        RunSummary,
        Schema,
        UserProfile,
        Value,
        ValueSet,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables ready")
    yield
    await engine.dispose()


app = FastAPI(
    title="undata Registry API",
    version="2026.03.0",
    lifespan=lifespan,
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging(request: Request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    duration = round((time.monotonic() - start) * 1000, 2)
    logger.info(
        "http.request",
        extra={"method": request.method, "path": request.url.path,
               "status": response.status_code, "ms": duration},
    )
    return response


@app.get("/health")
async def health():
    return {"status": "ok", "version": "2026.03.0"}


# GraphQL API
from src.graphql.schema import graphql_app  # noqa: E402

app.include_router(graphql_app, prefix="/graphql")
