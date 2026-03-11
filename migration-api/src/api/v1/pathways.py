"""Pathway CRUD and composition endpoints — /pathways."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from src.models import PathwayComposeRequest, PathwayCreateRequest
from src.services.backend_client import BackendClient, get_backend_client
from src.services.pathway_service import CompositionError, PathwayService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("", status_code=201)
async def create_pathway(
    request: PathwayCreateRequest,
    client: BackendClient = Depends(get_backend_client),
):
    """Register a migration pathway.

    Validates all mapping_ids, auto-derives inverse if possible, persists to backend.
    """
    service = PathwayService(client)
    steps = [{"position": s.position, "mapping_id": str(s.mapping_id)} for s in request.steps]

    try:
        await service.validate_steps(steps)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Create in backend
    payload: dict = {
        "name": request.name,
        "source_schema_id": str(request.source_schema_id),
        "target_schema_id": str(request.target_schema_id),
        "direction": request.direction,
        "steps": steps,
    }

    try:
        pathway = await client.create_pathway(payload)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Backend error: {exc}") from exc

    # Auto-derive inverse if possible
    can_inverse = await service.can_derive_inverse(steps)
    if can_inverse and not pathway.get("inverse_pathway_id"):
        try:
            inverse_steps = await service.build_inverse_steps(steps)
            inverse_payload = {
                "name": f"{request.name} (inverse)",
                "source_schema_id": str(request.target_schema_id),
                "target_schema_id": str(request.source_schema_id),
                "direction": "backward",
                "steps": inverse_steps,
            }
            inverse = await client.create_pathway(inverse_payload)
            await client.update_pathway(
                pathway["id"],
                {"name": request.name, "inverse_pathway_id": inverse["id"]},
            )
            pathway["inverse_pathway_id"] = inverse["id"]
        except Exception:
            logger.exception("Failed to create inverse pathway")

    return pathway


@router.get("")
async def list_pathways(
    source_schema_id: str | None = None,
    target_schema_id: str | None = None,
    direction: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    client: BackendClient = Depends(get_backend_client),
):
    """List pathways with optional filters."""
    params = {"limit": limit, "offset": offset}
    if source_schema_id:
        params["source_schema_id"] = source_schema_id
    if target_schema_id:
        params["target_schema_id"] = target_schema_id
    if direction:
        params["direction"] = direction
    if status:
        params["status"] = status

    try:
        return await client.list_pathways(**params)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/{pathway_id}")
async def get_pathway(
    pathway_id: str,
    client: BackendClient = Depends(get_backend_client),
):
    """Get a pathway by ID with full step details."""
    try:
        return await client.get_pathway(pathway_id)
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Pathway not found") from exc


@router.put("/{pathway_id}")
async def update_pathway(
    pathway_id: str,
    request: PathwayCreateRequest,
    client: BackendClient = Depends(get_backend_client),
):
    """Update a pathway's steps, re-validate, and set status."""
    service = PathwayService(client)
    steps = [{"position": s.position, "mapping_id": str(s.mapping_id)} for s in request.steps]

    try:
        await service.validate_steps(steps)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        return await client.update_pathway(
            pathway_id,
            {
                "name": request.name,
                "steps": steps,
                "status": "active",
            },
        )
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Pathway not found") from exc


@router.delete("/{pathway_id}", status_code=204)
async def delete_pathway(
    pathway_id: str,
    client: BackendClient = Depends(get_backend_client),
):
    """Soft-delete a pathway (sets status=deleted in backend)."""
    try:
        await client.update_pathway(pathway_id, {"status": "deleted"})
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Pathway not found") from exc


@router.post("/compose")
async def compose_pathways(
    request: PathwayComposeRequest,
    client: BackendClient = Depends(get_backend_client),
):
    """Compose two pathways A→B + B→C into A→C."""
    service = PathwayService(client)
    try:
        composed = await service.compose(
            str(request.pathway_a_id),
            str(request.pathway_b_id),
        )
    except CompositionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=404, detail="Pathway not found") from exc

    if request.save:
        try:
            saved = await client.create_pathway(composed)
            return saved
        except Exception as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    return composed
