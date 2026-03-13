"""Migration API — FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pythonjsonlogger import jsonlogger

from src.api.v1 import diff, jobs, migrate, pathways, schemas

# Structured JSON logging
handler = logging.StreamHandler()
handler.setFormatter(jsonlogger.JsonFormatter("%(asctime)s %(name)s %(levelname)s %(message)s"))
logging.root.handlers = [handler]
logging.root.setLevel(logging.INFO)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("migration-api starting up")
    yield
    logger.info("migration-api shutting down")


app = FastAPI(
    title="Migration API",
    description="Dynamic schema construction and migration pathway execution",
    version="2026.03.1",
    lifespan=lifespan,
)

app.include_router(schemas.router, prefix="/schemas", tags=["schemas"])
app.include_router(pathways.router, prefix="/pathways", tags=["pathways"])
app.include_router(migrate.router, prefix="/migrate", tags=["migrate"])
app.include_router(diff.router, prefix="/diff", tags=["diff"])
app.include_router(jobs.router, prefix="/jobs", tags=["jobs"])


@app.get("/health", tags=["health"])
async def health() -> dict:
    return {"status": "ok", "service": "migration-api"}
