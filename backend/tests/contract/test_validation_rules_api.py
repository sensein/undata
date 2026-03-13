"""Contract tests for Validation Rules API — T028/T029/T030/T031.

TDD: These tests MUST FAIL before /elements/{id}/validation-rules endpoints
are implemented.
"""

from __future__ import annotations

from uuid import uuid4

import pytest


@pytest.fixture()
async def element_with_source(client, curator_token):
    """Create a source + element, return (element_id, source_id)."""
    src_resp = await client.post(
        "/api/v1/sources",
        headers={"Authorization": f"Bearer {curator_token}"},
        json={"name": f"vr-src-{uuid4()}", "format": "bids"},
    )
    assert src_resp.status_code == 201
    source = src_resp.json()

    el_resp = await client.post(
        "/api/v1/elements",
        headers={"Authorization": f"Bearer {curator_token}"},
        json={"name": f"age-{uuid4()}", "data_type": "integer", "source_id": source["id"]},
    )
    assert el_resp.status_code == 201
    return el_resp.json()["id"], source["id"]


class TestPostValidationRule:
    """T028 — POST /api/v1/elements/{id}/validation-rules"""

    async def test_create_rule_returns_201_with_id(self, client, curator_token, element_with_source):
        """POST returns 201 with stable rule id."""
        element_id, _ = element_with_source

        resp = await client.post(
            f"/api/v1/elements/{element_id}/validation-rules",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"rule_type": "enum_set", "rule_value": {"values": ["M", "F", "O"]}},
        )
        assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"
        body = resp.json()
        assert "id" in body
        assert body["rule_type"] == "enum_set"

    async def test_duplicate_rule_type_returns_409(self, client, curator_token, element_with_source):
        """409 on second rule with same rule_type."""
        element_id, _ = element_with_source

        resp1 = await client.post(
            f"/api/v1/elements/{element_id}/validation-rules",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"rule_type": "range", "rule_value": {"min": 0, "max": 120}},
        )
        assert resp1.status_code == 201

        resp2 = await client.post(
            f"/api/v1/elements/{element_id}/validation-rules",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"rule_type": "range", "rule_value": {"min": 0, "max": 100}},
        )
        assert resp2.status_code == 409, f"Expected 409, got {resp2.status_code}: {resp2.text}"


class TestGetValidationRules:
    """T029 — GET /api/v1/elements/{id}/validation-rules"""

    async def test_get_rules_returns_active_rules(self, client, curator_token, element_with_source):
        """GET returns all active rules ordered by rule_type."""
        element_id, _ = element_with_source

        # Create two rules
        await client.post(
            f"/api/v1/elements/{element_id}/validation-rules",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"rule_type": "range", "rule_value": {"min": 0, "max": 120}},
        )
        await client.post(
            f"/api/v1/elements/{element_id}/validation-rules",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"rule_type": "type_constraint", "rule_value": {"type": "integer"}},
        )

        resp = await client.get(
            f"/api/v1/elements/{element_id}/validation-rules",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        assert resp.status_code == 200, f"Expected 200: {resp.text}"
        body = resp.json()
        assert "rules" in body
        rule_types = [r["rule_type"] for r in body["rules"]]
        assert "range" in rule_types
        assert "type_constraint" in rule_types

    async def test_get_rules_excludes_soft_deleted(self, client, curator_token, element_with_source):
        """Soft-deleted rules are excluded from GET."""
        element_id, _ = element_with_source

        # Create rule
        create_resp = await client.post(
            f"/api/v1/elements/{element_id}/validation-rules",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"rule_type": "enum_set", "rule_value": {"values": ["A", "B"]}},
        )
        assert create_resp.status_code == 201
        rule_id = create_resp.json()["id"]

        # Delete rule
        del_resp = await client.delete(
            f"/api/v1/elements/{element_id}/validation-rules/{rule_id}",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        assert del_resp.status_code == 200

        # Get rules — should be empty
        get_resp = await client.get(
            f"/api/v1/elements/{element_id}/validation-rules",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        assert get_resp.status_code == 200
        rules = get_resp.json()["rules"]
        assert not any(r["id"] == rule_id for r in rules)


class TestPutValidationRule:
    """T030 — PUT /api/v1/elements/{id}/validation-rules/{rule_id}"""

    async def test_narrow_enum_returns_breaking_true(self, client, curator_token, element_with_source):
        """Narrowing enum_set → breaking=true in change record."""
        element_id, _ = element_with_source

        create_resp = await client.post(
            f"/api/v1/elements/{element_id}/validation-rules",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"rule_type": "enum_set", "rule_value": {"values": ["M", "F", "O"]}},
        )
        assert create_resp.status_code == 201
        rule_id = create_resp.json()["id"]

        put_resp = await client.put(
            f"/api/v1/elements/{element_id}/validation-rules/{rule_id}",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"rule_value": {"values": ["M", "F"]}},
        )
        assert put_resp.status_code == 200, f"Expected 200: {put_resp.text}"
        body = put_resp.json()
        assert body["change"]["breaking"] is True
        assert body["change"]["old_value"] == {"values": ["M", "F", "O"]}
        assert body["change"]["new_value"] == {"values": ["M", "F"]}

    async def test_widen_range_returns_breaking_false(self, client, curator_token, element_with_source):
        """Widening range → breaking=false."""
        element_id, _ = element_with_source

        create_resp = await client.post(
            f"/api/v1/elements/{element_id}/validation-rules",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"rule_type": "range", "rule_value": {"min": 0, "max": 100}},
        )
        assert create_resp.status_code == 201
        rule_id = create_resp.json()["id"]

        put_resp = await client.put(
            f"/api/v1/elements/{element_id}/validation-rules/{rule_id}",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"rule_value": {"min": 0, "max": 150}},
        )
        assert put_resp.status_code == 200
        assert put_resp.json()["change"]["breaking"] is False


class TestDeleteValidationRule:
    """T031 — DELETE /api/v1/elements/{id}/validation-rules/{rule_id}"""

    async def test_delete_returns_breaking_false(self, client, curator_token, element_with_source):
        """DELETE returns breaking=false (relaxes constraints)."""
        element_id, _ = element_with_source

        create_resp = await client.post(
            f"/api/v1/elements/{element_id}/validation-rules",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"rule_type": "pattern", "rule_value": {"regex": "^[A-Z]+$"}},
        )
        assert create_resp.status_code == 201
        rule_id = create_resp.json()["id"]

        del_resp = await client.delete(
            f"/api/v1/elements/{element_id}/validation-rules/{rule_id}",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        assert del_resp.status_code == 200, f"Expected 200: {del_resp.text}"
        body = del_resp.json()
        assert body["breaking"] is False

    async def test_delete_removes_rule_from_list(self, client, curator_token, element_with_source):
        """After DELETE, rule absent from GET."""
        element_id, _ = element_with_source

        create_resp = await client.post(
            f"/api/v1/elements/{element_id}/validation-rules",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"rule_type": "cardinality", "rule_value": {"min_count": 1}},
        )
        assert create_resp.status_code == 201
        rule_id = create_resp.json()["id"]

        await client.delete(
            f"/api/v1/elements/{element_id}/validation-rules/{rule_id}",
            headers={"Authorization": f"Bearer {curator_token}"},
        )

        get_resp = await client.get(
            f"/api/v1/elements/{element_id}/validation-rules",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        assert get_resp.status_code == 200
        rules = get_resp.json()["rules"]
        assert not any(r["id"] == rule_id for r in rules)


class TestCascadeDeleteOnElementDelete:
    """T066 — ValidationRule cascade soft-delete when element is deleted."""

    async def test_rules_cascade_soft_deleted_when_element_deleted(
        self, client, curator_token
    ):
        """Deleting an element → all its active ValidationRules are soft-deleted."""
        src_resp = await client.post(
            "/api/v1/sources",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"name": f"cas-src-{__import__('uuid').uuid4()}", "format": "bids"},
        )
        assert src_resp.status_code == 201
        source_id = src_resp.json()["id"]

        el_resp = await client.post(
            "/api/v1/elements",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"name": f"cas-el-{__import__('uuid').uuid4()}", "data_type": "integer", "source_id": source_id},
        )
        assert el_resp.status_code == 201
        element_id = el_resp.json()["id"]

        rule_resp = await client.post(
            f"/api/v1/elements/{element_id}/validation-rules",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"rule_type": "range", "rule_value": {"min": 0, "max": 120}},
        )
        assert rule_resp.status_code == 201

        del_resp = await client.delete(
            f"/api/v1/elements/{element_id}",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        assert del_resp.status_code == 200

        # After element deletion, validation rules endpoint returns 404 (element gone)
        # OR rules should be gone — either behavior is acceptable
        get_resp = await client.get(
            f"/api/v1/elements/{element_id}/validation-rules",
            headers={"Authorization": f"Bearer {curator_token}"},
        )
        # Either 404 (element deleted) or 200 with empty/soft-deleted rules
        if get_resp.status_code == 200:
            rules = get_resp.json()["rules"]
            assert len(rules) == 0, f"Expected 0 active rules after element delete, got {rules}"
