"""Export elements and mappings from backend API to library YAML files."""

from __future__ import annotations

from pathlib import Path

import httpx
import yaml

from .models import (
    ElementMetadata,
    ElementRecord,
    ElementVersion,
    MappingMetadata,
    MappingRecord,
    MappingVersion,
)


async def export_elements(
    backend_url: str,
    output_dir: Path,
    token: str | None = None,
) -> int:
    """Fetch all elements from backend and write YAML files.

    Returns the number of elements exported.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    count = 0
    offset = 0
    limit = 100

    async with httpx.AsyncClient(base_url=backend_url, headers=headers) as client:
        while True:
            resp = await client.get(
                "/api/v1/elements", params={"limit": limit, "offset": offset}
            )
            resp.raise_for_status()
            data = resp.json()
            items = data.get("items", [])
            if not items:
                break

            for item in items:
                record = _element_api_to_record(item)
                filename = f"element-{item['id']}.yaml"
                path = output_dir / filename
                path.write_text(
                    yaml.dump(
                        record.model_dump(mode="json", exclude_none=True),
                        default_flow_style=False,
                        sort_keys=False,
                    ),
                    encoding="utf-8",
                )
                count += 1

            offset += limit
            if offset >= data.get("total", 0):
                break

    return count


async def export_mappings(
    backend_url: str,
    output_dir: Path,
    token: str | None = None,
) -> int:
    """Fetch all mappings from backend and write YAML files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    count = 0
    offset = 0
    limit = 100

    async with httpx.AsyncClient(base_url=backend_url, headers=headers) as client:
        while True:
            resp = await client.get(
                "/api/v1/mappings", params={"limit": limit, "offset": offset}
            )
            resp.raise_for_status()
            data = resp.json()
            items = data.get("items", [])
            if not items:
                break

            for item in items:
                record = _mapping_api_to_record(item)
                filename = f"mapping-{item['id']}.yaml"
                path = output_dir / filename
                path.write_text(
                    yaml.dump(
                        record.model_dump(mode="json", exclude_none=True),
                        default_flow_style=False,
                        sort_keys=False,
                    ),
                    encoding="utf-8",
                )
                count += 1

            offset += limit
            if offset >= data.get("total", 0):
                break

    return count


def _element_api_to_record(api_item: dict) -> ElementRecord:
    """Convert backend API element response to ElementRecord."""
    version = ElementVersion(
        version_num=api_item.get("version_num", 1),
        name=api_item.get("name", ""),
        data_type=api_item.get("data_type", "string"),
        description=api_item.get("description"),
        required=api_item.get("required"),
        multivalued=api_item.get("multivalued"),
        allowed_values=api_item.get("allowed_values"),
        constraints=api_item.get("constraints"),
        created_at=api_item.get("created_at", "2026-01-01T00:00:00Z"),
    )

    source = api_item.get("source", {})
    metadata = ElementMetadata(
        id=api_item.get("uri", f"https://schema.undata.live/elements/{api_item['id']}"),
        source_local_id=api_item.get("source_local_id", api_item["id"]),
        source_id=source.get("id"),
        created_at=api_item.get("created_at", "2026-01-01T00:00:00Z"),
    )

    return ElementRecord(
        element=metadata,
        versions=[version],
        current_version=version.version_num,
    )


def _mapping_api_to_record(api_item: dict) -> MappingRecord:
    """Convert backend API mapping response to MappingRecord."""
    version = MappingVersion(
        version_num=api_item.get("version_num", 1),
        function_type=api_item.get("function_type"),
        created_at=api_item.get("created_at", "2026-01-01T00:00:00Z"),
    )

    metadata = MappingMetadata(
        id=api_item.get("uri", f"https://schema.undata.live/mappings/{api_item['id']}"),
        output_element_id=api_item.get("output_element_id"),
        status=api_item.get("status"),
        attributed_to=api_item.get("attributed_to"),
        confidence_score=api_item.get("confidence_score"),
        created_at=api_item.get("created_at", "2026-01-01T00:00:00Z"),
    )

    return MappingRecord(
        mapping=metadata,
        versions=[version],
        current_version=version.version_num,
    )
