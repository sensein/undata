"""Import v2 YAML files to backend API."""

from __future__ import annotations

from pathlib import Path

import httpx
import yaml

from .validation import validate_file


async def import_elements(
    backend_url: str,
    elements_dir: Path,
    token: str | None = None,
) -> tuple[int, int]:
    """Import element YAML files to backend via POST /api/v1/elements.

    Returns (created_count, merged_count).
    """
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    created = 0
    merged = 0

    async with httpx.AsyncClient(base_url=backend_url, headers=headers) as client:
        for path in sorted(elements_dir.glob("*.yaml")):
            report = validate_file(path)
            if not report.valid:
                continue

            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            resp = await client.post("/api/v1/elements", json=data)

            if resp.status_code == 201:
                created += 1
            elif resp.status_code == 200:
                merged += 1

    return created, merged


async def import_values(
    backend_url: str,
    values_dir: Path,
    token: str | None = None,
) -> tuple[int, int]:
    """Import value concept YAML files to backend."""
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    created = 0
    merged = 0

    async with httpx.AsyncClient(base_url=backend_url, headers=headers) as client:
        for path in sorted(values_dir.glob("*.yaml")):
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or "semantic" not in data:
                continue
            resp = await client.post("/api/v1/values", json=data)
            if resp.status_code == 201:
                created += 1
            elif resp.status_code == 200:
                merged += 1

    return created, merged


async def import_schemas(
    backend_url: str,
    schemas_dir: Path,
    token: str | None = None,
) -> tuple[int, int]:
    """Import schema shape YAML files to backend."""
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    created = 0
    merged = 0

    async with httpx.AsyncClient(base_url=backend_url, headers=headers) as client:
        for path in sorted(schemas_dir.glob("*.yaml")):
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or "semantic" not in data:
                continue
            resp = await client.post("/api/v1/schemas", json=data)
            if resp.status_code == 201:
                created += 1
            elif resp.status_code == 200:
                merged += 1

    return created, merged
