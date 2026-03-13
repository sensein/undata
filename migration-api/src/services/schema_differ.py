"""Schema diff computation logic."""

from __future__ import annotations

import logging

from src.models import SchemaDiff
from src.services.backend_client import BackendClient

logger = logging.getLogger(__name__)


class SchemaDiffer:
    """Compute a structured diff between two schemas."""

    def __init__(self, client: BackendClient) -> None:
        self._client = client

    async def diff(
        self,
        source_schema_id: str,
        target_schema_id: str,
    ) -> SchemaDiff:
        """
        Compare two schemas and produce a SchemaDiff.

        Categories:
          - added: in target, not in source (by element name)
          - removed: in source, not in target (by element name)
          - type_changed: same name, different data_type
          - description_changed: same name + type, different description
          - constraint_changed: same name + type + description, different constraints
          - renamed: detected via alias_group (not yet implemented — placeholder)

        Coverage:
          - FULL: no diffs (or all diffs have registered mappings)
          - PARTIAL: some diffs exist but at least one has a mapping
          - NONE: diffs exist, no mappings cover them
        """
        source_elements = await self._client.get_schema_elements(source_schema_id)
        target_elements = await self._client.get_schema_elements(target_schema_id)

        source_by_name: dict[str, dict] = {e["name"]: e for e in source_elements}
        target_by_name: dict[str, dict] = {e["name"]: e for e in target_elements}

        added: list[dict] = []
        removed: list[dict] = []
        type_changed: list[dict] = []
        description_changed: list[dict] = []
        constraint_changed: list[dict] = []

        # Elements in target but not source → ADDED
        for name, elem in target_by_name.items():
            if name not in source_by_name:
                added.append(
                    {"element_id": elem["id"], "name": name, "schema_id": target_schema_id}
                )

        # Elements in source but not target → REMOVED
        for name, elem in source_by_name.items():
            if name not in target_by_name:
                removed.append(
                    {"element_id": elem["id"], "name": name, "schema_id": source_schema_id}
                )

        # Elements in both — check for changes
        for name in source_by_name.keys() & target_by_name.keys():
            src = source_by_name[name]
            tgt = target_by_name[name]

            if src.get("data_type") != tgt.get("data_type"):
                type_changed.append(
                    {
                        "name": name,
                        "source": {"element_id": src["id"], "data_type": src.get("data_type")},
                        "target": {"element_id": tgt["id"], "data_type": tgt.get("data_type")},
                    }
                )
            elif src.get("description") != tgt.get("description"):
                description_changed.append(
                    {
                        "name": name,
                        "source": {
                            "element_id": src["id"],
                            "description": src.get("description"),
                        },
                        "target": {
                            "element_id": tgt["id"],
                            "description": tgt.get("description"),
                        },
                    }
                )
            elif src.get("constraints") != tgt.get("constraints"):
                constraint_changed.append(
                    {
                        "name": name,
                        "source": {
                            "element_id": src["id"],
                            "constraints": src.get("constraints"),
                        },
                        "target": {
                            "element_id": tgt["id"],
                            "constraints": tgt.get("constraints"),
                        },
                    }
                )

        # Assess coverage
        total_diffs = (
            len(added)
            + len(removed)
            + len(type_changed)
            + len(description_changed)
            + len(constraint_changed)
        )

        draft_pathway: dict | None = None

        if total_diffs == 0:
            coverage = "FULL"
        else:
            # Check if any pathways exist between these schemas
            try:
                pathway_data = await self._client.list_pathways(
                    source_schema_id=source_schema_id,
                    target_schema_id=target_schema_id,
                )
                existing_pathways = (
                    (pathway_data.get("items") or []) if isinstance(pathway_data, dict) else []
                )
                if existing_pathways:
                    coverage = "PARTIAL"
                    # Assemble draft pathway from the first matching pathway;
                    # gaps are elements with no mapping (added/removed elements)
                    first = existing_pathways[0]
                    gap_names = [e["name"] for e in removed] + [e["name"] for e in added]
                    draft_pathway = {
                        "pathway_id": first.get("id"),
                        "name": first.get("name"),
                        "source_schema_id": source_schema_id,
                        "target_schema_id": target_schema_id,
                        "steps": first.get("steps") or [],
                        "gaps": gap_names,
                    }
                else:
                    coverage = "NONE"
            except Exception:
                coverage = "NONE"

        return SchemaDiff(
            source_schema_id=source_schema_id,
            target_schema_id=target_schema_id,
            coverage=coverage,
            added=added,
            removed=removed,
            renamed=[],  # alias-group detection not yet implemented
            type_changed=type_changed,
            constraint_changed=constraint_changed,
            description_changed=description_changed,
            draft_pathway=draft_pathway,
        )
