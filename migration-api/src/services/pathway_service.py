"""Pathway validation and composition service."""

from __future__ import annotations

import logging

from src.services.backend_client import BackendClient, BackendClientError

logger = logging.getLogger(__name__)


class BrokenPathwayError(Exception):
    """Raised when a pathway has status='broken'."""


class CompositionError(Exception):
    """Raised when pathway composition fails due to schema mismatch or other issues."""


class PathwayService:
    """Business logic for pathway validation and composition."""

    def __init__(self, client: BackendClient) -> None:
        self._client = client

    async def validate_steps(self, steps: list[dict]) -> None:
        """
        Validate that all mapping_ids in steps exist in the backend.

        Raises:
            ValueError: If any mapping_id cannot be found.
        """
        unknown: list[str] = []
        for step in steps:
            mapping_id = step.get("mapping_id", "")
            try:
                await self._client.get_mapping(mapping_id)
            except BackendClientError as exc:
                if exc.status_code == 404:
                    unknown.append(mapping_id)
                else:
                    raise
        if unknown:
            raise ValueError(f"Unknown mapping_id(s): {unknown}")

    async def can_derive_inverse(self, steps: list[dict]) -> bool:
        """
        Check whether an inverse pathway can be auto-derived.

        Returns True only if every step has an inverse_mapping_id in the backend.
        """
        for step in steps:
            mapping_id = step.get("mapping_id", "")
            try:
                mapping = await self._client.get_mapping(mapping_id)
            except BackendClientError:
                return False
            cv = mapping.get("current_version") or {}
            if not cv.get("inverse_mapping_id"):
                return False
        return True

    async def build_inverse_steps(self, steps: list[dict]) -> list[dict]:
        """Build the inverse step list by fetching inverse_mapping_ids in reverse order."""
        inverse_steps = []
        for i, step in enumerate(reversed(steps)):
            mapping = await self._client.get_mapping(step["mapping_id"])
            cv = mapping.get("current_version") or {}
            inverse_steps.append(
                {
                    "position": i,
                    "mapping_id": cv["inverse_mapping_id"],
                }
            )
        return inverse_steps

    async def compose(
        self,
        pathway_a_id: str,
        pathway_b_id: str,
    ) -> dict:
        """
        Compose two pathways A→B and B→C into a single A→C pathway.

        Raises:
            CompositionError: If pathway_a.target_schema_id != pathway_b.source_schema_id.
        """
        pathway_a = await self._client.get_pathway(pathway_a_id)
        pathway_b = await self._client.get_pathway(pathway_b_id)

        if pathway_a["target_schema_id"] != pathway_b["source_schema_id"]:
            raise CompositionError(
                f"Schema mismatch: pathway_a.target={pathway_a['target_schema_id']} "
                f"!= pathway_b.source={pathway_b['source_schema_id']}"
            )

        # Concatenate steps with re-indexed positions
        steps_a = pathway_a.get("steps") or []
        steps_b = pathway_b.get("steps") or []
        combined_steps = []
        for i, step in enumerate(steps_a):
            combined_steps.append({"position": i, "mapping_id": step["mapping_id"]})
        offset = len(steps_a)
        for j, step in enumerate(steps_b):
            combined_steps.append({"position": offset + j, "mapping_id": step["mapping_id"]})

        return {
            "name": f"{pathway_a['name']}+{pathway_b['name']}",
            "source_schema_id": pathway_a["source_schema_id"],
            "target_schema_id": pathway_b["target_schema_id"],
            "direction": "forward",
            "status": "active",
            "steps": combined_steps,
            "inverse_pathway_id": None,
            "version_num": 0,
        }
