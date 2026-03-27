"""FastAPI application — GraphQL API for the undata registry."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager

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


# Auth endpoint — token validity check (FR-012)
@app.get("/auth/me")
async def auth_me(request: Request):
    from src.auth.dependencies import get_current_user

    user = await get_current_user(request)
    if user is None:
        return JSONResponse(status_code=401, content={"error": "Not authenticated"})
    return {
        "sub": user.get("sub"),
        "email": user.get("email"),
        "name": user.get("name"),
        "roles": user.get("realm_access", {}).get("roles", []),
    }


# GraphQL mount
from strawberry.fastapi import GraphQLRouter

from src.graphql.schema import schema

graphql_app = GraphQLRouter(schema)
app.include_router(graphql_app, prefix="/graphql")
