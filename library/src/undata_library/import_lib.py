"""Import elements and mappings from library YAML files to backend API."""

from __future__ import annotations

from pathlib import Path

import httpx
import yaml

from .models import ElementRecord
from .validation import validate_file


async def import_elements(
    backend_url: str,
    elements_dir: Path,
    token: str | None = None,
) -> tuple[int, int]:
    """Import element YAML files to backend.

    Returns (created_count, skipped_count).
    """
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    created = 0
    skipped = 0

    async with httpx.AsyncClient(base_url=backend_url, headers=headers) as client:
        for path in sorted(elements_dir.glob("*.yaml")):
            report = validate_file(path)
            if not report.valid:
                skipped += 1
                continue

            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            record = ElementRecord.model_validate(data)

            # Use latest version for creation
            latest = max(record.versions, key=lambda v: v.version_num)

            payload = {
                "name": latest.name,
                "data_type": latest.data_type.value,
                "description": latest.description,
                "required": latest.required or False,
                "multivalued": latest.multivalued or False,
                "source_local_id": record.element.source_local_id,
            }

            if latest.allowed_values:
                payload["allowed_values"] = latest.allowed_values

            resp = await client.post("/api/v1/elements", json=payload)

            if resp.status_code == 201:
                created += 1
            elif resp.status_code == 409:
                skipped += 1  # duplicate
            else:
                skipped += 1

    return created, skipped
