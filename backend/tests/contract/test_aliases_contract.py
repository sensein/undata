"""Contract tests for alias group and detection endpoints — T051.

Tests MUST FAIL before T061 (aliases router) is implemented.
"""

from __future__ import annotations

from uuid import uuid4

import pytest


@pytest.fixture()
async def cross_source_elements(client, curator_token):
    """Create elements from two different sources for cross-source alias testing."""
    elements = []
    for i in range(2):
        src_resp = await client.post(
            "/api/v1/sources",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"name": f"alias-src-{i}-{uuid4()}", "format": "bids"},
        )
        assert src_resp.status_code == 201
        source = src_resp.json()

        el_resp = await client.post(
            "/api/v1/elements",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "name": "age",
                "data_type": "integer",
                "source_id": source["id"],
                "description": "Age of participant in years",
                "semantic_graph": {
                    "entities": [{"label": "Participant", "type": "Person", "role": "subject", "external_uri": None}],
                    "property": {"label": "age", "type": "numeric", "external_uri": None},
                    "unit": {"label": "year", "symbol": "yr", "external_uri": None},
                    "relations": [],
                    "domain": "neuroscience",
                },
            },
        )
        assert el_resp.status_code == 201
        elements.append(el_resp.json())

    return elements


class TestAliasesContract:
    async def test_post_aliases_returns_201(self, client, curator_token, cross_source_elements):
        """POST /aliases returns 201 and identity mappings are created."""
        elements = cross_source_elements

        response = await client.post(
            "/api/v1/aliases",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={
                "element_ids": [e["id"] for e in elements],
                "sssom_predicate": "skos:exactMatch",
                "confidence": 0.95,
            },
        )
        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"

    async def test_detect_aliases_returns_paginated_pair_list(self, client, curator_token, cross_source_elements):
        """POST /aliases/detect returns PaginatedList[AliasCandidatePair]."""
        response = await client.post(
            "/api/v1/aliases/detect",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"cross_source_only": False, "threshold": 0.0, "limit": 50},
        )
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        body = response.json()
        assert "total" in body
        assert "items" in body

        for item in body.get("items", []):
            assert "element_a" in item
            assert "element_b" in item
            assert "similarity_score" in item
            assert "suggested_predicate" in item

    async def test_detect_cross_source_only_returns_cross_source_pairs(self, client, curator_token, cross_source_elements):
        """POST /aliases/detect with cross_source_only=true returns only cross-source pairs."""
        response = await client.post(
            "/api/v1/aliases/detect",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"cross_source_only": True, "threshold": 0.0, "limit": 50},
        )
        assert response.status_code == 200
        # All returned pairs must be from different sources
        for item in response.json().get("items", []):
            if item.get("element_a") and item.get("element_b"):
                source_a = item["element_a"].get("source", {}).get("id") if item["element_a"].get("source") else None
                source_b = item["element_b"].get("source", {}).get("id") if item["element_b"].get("source") else None
                if source_a and source_b:
                    assert source_a != source_b, "cross_source_only should only return cross-source pairs"

    async def test_detect_alias_pair_includes_semantic_graph_overlap(self, client, curator_token, cross_source_elements):
        """AliasCandidatePair includes semantic_graph_overlap with correct field types."""
        response = await client.post(
            "/api/v1/aliases/detect",
            headers={"Authorization": f"Bearer {curator_token}"},
            json={"cross_source_only": False, "threshold": 0.0, "limit": 50},
        )
        assert response.status_code == 200

        for item in response.json().get("items", []):
            overlap = item.get("semantic_graph_overlap")
            if overlap is not None:
                assert isinstance(overlap.get("property_match"), bool), "property_match must be bool"
                assert isinstance(overlap.get("unit_match"), bool), "unit_match must be bool"
                assert isinstance(overlap.get("entity_labels_match"), bool), "entity_labels_match must be bool"
                domain_match = overlap.get("domain_match")
                assert isinstance(domain_match, (bool, type(None))), (
                    f"domain_match must be bool | None, got {type(domain_match)}"
                )
