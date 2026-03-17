"""FastAPI application entry point for the Schema Backend service."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.logging import get_logger
from src.db.session import AsyncSessionLocal

logger = get_logger(__name__)


async def _seed_undata_source(session: AsyncSession) -> None:
    """Idempotently insert the canonical undata SchemaSource row.

    Uses ON CONFLICT (name) DO NOTHING so it is safe to call on every startup.
    """
    await session.execute(
        text(
            """
            INSERT INTO schema_source (id, name, format, content_hash, ingested_at, is_active, version_num)
            VALUES (gen_random_uuid(), 'undata', 'canonical', 'seeded', now(), true, 1)
            ON CONFLICT (name) DO NOTHING
            """
        )
    )
    logger.info("undata canonical source seeding complete (idempotent)")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler.

    On startup:
    1. Run Alembic migrations to head.
    2. Seed the canonical undata SchemaSource (idempotent).
    """
    # 1. Migrations are run by the entrypoint script before uvicorn starts.
    #    Nothing to do here — log confirmation only.
    logger.info("alembic.upgrade.complete")

    # 2. Initialize UnitResolutionService (loads QUDT TTL ~100ms)
    from src.services.units import UnitResolutionService

    app.state.unit_service = UnitResolutionService(ttl_path=settings.qudt_ttl_path)
    logger.info(
        "unit_service.initialized",
        extra={"units": len(app.state.unit_service.list_known())},
    )

    # 3. Seed canonical undata source
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await _seed_undata_source(session)

    yield
    # Shutdown — nothing to clean up


app = FastAPI(
    title="Schema Backend",
    version="2026.03.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Request logging middleware
# ---------------------------------------------------------------------------


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    duration_ms = round((time.monotonic() - start) * 1000, 2)
    logger.info(
        "http.request",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    return response


# ---------------------------------------------------------------------------
# Health endpoint
# ---------------------------------------------------------------------------


@app.get("/health", tags=["ops"])
async def health() -> dict:
    return {"status": "ok", "version": "2026.03.0"}


# ---------------------------------------------------------------------------
# API routers
# ---------------------------------------------------------------------------

# Phase 3 (US4): Auth, Users, Tokens
from src.api.v1.auth import router as auth_router  # noqa: E402
from src.api.v1.tokens import router as tokens_router  # noqa: E402
from src.api.v1.users import router as users_router  # noqa: E402

app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(tokens_router, prefix="/api/v1")

# Phase 4 (US1): Sources, Elements
from src.api.v1.elements import router as elements_router  # noqa: E402
from src.api.v1.sources import router as sources_router  # noqa: E402

app.include_router(sources_router, prefix="/api/v1")
app.include_router(elements_router, prefix="/api/v1")

# Phase 5 (US5): Schemas
from src.api.v1.schemas import router as schemas_router  # noqa: E402

app.include_router(schemas_router, prefix="/api/v1")

# Phase 6 (US2): Mappings, Aliases
from src.api.v1.aliases import router as aliases_router  # noqa: E402
from src.api.v1.mappings import router as mappings_router  # noqa: E402

app.include_router(mappings_router, prefix="/api/v1")
app.include_router(aliases_router, prefix="/api/v1")

# Phase 7 (US3): Audit
from src.api.v1.audit import router as audit_router  # noqa: E402

app.include_router(audit_router, prefix="/api/v1")

# Phase 10 (US7): Units
from src.api.v1.units import router as units_router  # noqa: E402

app.include_router(units_router, prefix="/api/v1")

# 004-migration-api: Migration Pathways
from src.api.v1.pathways import router as pathways_router  # noqa: E402

app.include_router(pathways_router, prefix="/api/v1")

# 017: V2 content-addressed API
from src.routes.elements_v2 import router as elements_v2_router  # noqa: E402
from src.routes.mappings_v2 import router as mappings_v2_router  # noqa: E402
from src.routes.schemas_v2 import router as schemas_v2_router  # noqa: E402
from src.routes.values_v2 import router as values_v2_router  # noqa: E402

app.include_router(elements_v2_router)
app.include_router(values_v2_router)
app.include_router(schemas_v2_router)
app.include_router(mappings_v2_router)
