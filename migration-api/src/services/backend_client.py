"""Async httpx client wrapping 002-schema-backend API."""

from __future__ import annotations

import os
from uuid import UUID

import httpx

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8002")
_TIMEOUT = 30.0


class BackendClientError(Exception):
    """Raised when the backend returns an unexpected error."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"BackendClient HTTP {status_code}: {detail}")


class BackendClient:
    """Async client for 002-schema-backend REST API."""

    def __init__(self, base_url: str = BACKEND_URL) -> None:
        self._base = base_url.rstrip("/")
        self._client = httpx.AsyncClient(base_url=self._base, timeout=_TIMEOUT)

    async def __aenter__(self) -> BackendClient:
        return self

    async def __aexit__(self, *args) -> None:
        await self._client.aclose()

    def _raise_for_status(self, resp: httpx.Response) -> None:
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("detail", resp.text)
            except Exception:
                detail = resp.text
            raise BackendClientError(resp.status_code, detail)

    # ---- Elements ----

    async def get_element(self, element_id: str | UUID) -> dict:
        resp = await self._client.get(f"/api/v1/elements/{element_id}")
        self._raise_for_status(resp)
        return resp.json()

    async def get_elements(self, ids: list[str | UUID]) -> list[dict]:
        """Fetch multiple elements; raises BackendClientError if any are missing."""
        results = []
        for eid in ids:
            element = await self.get_element(eid)
            results.append(element)
        return results

    # ---- Mappings ----

    async def get_mapping(self, mapping_id: str | UUID) -> dict:
        resp = await self._client.get(f"/api/v1/mappings/{mapping_id}")
        self._raise_for_status(resp)
        return resp.json()

    # ---- Schemas ----

    async def get_schema(self, schema_id: str | UUID) -> dict:
        resp = await self._client.get(f"/api/v1/schemas/{schema_id}")
        self._raise_for_status(resp)
        return resp.json()

    async def create_schema(self, payload: dict) -> dict:
        resp = await self._client.post("/api/v1/schemas", json=payload)
        self._raise_for_status(resp)
        return resp.json()

    async def get_schema_elements(self, schema_id: str | UUID) -> list[dict]:
        """Return all elements associated with a schema."""
        resp = await self._client.get(f"/api/v1/schemas/{schema_id}/elements")
        self._raise_for_status(resp)
        return resp.json()

    # ---- Pathways ----

    async def get_pathway(self, pathway_id: str | UUID) -> dict:
        resp = await self._client.get(f"/api/v1/pathways/{pathway_id}")
        self._raise_for_status(resp)
        return resp.json()

    async def create_pathway(self, payload: dict) -> dict:
        resp = await self._client.post("/api/v1/pathways", json=payload)
        self._raise_for_status(resp)
        return resp.json()

    async def update_pathway(self, pathway_id: str | UUID, payload: dict) -> dict:
        resp = await self._client.put(f"/api/v1/pathways/{pathway_id}", json=payload)
        self._raise_for_status(resp)
        return resp.json()

    async def list_pathways(self, **params) -> dict:
        resp = await self._client.get("/api/v1/pathways", params=params)
        self._raise_for_status(resp)
        return resp.json()


def get_backend_client() -> BackendClient:
    """FastAPI dependency: returns a BackendClient using the configured BACKEND_URL."""
    return BackendClient()
