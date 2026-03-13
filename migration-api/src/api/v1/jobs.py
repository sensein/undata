"""Job polling endpoints — /jobs."""

from __future__ import annotations

import logging

from celery.result import AsyncResult
from fastapi import APIRouter

from src.models import JobStatus
from src.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/{job_id}", response_model=JobStatus)
async def get_job(job_id: str) -> JobStatus:
    """Poll the status of an async job (schema construction or batch migration)."""
    result = AsyncResult(job_id, app=celery_app)

    state = result.state  # PENDING, STARTED, PROGRESS, SUCCESS, FAILURE, REVOKED
    progress = 0
    job_result = None
    error = None
    completed_at = None

    if state == "PENDING":
        status = "pending"
    elif state in ("STARTED", "PROGRESS"):
        status = "running"
        if result.info and isinstance(result.info, dict):
            progress = result.info.get("progress", 0)
    elif state == "SUCCESS":
        status = "done"
        progress = 100
        job_result = result.result if isinstance(result.result, dict) else {"value": result.result}
    elif state == "FAILURE":
        status = "failed"
        error = str(result.result)
    else:
        status = state.lower()

    return JobStatus(
        job_id=job_id,
        job_type="async",
        status=status,
        progress=progress,
        result=job_result,
        error=error,
        created_at="",
        completed_at=completed_at,
        poll_url=f"/jobs/{job_id}",
    )
