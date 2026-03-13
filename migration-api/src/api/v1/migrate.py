"""Migration execution endpoints — /migrate."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from src.models import MigrateRequest, MigrateResponse, RecordResult
from src.services.backend_client import BackendClient, get_backend_client
from src.services.pathway_executor import PathwayExecutor
from src.tasks.batch_migrate import batch_migrate_task

logger = logging.getLogger(__name__)
router = APIRouter()

_ASYNC_THRESHOLD = 100  # record count above which we go async


@router.post("", status_code=200)
async def migrate_records(
    request: MigrateRequest,
    client: BackendClient = Depends(get_backend_client),
):
    """Execute migration for a batch of records using a registered pathway.

    Returns 200 (sync) for ≤100 records, or 202 (async) for >100.
    Returns 409 if the pathway status is not 'active'.
    """
    pathway_id = str(request.pathway_id)

    # Fetch pathway and check status
    try:
        pathway = await client.get_pathway(pathway_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Pathway not found") from exc

    if pathway.get("status") != "active":
        raise HTTPException(
            status_code=409,
            detail={
                "message": f"Pathway is not active (status={pathway.get('status')})",
                "pathway_id": pathway_id,
            },
        )

    records = request.records

    if len(records) > _ASYNC_THRESHOLD:
        # Dispatch async Celery task
        task = batch_migrate_task.delay({"pathway_id": pathway_id, "records": records})
        return JSONResponse(
            status_code=202,
            content={
                "job_id": task.id,
                "status": "pending",
                "poll_url": f"/jobs/{task.id}",
            },
        )

    # Synchronous path — per-record failure isolation
    executor = PathwayExecutor(client)
    results: list[RecordResult] = []

    for record in records:
        try:
            report = await executor.execute(pathway_id=pathway_id, input_record=record)
            results.append(
                RecordResult(
                    input_record=record,
                    output_record={},  # output_record is in the report, not on context here
                    status=report.overall_status,
                    report={
                        "steps_applied": [
                            {
                                "position": s.position,
                                "status": s.status,
                                "error_message": s.error_message,
                            }
                            for s in report.steps_applied
                        ],
                        "passthrough_fields": report.passthrough_fields,
                        "duration_ms": report.duration_ms,
                    },
                )
            )
        except Exception as exc:
            logger.exception("Per-record execution error for record: %r", record)
            results.append(
                RecordResult(
                    input_record=record,
                    output_record=None,
                    status="FAIL",
                    report={"error": str(exc)},
                )
            )

    succeeded = sum(1 for r in results if r.status in ("PASS", "PARTIAL"))
    failed = len(results) - succeeded

    return MigrateResponse(
        pathway_id=pathway_id,
        total=len(results),
        succeeded=succeeded,
        failed=failed,
        results=results,
    )
