"""Schema diff endpoints — /diff."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from src.models import DiffRequest, DiffResponse
from src.services.backend_client import BackendClient, BackendClientError, get_backend_client
from src.services.schema_differ import SchemaDiffer

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("", response_model=DiffResponse)
async def diff_schemas(
    request: DiffRequest,
    client: BackendClient = Depends(get_backend_client),
) -> DiffResponse:
    """Compare two schemas and return a structured compatibility diff."""
    source_id = str(request.source_schema_id)
    target_id = str(request.target_schema_id)

    # Validate both schemas exist
    try:
        await client.get_schema(source_id)
    except BackendClientError as exc:
        raise HTTPException(
            status_code=404, detail=f"Source schema not found: {source_id}"
        ) from exc
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Source schema not found") from exc

    differ = SchemaDiffer(client)
    diff = await differ.diff(source_id, target_id)

    return DiffResponse(
        source_schema_id=diff.source_schema_id,
        target_schema_id=diff.target_schema_id,
        coverage=diff.coverage,
        added=diff.added,
        removed=diff.removed,
        renamed=[],
        type_changed=diff.type_changed,
        constraint_changed=diff.constraint_changed,
        description_changed=diff.description_changed,
        draft_pathway=diff.draft_pathway,
    )
