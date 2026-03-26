"""FastAPI application — GraphQL API for the undata registry."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager

import strawberry
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.core.config import settings
from src.core.logging import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create database tables on startup."""
    from src.db import models  # noqa: F401 — registers models with Base
    from src.db.session import Base, engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created")
    yield
    await engine.dispose()


# Placeholder schema — Phase 5 will wire the full resolvers
@strawberry.type
class Query:
    @strawberry.field
    def status(self) -> str:
        return "ok"

    @strawberry.field
    async def element_count(self) -> int:
        from src.db.session import AsyncSessionLocal
        from src.storage.database_backend import DatabaseBackend

        async with AsyncSessionLocal() as session:
            backend = DatabaseBackend(session)
            return await backend.entities.count("elements")


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def import_registry(self, registry_path: str) -> str:
        from src.db.session import AsyncSessionLocal
        from src.services.import_service import import_registry

        async with AsyncSessionLocal() as session:
            stats = await import_registry(session, registry_path)
            await session.commit()
            return str(stats)


schema = strawberry.Schema(query=Query, mutation=Mutation)

app = FastAPI(title="undata API", lifespan=lifespan)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        t0 = time.time()
        response = await call_next(request)
        duration_ms = (time.time() - t0) * 1000
        logger.info(
            "request",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round(duration_ms, 1),
            },
        )
        return response


app.add_middleware(RequestLoggingMiddleware)


# Error handlers
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error("unhandled_error", extra={"error": str(exc), "path": request.url.path})
    return JSONResponse(status_code=500, content={"error": "Internal server error"})


# Health endpoint
@app.get("/health")
async def health():
    from sqlalchemy import text as sa_text

    from src.db.session import engine

    try:
        async with engine.connect() as conn:
            await conn.execute(sa_text("SELECT 1"))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {e}"

    return {"status": "ok", "database": db_status}


# GraphQL mount
from strawberry.fastapi import GraphQLRouter

graphql_app = GraphQLRouter(schema)
app.include_router(graphql_app, prefix="/graphql")
