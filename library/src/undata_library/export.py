"""Export elements, values, and schemas from backend API to v2 YAML files."""

from __future__ import annotations

from pathlib import Path

import httpx
import yaml


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

    count = 0
    offset = 0
    limit = 100

    async with httpx.AsyncClient(base_url=backend_url, headers=headers) as client:
        while True:
            resp = await client.get("/api/v1/elements", params={"limit": limit, "offset": offset})
            resp.raise_for_status()
            data = resp.json()
            items = data.get("items", [])
            if not items:
                break

            for item in items:
                _write_element_yaml(item, output_dir)
                count += 1

            offset += limit
            if offset >= data.get("total", 0):
                break

    return count


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

    count = 0
    offset = 0
    limit = 100

    async with httpx.AsyncClient(base_url=backend_url, headers=headers) as client:
        while True:
            resp = await client.get("/api/v1/values", params={"limit": limit, "offset": offset})
            resp.raise_for_status()
            data = resp.json()
            items = data.get("items", [])
            if not items:
                break

            for item in items:
                _write_value_yaml(item, output_dir)
                count += 1

            offset += limit
            if offset >= data.get("total", 0):
                break

    return count


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

    count = 0
    offset = 0
    limit = 100

    async with httpx.AsyncClient(base_url=backend_url, headers=headers) as client:
        while True:
            resp = await client.get("/api/v1/schemas", params={"limit": limit, "offset": offset})
            resp.raise_for_status()
            data = resp.json()
            items = data.get("items", [])
            if not items:
                break

            for item in items:
                _write_schema_yaml(item, output_dir)
                count += 1

            offset += limit
            if offset >= data.get("total", 0):
                break

    return count


def _write_element_yaml(item: dict, output_dir: Path) -> None:
    """Write an element API response to a v2 YAML file."""
    uri = item["uri"]
    filename = uri.split("/")[-1] + ".yaml"
    data = {"semantic": item["semantic"], "provenance": item["provenance"]}
    (output_dir / filename).write_text(
        yaml.dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8"
    )


def _write_value_yaml(item: dict, output_dir: Path) -> None:
    uri = item["uri"]
    filename = uri.split("/")[-1] + ".yaml"
    data = {"semantic": item["semantic"], "provenance": item["provenance"]}
    (output_dir / filename).write_text(
        yaml.dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8"
    )


def _write_schema_yaml(item: dict, output_dir: Path) -> None:
    uri = item["uri"]
    filename = uri.split("/")[-1] + ".yaml"
    data = {"semantic": item["semantic"], "provenance": item["provenance"]}
    (output_dir / filename).write_text(
        yaml.dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8"
    )
