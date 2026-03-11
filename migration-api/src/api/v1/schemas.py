"""Schema construction endpoints — /schemas."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from src.models import (
    SchemaConstructionRequest,
    SchemaConstructionResponse,
)
from src.services.backend_client import BackendClient, get_backend_client
from src.services.schema_builder import ConflictError, SchemaBuilder
from src.tasks.build_schema import build_schema_task

logger = logging.getLogger(__name__)
router = APIRouter()

_ASYNC_THRESHOLD = 50  # element count above which we go async


def _total_elements(request: SchemaConstructionRequest) -> int:
    return sum(len(cls.element_ids) for cls in request.classes)


@router.post("", status_code=200)
async def create_schema(
    request: SchemaConstructionRequest,
    client: BackendClient = Depends(get_backend_client),
):
    """Construct a dynamic LinkML schema from stored element IDs.

    Returns 200 (sync) for ≤50 elements, or 202 (async) for >50.
    """
    total = _total_elements(request)

    if total > _ASYNC_THRESHOLD:
        # Dispatch async Celery task
        task = build_schema_task.delay(request.model_dump(mode="json"))
        job_id = task.id
        return JSONResponse(
            status_code=202,
            content={
                "job_id": job_id,
                "status": "pending",
                "poll_url": f"/jobs/{job_id}",
            },
        )

    # Synchronous path
    builder = SchemaBuilder(client)
    try:
        result = await builder.build(
            name=request.name,
            version=request.version,
            classes=[
                {"name": cls.name, "element_ids": [str(eid) for eid in cls.element_ids]}
                for cls in request.classes
            ],
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail={"message": str(exc), "unknown_ids": _extract_unknown_ids(str(exc))},
        ) from exc
    except ConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "message": str(exc),
                "conflicting_names": exc.conflicting_names,
            },
        ) from exc

    schema_id = None
    if request.save:
        try:
            saved = await client.create_schema(
                {
                    "name": result.name,
                    "version": result.version,
                    "linkml_yaml": result.linkml_yaml,
                    "classes": [
                        {
                            "name": cls.name,
                            "element_ids": [str(eid) for eid in cls.element_ids],
                        }
                        for cls in request.classes
                    ],
                    "status": "published",
                }
            )
            schema_id = saved.get("id")
        except Exception:
            logger.exception("Failed to save schema to backend")

    return SchemaConstructionResponse(
        schema_id=schema_id,
        name=result.name,
        version=result.version,
        linkml_yaml=result.linkml_yaml,
        linkml_jsonld=result.linkml_jsonld,
        status="published" if request.save else "draft",
    )


@router.get("/{schema_id}")
async def get_schema(
    schema_id: str,
    client: BackendClient = Depends(get_backend_client),
):
    """Fetch a stored DynamicSchema by ID."""
    try:
        schema = await client.get_schema(schema_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Schema not found") from exc
    return schema


@router.get("/{schema_id}/versions")
async def get_schema_versions(
    schema_id: str,
    client: BackendClient = Depends(get_backend_client),
):
    """List all versions for a schema (by fetching the base schema and related versions)."""
    try:
        schema = await client.get_schema(schema_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Schema not found") from exc
    # Return a list containing this schema; multi-version lookup requires backend support
    return [schema]


def _extract_unknown_ids(message: str) -> list[str]:
    """Extract unknown ID list from ValueError message."""
    import re

    match = re.search(r"\[(.+?)\]", message)
    if match:
        return [s.strip().strip("'\"") for s in match.group(1).split(",")]
    return []
