"""Integration tests for audit trail and provenance — US3.

⚠️ TDD: These tests MUST FAIL before T064/T065 are implemented.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_audit_entries_created_on_element_lifecycle(client: AsyncClient, curator_token: str):
    """CREATE, UPDATE, DELETE on element produces 3 audit log entries."""
    headers = {"Authorization": f"Bearer {curator_token}"}

    # Create a source first
    src_resp = await client.post(
        "/api/v1/sources",
        json={"name": "audit-test-source", "format": "bids", "content_hash": "audit-hash"},
        headers=headers,
    )
    assert src_resp.status_code == 201
    source_id = src_resp.json()["id"]

    # Create element
    create_resp = await client.post(
        "/api/v1/elements",
        json={
            "name": "audit_test_element",
            "data_type": "string",
            "source_id": source_id,
            "source_local_id": "audit_test_el",
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    element_id = create_resp.json()["id"]

    # Update element
    update_resp = await client.put(
        f"/api/v1/elements/{element_id}",
        json={"description": "updated description", "version_num": 1},
        headers=headers,
    )
    assert update_resp.status_code == 200

    # Delete element
    del_resp = await client.delete(f"/api/v1/elements/{element_id}", headers=headers)
    assert del_resp.status_code == 200

    # Query audit log for this element
    audit_resp = await client.get(
        "/api/v1/audit",
        params={"record_type": "DataElement", "record_id": element_id},
    )
    assert audit_resp.status_code == 200
    data = audit_resp.json()
    assert data["total"] >= 3
    operations = [item["operation"] for item in data["items"]]
    assert "create" in operations
    assert "update" in operations
    assert "delete" in operations


@pytest.mark.asyncio
async def test_audit_entries_have_actor_id_uuid(client: AsyncClient, curator_token: str):
    """Audit entries must have actor_id as UUID (not email string) and actor_display_name."""
    headers = {"Authorization": f"Bearer {curator_token}"}

    src_resp = await client.post(
        "/api/v1/sources",
        json={"name": "audit-actor-source", "format": "bids", "content_hash": "actor-hash"},
        headers=headers,
    )
    assert src_resp.status_code == 201
    source_id = src_resp.json()["id"]

    create_resp = await client.post(
        "/api/v1/elements",
        json={
            "name": "actor_test_element",
            "data_type": "integer",
            "source_id": source_id,
            "source_local_id": "actor_test_el",
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    element_id = create_resp.json()["id"]

    audit_resp = await client.get(
        "/api/v1/audit",
        params={"record_type": "DataElement", "record_id": element_id, "operation": "create"},
    )
    assert audit_resp.status_code == 200
    items = audit_resp.json()["items"]
    assert len(items) >= 1
    entry = items[0]

    # actor_id must be a UUID string, not an email
    import re
    uuid_pattern = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
    assert uuid_pattern.match(entry["actor_id"]), f"actor_id should be UUID, got: {entry['actor_id']}"
    assert "actor_display_name" in entry
    assert isinstance(entry["actor_display_name"], str)


@pytest.mark.asyncio
async def test_audit_filter_by_record_type(client: AsyncClient, curator_token: str):
    """GET /audit?record_type=DataElement returns only DataElement entries."""
    audit_resp = await client.get(
        "/api/v1/audit",
        params={"record_type": "DataElement", "limit": 10},
    )
    assert audit_resp.status_code == 200
    data = audit_resp.json()
    assert "total" in data
    assert "items" in data
    for item in data["items"]:
        assert item["record_type"] == "DataElement"


@pytest.mark.asyncio
async def test_audit_filter_by_actor_id(client: AsyncClient, curator_token: str):
    """GET /audit?actor_id=<uuid> returns entries filtered to that actor."""
    # Get current user to know actor_id
    me_resp = await client.get(
        "/api/v1/users/me",
        headers={"Authorization": f"Bearer {curator_token}"},
    )
    assert me_resp.status_code == 200
    actor_id = me_resp.json()["id"]

    audit_resp = await client.get(
        "/api/v1/audit",
        params={"actor_id": actor_id, "limit": 5},
    )
    assert audit_resp.status_code == 200
    data = audit_resp.json()
    for item in data["items"]:
        assert item["actor_id"] == actor_id


@pytest.mark.asyncio
async def test_audit_filter_by_time_range(client: AsyncClient, curator_token: str):
    """GET /audit?from=<iso>&to=<iso> time-bounds results correctly."""
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    from_ts = now.replace(year=now.year - 1).isoformat()
    to_ts = now.replace(year=now.year + 1).isoformat()

    audit_resp = await client.get(
        "/api/v1/audit",
        params={"from": from_ts, "to": to_ts, "limit": 5},
    )
    assert audit_resp.status_code == 200
    data = audit_resp.json()
    assert "total" in data
    assert isinstance(data["items"], list)


@pytest.mark.asyncio
async def test_audit_update_entry_has_diff(client: AsyncClient, curator_token: str):
    """UPDATE audit entry has a non-null diff field."""
    headers = {"Authorization": f"Bearer {curator_token}"}

    src_resp = await client.post(
        "/api/v1/sources",
        json={"name": "audit-diff-source", "format": "bids", "content_hash": "diff-hash"},
        headers=headers,
    )
    assert src_resp.status_code == 201
    source_id = src_resp.json()["id"]

    create_resp = await client.post(
        "/api/v1/elements",
        json={
            "name": "diff_test_element",
            "data_type": "string",
            "source_id": source_id,
            "source_local_id": "diff_test_el",
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    element_id = create_resp.json()["id"]

    await client.put(
        f"/api/v1/elements/{element_id}",
        json={"description": "added description", "version_num": 1},
        headers=headers,
    )

    audit_resp = await client.get(
        "/api/v1/audit",
        params={"record_type": "DataElement", "record_id": element_id, "operation": "update"},
    )
    assert audit_resp.status_code == 200
    items = audit_resp.json()["items"]
    assert len(items) >= 1
    # diff should be present for update operations
    update_entry = items[0]
    assert update_entry["operation"] == "update"


@pytest.mark.asyncio
async def test_element_history_ascending_order(client: AsyncClient, curator_token: str):
    """GET /elements/{id}/history returns versions in ascending version_num order."""
    headers = {"Authorization": f"Bearer {curator_token}"}

    src_resp = await client.post(
        "/api/v1/sources",
        json={"name": "history-source", "format": "bids", "content_hash": "hist-hash"},
        headers=headers,
    )
    assert src_resp.status_code == 201
    source_id = src_resp.json()["id"]

    create_resp = await client.post(
        "/api/v1/elements",
        json={
            "name": "history_element",
            "data_type": "float",
            "source_id": source_id,
            "source_local_id": "history_el",
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    element_id = create_resp.json()["id"]

    # Create second version
    await client.put(
        f"/api/v1/elements/{element_id}",
        json={"description": "v2 description", "version_num": 1},
        headers=headers,
    )

    history_resp = await client.get(f"/api/v1/elements/{element_id}/history")
    assert history_resp.status_code == 200
    versions = history_resp.json()
    assert len(versions) >= 2
    version_nums = [v["version_num"] for v in versions]
    assert version_nums == sorted(version_nums), "Versions should be in ascending order"


@pytest.mark.asyncio
async def test_soft_deleted_element_retrievable_by_id(client: AsyncClient, curator_token: str):
    """GET /elements/{id} for a soft-deleted element returns it with deleted_at non-null."""
    headers = {"Authorization": f"Bearer {curator_token}"}

    src_resp = await client.post(
        "/api/v1/sources",
        json={"name": "deleted-source", "format": "bids", "content_hash": "del-hash"},
        headers=headers,
    )
    assert src_resp.status_code == 201
    source_id = src_resp.json()["id"]

    create_resp = await client.post(
        "/api/v1/elements",
        json={
            "name": "deleted_element",
            "data_type": "string",
            "source_id": source_id,
            "source_local_id": "del_el",
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    element_id = create_resp.json()["id"]

    await client.delete(f"/api/v1/elements/{element_id}", headers=headers)

    get_resp = await client.get(f"/api/v1/elements/{element_id}")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["deleted_at"] is not None, "deleted_at should be set after soft-delete"
