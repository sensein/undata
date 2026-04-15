"""Export elements, values, and schemas from backend API to v2 YAML files."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import httpx
import yaml


async def _paginate_and_write(
    client: httpx.AsyncClient,
    endpoint: str,
    writer: Callable[[dict, Path], None],
    output_dir: Path,
    limit: int = 100,
) -> int:
    """Generic paginated fetch + write loop for export endpoints."""
    count = 0
    offset = 0
    while True:
        resp = await client.get(endpoint, params={"limit": limit, "offset": offset})
        resp.raise_for_status()
        data = resp.json()
        items = data.get("items", [])
        if not items:
            break
        for item in items:
            writer(item, output_dir)
            count += 1
        offset += limit
        if offset >= data.get("total", 0):
            break
    return count


def _write_entity_yaml(item: dict, output_dir: Path) -> None:
    """Write an API response item to a v2 YAML file."""
    uri = item["uri"]
    filename = uri.split("/")[-1] + ".yaml"
    data = {"semantic": item["semantic"], "provenance": item["provenance"]}
    (output_dir / filename).write_text(
        yaml.dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8"
    )


async def export_elements(
    backend_url: str,
    output_dir: Path,
    token: str | None = None,
) -> int:
    """Fetch elements from backend API and write v2 YAML files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    async with httpx.AsyncClient(base_url=backend_url, headers=headers) as client:
        return await _paginate_and_write(client, "/api/v1/elements", _write_entity_yaml, output_dir)


async def export_values(
    backend_url: str,
    output_dir: Path,
    token: str | None = None,
) -> int:
    """Fetch value concepts from backend API and write YAML files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    async with httpx.AsyncClient(base_url=backend_url, headers=headers) as client:
        return await _paginate_and_write(client, "/api/v1/values", _write_entity_yaml, output_dir)


async def export_schemas(
    backend_url: str,
    output_dir: Path,
    token: str | None = None,
) -> int:
    """Fetch schema shapes from backend API and write YAML files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    async with httpx.AsyncClient(base_url=backend_url, headers=headers) as client:
        return await _paginate_and_write(client, "/api/v1/schemas", _write_entity_yaml, output_dir)
