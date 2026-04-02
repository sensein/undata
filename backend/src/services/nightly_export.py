"""Nightly export scheduler — produces compressed archives and creates Release records."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from src.core.config import settings
from src.db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)

_EXPORT_INTERVAL_HOURS = 24


async def run_nightly_export():
    """Execute a single nightly export cycle."""
    from src.db.models import Release
    from src.services.export_service import export_full_registry

    version = datetime.now(timezone.utc).strftime("nightly-%Y%m%d-%H%M%S")

    async with AsyncSessionLocal() as session:
        try:
            result = await export_full_registry(session, settings.export_dir, version=version)

            release = Release(
                version=version,
                release_type="nightly",
                file_path=result["file_path"],
                file_size=result["file_size"],
                entity_counts=result["entity_counts"],
            )
            session.add(release)
            await session.commit()
            logger.info("Nightly export completed: %s (%d bytes)", version, result["file_size"])
        except Exception as e:
            logger.error("Nightly export failed: %s", e)


async def nightly_export_loop():
    """Background loop that runs nightly exports."""
    while True:
        await asyncio.sleep(_EXPORT_INTERVAL_HOURS * 3600)
        try:
            await run_nightly_export()
        except Exception as e:
            logger.error("Nightly export loop error: %s", e)
