"""IngestionPipeline — normalizes elements and bulk-POSTs to the backend."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import httpx

from undata.logging import get_logger
from undata.models import IngestionResult, NormalizedElement, SchemaClassPayload

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

BULK_CHUNK_SIZE = 50


def _element_to_payload(el: NormalizedElement, source_id: str) -> dict:
    payload: dict = {
        "source_id": source_id,
        "source_local_id": el.source_local_id,
        "name": el.name,
        "data_type": el.data_type,
        "description": el.description,
        "required": el.required,
        "multivalued": el.multivalued,
    }
    if el.allowed_values:
        payload["allowed_values"] = el.allowed_values
    if el.constraints:
        payload["constraints"] = el.constraints
    return payload


class IngestionPipeline:
    def __init__(self, backend_url: str, token: str) -> None:
        self._backend_url = backend_url.rstrip("/")
        self._token = token

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

    async def _upsert_source(
        self,
        client: httpx.AsyncClient,
        source_name: str,
        source_format: str,
        version_info: dict,
    ) -> str:
        resp = await client.post(
            f"{self._backend_url}/sources",
            json={
                "name": source_name,
                "format": source_format,
                "version_tag": version_info.get("version_tag", ""),
                "content_hash": version_info.get("content_hash", ""),
            },
            headers=self._headers(),
        )
        if resp.status_code == 409:
            # Duplicate source — already ingested; log WARN and return existing ID
            logger.warning(
                "Source already exists (409 Duplicate) — using existing source",
                extra={"source_name": source_name},
            )
            # Try to get the existing source ID from the 409 response body
            try:
                body = resp.json()
                if "id" in body:
                    return body["id"]
            except Exception:
                pass
            # Fallback: GET /sources?name=... to find the existing source ID
            list_resp = await client.get(
                f"{self._backend_url}/sources",
                params={"name": source_name},
                headers=self._headers(),
            )
            list_resp.raise_for_status()
            items = list_resp.json().get("items", [])
            if items:
                return items[0]["id"]
            # If we still can't find it, raise to avoid silent data loss
            raise RuntimeError(
                f"Source '{source_name}' returned 409 but could not be found via GET /sources"
            )
        resp.raise_for_status()
        return resp.json()["id"]

    async def _bulk_post(
        self,
        client: httpx.AsyncClient,
        source_id: str,
        elements: list[NormalizedElement],
    ) -> tuple[int, int, list[dict]]:
        succeeded = 0
        failed = 0
        failures: list[dict] = []

        for i in range(0, len(elements), BULK_CHUNK_SIZE):
            chunk = elements[i : i + BULK_CHUNK_SIZE]
            payload = {"elements": [_element_to_payload(el, source_id) for el in chunk]}
            resp = await client.post(
                f"{self._backend_url}/elements/bulk",
                json=payload,
                headers=self._headers(),
            )
            if resp.status_code not in (200, 201, 207):
                resp.raise_for_status()
            result = resp.json()
            succeeded_items = result.get("succeeded", [])
            failed_items = result.get("failed", [])
            succeeded += (
                len(succeeded_items) if isinstance(succeeded_items, list) else int(succeeded_items)
            )
            failed += len(failed_items) if isinstance(failed_items, list) else int(failed_items)
            failures.extend(failed_items if isinstance(failed_items, list) else [])

        return succeeded, failed, failures

    async def _post_classes(
        self,
        client: httpx.AsyncClient,
        source_id: str,
        classes: list[SchemaClassPayload],
        element_slid_to_id: dict[str, str],
    ) -> None:
        """POST class nodes and link elements for each SchemaClassPayload."""
        classes_created = 0
        links_created = 0

        for cls in classes:
            # Create class node
            resp = await client.post(
                f"{self._backend_url}/sources/{source_id}/classes",
                headers=self._headers(),
                json={
                    "class_name": cls.class_name,
                    "description": cls.description,
                    "parent_class_name": cls.parent_class_name,
                },
            )
            if resp.status_code not in (200, 201):
                logger.warning(
                    "Class creation failed",
                    extra={"class_name": cls.class_name, "status": resp.status_code},
                )
                continue

            class_id = resp.json().get("id")
            classes_created += 1

            # Link elements
            for slid in cls.element_source_local_ids:
                element_id = element_slid_to_id.get(slid)
                if not element_id:
                    continue
                link_resp = await client.post(
                    f"{self._backend_url}/sources/{source_id}/classes/{class_id}/elements",
                    headers=self._headers(),
                    json={"element_id": element_id},
                )
                if link_resp.status_code in (200, 201):
                    links_created += 1

        logger.info(
            "Classes posted",
            extra={"source_id": source_id, "classes": classes_created, "links": links_created},
        )

    async def ingest(
        self,
        source_name: str,
        source_format: str,
        elements: list[NormalizedElement],
        version_info: dict,
        dry_run: bool = False,
        classes: list[SchemaClassPayload] | None = None,
    ) -> IngestionResult:
        start = time.monotonic()
        submitted = len(elements)

        if dry_run:
            logger.info(
                "Dry run — skipping backend writes",
                extra={"source": source_name, "count": submitted},
            )
            return IngestionResult(
                source_name=source_name,
                elements_submitted=submitted,
                elements_succeeded=submitted,
                elements_failed=0,
                failures=[],
                duration_seconds=time.monotonic() - start,
            )

        async with httpx.AsyncClient(timeout=300.0, follow_redirects=True) as client:
            source_id = await self._upsert_source(client, source_name, source_format, version_info)
            succeeded, failed, failures = await self._bulk_post(client, source_id, elements)

            # Post class groupings if provided
            if classes:
                # Build source_local_id → element_id mapping from elements list
                slid_map: dict[str, str] = {}
                for failure_info in failures:
                    pass  # We don't have IDs for failures

                # Fetch element IDs by source_local_id via a lightweight GET
                slids = [el.source_local_id for el in elements]
                # Build map from what we can — query element IDs from backend
                try:
                    list_resp = await client.get(
                        f"{self._backend_url}/elements",
                        headers=self._headers(),
                        params={"source_id": source_id, "limit": len(slids)},
                    )
                    if list_resp.status_code == 200:
                        for item in list_resp.json().get("items", []):
                            slid = item.get("source_local_id", "")
                            if slid:
                                slid_map[slid] = item["id"]
                except Exception as exc:
                    logger.warning(
                        "Could not fetch element IDs for class linking", extra={"error": str(exc)}
                    )

                await self._post_classes(client, source_id, classes, slid_map)

        duration = time.monotonic() - start
        logger.info(
            "Ingest complete",
            extra={
                "source": source_name,
                "succeeded": succeeded,
                "failed": failed,
                "duration_s": round(duration, 2),
            },
        )
        return IngestionResult(
            source_name=source_name,
            elements_submitted=submitted,
            elements_succeeded=succeeded,
            elements_failed=failed,
            failures=failures,
            duration_seconds=duration,
        )
