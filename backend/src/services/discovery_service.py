"""Background discovery service — schedules repository scans and auto-ingests approved sources.

Runs on startup and daily thereafter. Polls OpenNeuro and DANDI APIs for new
datasets. Pre-approved sources auto-ingest; unknown sources queue for review.
"""

from __future__ import annotations

import asyncio
import logging
import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

SCAN_INTERVAL_HOURS = int(os.environ.get("DISCOVERY_SCAN_INTERVAL_HOURS", "24"))

# Pre-approved sources with known adapters — auto-ingest without curator approval
APPROVED_SOURCES = {
    "openneuro": "bids",
    "dandi": "dandi",
}


async def run_discovery_scan(session: AsyncSession) -> dict:
    """Scan all approved repositories for new datasets and queue ingestion jobs."""
    from src.db.models import IngestionJob

    try:
        from undata_library.discovery import scan_all_repositories
    except ImportError:
        logger.warning("undata_library.discovery not available")
        return {"error": "library not available"}

    # Get last scan timestamp
    last_job = (
        await session.execute(
            select(IngestionJob).order_by(IngestionJob.created_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    since = str(last_job.created_at) if last_job else None

    # Scan repositories
    datasets = scan_all_repositories(since=since, limit=50)
    logger.info("Discovery scan found %d new datasets", len(datasets))

    queued = 0
    for ds in datasets:
        # Check if already queued
        existing = (
            await session.execute(
                select(IngestionJob).where(IngestionJob.repository_url == ds["url"])
            )
        ).scalar_one_or_none()
        if existing:
            continue

        # Determine if auto-approved
        source = ds.get("source", "")
        adapter = APPROVED_SOURCES.get(source)
        auto = adapter is not None

        job = IngestionJob(
            repository_url=ds["url"],
            adapter_type=adapter or ds.get("adapter", "unknown"),
            status="approved" if auto else "pending",
            auto_approved=auto,
        )
        session.add(job)
        queued += 1

    if queued > 0:
        await session.flush()
        logger.info(
            "Queued %d new ingestion jobs (%d auto-approved)",
            queued,
            sum(1 for d in datasets if d.get("source") in APPROVED_SOURCES),
        )

    return {"scanned": len(datasets), "queued": queued}


async def discovery_loop():
    """Background loop that runs discovery scans on schedule."""
    from src.db.session import AsyncSessionLocal

    logger.info("Discovery service started (interval: %dh)", SCAN_INTERVAL_HOURS)

    while True:
        try:
            async with AsyncSessionLocal() as session:
                result = await run_discovery_scan(session)
                await session.commit()
                logger.info("Discovery scan complete: %s", result)
        except Exception as exc:
            logger.warning("Discovery scan failed: %s", exc)

        await asyncio.sleep(SCAN_INTERVAL_HOURS * 3600)
