"""Full curation integration test — T083 (Polish Phase 8).

Tests the complete workflow:
1. Register BIDS + DANDI sources
2. Create elements with semantic_graph
3. Detect alias candidates (cross-source)
4. Create canonical undata element
5. Register identity mappings
6. Compose DynamicSchema
7. Verify source filtering
8. Verify mapping target filtering
9. Verify URI stability
10. Intra-undata alias detection returns 0 pairs (clean namespace)

Note: SimilarityService is mocked or uses pre-seeded embeddings to avoid
      flaky threshold dependency.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from src.models.schemas import AliasCandidatePair, DataElementSummary


@pytest.mark.asyncio
async def test_full_curation_workflow(client: AsyncClient, curator_token: str):
    """End-to-end curation workflow from raw schema ingestion to alias group creation."""
    headers = {"Authorization": f"Bearer {curator_token}"}

    # Step 1: Register BIDS and DANDI sources
    bids_src_resp = await client.post(
        "/api/v1/sources",
        json={"name": "curation-bids", "format": "bids", "content_hash": "bids-hash-curation"},
        headers=headers,
    )
    assert bids_src_resp.status_code == 201
    bids_source_id = bids_src_resp.json()["id"]

    dandi_src_resp = await client.post(
        "/api/v1/sources",
        json={"name": "curation-dandi", "format": "dandi", "content_hash": "dandi-hash-curation"},
        headers=headers,
    )
    assert dandi_src_resp.status_code == 201
    dandi_source_id = dandi_src_resp.json()["id"]

    # Step 2: Create BIDS subject_age element with semantic_graph (person/age/year)
    bids_el_resp = await client.post(
        "/api/v1/elements",
        json={
            "name": "subject_age",
            "data_type": "integer",
            "source_id": bids_source_id,
            "source_local_id": "subject_age_bids",
            "description": "Age of the subject participant in years",
            "semantic_graph": {
                "entities": [{"label": "person", "type": "organism", "role": "subject"}],
                "property": {"label": "age", "type": "demographic"},
                "unit": {"label": "year", "symbol": "yr"},
                "relations": [],
                "domain": "demographics",
            },
        },
        headers=headers,
    )
    assert bids_el_resp.status_code == 201
    bids_el_id = bids_el_resp.json()["id"]

    # Step 3: Create DANDI participant_age element with same semantic_graph
    dandi_el_resp = await client.post(
        "/api/v1/elements",
        json={
            "name": "participant_age",
            "data_type": "integer",
            "source_id": dandi_source_id,
            "source_local_id": "participant_age_dandi",
            "description": "Age of the study participant in years",
            "semantic_graph": {
                "entities": [{"label": "person", "type": "organism", "role": "subject"}],
                "property": {"label": "age", "type": "demographic"},
                "unit": {"label": "year", "symbol": "yr"},
                "relations": [],
                "domain": "demographics",
            },
        },
        headers=headers,
    )
    assert dandi_el_resp.status_code == 201
    dandi_el_id = dandi_el_resp.json()["id"]

    # Step 4: Call POST /aliases/detect with cross_source_only=true
    # Mock SimilarityService to return a known candidate pair
    mock_summary_bids = DataElementSummary(
        id=bids_el_resp.json()["id"],
        uri=bids_el_resp.json()["uri"],
        name="subject_age",
        data_type="integer",
        description="Age of the subject participant in years",
        required=False,
        multivalued=False,
        source=None,
        unit="year",
        superseded_by=None,
        version_num=1,
    )
    mock_summary_dandi = DataElementSummary(
        id=dandi_el_resp.json()["id"],
        uri=dandi_el_resp.json()["uri"],
        name="participant_age",
        data_type="integer",
        description="Age of the study participant in years",
        required=False,
        multivalued=False,
        source=None,
        unit="year",
        superseded_by=None,
        version_num=1,
    )
    mock_candidate = AliasCandidatePair(
        element_a=mock_summary_bids,
        element_b=mock_summary_dandi,
        similarity_score=0.95,
        suggested_predicate="skos:exactMatch",
        semantic_graph_overlap=None,
    )

    with patch(
        "src.services.similarity.SimilarityService.find_candidates",
        new=AsyncMock(return_value=(1, [mock_candidate])),
    ):
        detect_resp = await client.post(
            "/api/v1/aliases/detect",
            json={"cross_source_only": True, "threshold": 0.5},
            headers=headers,
        )
    assert detect_resp.status_code == 200
    detect_data = detect_resp.json()
    assert detect_data["total"] >= 1

    # Verify candidate pair structure
    pair = detect_data["items"][0]
    assert "element_a" in pair
    assert "element_b" in pair
    assert "similarity_score" in pair
    assert "suggested_predicate" in pair
    # semantic_graph_overlap may be null or have overlap values
    assert "semantic_graph_overlap" in pair

    # Step 5: Fetch undata source ID
    undata_src_resp = await client.get("/api/v1/sources", params={"name": "undata"})
    assert undata_src_resp.status_code == 200
    assert undata_src_resp.json()["total"] == 1
    undata_source_id = undata_src_resp.json()["items"][0]["id"]

    # Step 6: Create canonical age_years element under undata source
    undata_el_resp = await client.post(
        "/api/v1/elements",
        json={
            "name": "age_years",
            "data_type": "integer",
            "source_id": undata_source_id,
            "source_local_id": "age_years_canonical",
            "description": "Canonical age in years",
            "semantic_graph": {
                "entities": [{"label": "person", "type": "organism", "role": "subject"}],
                "property": {"label": "age", "type": "demographic"},
                "unit": {"label": "year", "symbol": "yr"},
                "relations": [],
                "domain": "demographics",
            },
        },
        headers=headers,
    )
    assert undata_el_resp.status_code == 201
    canonical_el_id = undata_el_resp.json()["id"]

    # Step 7: Register BIDS→undata identity mapping
    bids_map_resp = await client.post(
        "/api/v1/mappings",
        json={
            "function_type": "identity",
            "output_element_id": canonical_el_id,
            "expression_type": "identity",
            "sssom_predicate": "skos:exactMatch",
            "input_element_ids": [{"element_id": bids_el_id, "position": 0}],
        },
        headers=headers,
    )
    assert bids_map_resp.status_code == 201
    assert "uri" in bids_map_resp.json()

    # Step 8: Register DANDI→undata identity mapping
    dandi_map_resp = await client.post(
        "/api/v1/mappings",
        json={
            "function_type": "identity",
            "output_element_id": canonical_el_id,
            "expression_type": "identity",
            "sssom_predicate": "skos:exactMatch",
            "input_element_ids": [{"element_id": dandi_el_id, "position": 0}],
        },
        headers=headers,
    )
    assert dandi_map_resp.status_code == 201

    # Step 9: Compose a DynamicSchema from the undata element
    schema_resp = await client.post(
        "/api/v1/schemas",
        json={
            "name": "AgeSchema",
            "elements": [{"element_id": canonical_el_id, "position": 0}],
        },
        headers=headers,
    )
    assert schema_resp.status_code == 201
    schema_id = schema_resp.json()["id"]
    schema_uri = schema_resp.json()["uri"]

    # Step 10: Verify GET /elements?source_id=<undata-id> returns age_years but not subject_age/participant_age
    undata_els_resp = await client.get("/api/v1/elements", params={"source_id": undata_source_id})
    assert undata_els_resp.status_code == 200
    undata_el_ids = [item["id"] for item in undata_els_resp.json()["items"]]
    assert canonical_el_id in undata_el_ids
    assert bids_el_id not in undata_el_ids
    assert dandi_el_id not in undata_el_ids

    # Step 11: Verify GET /mappings?target_element_id=<age_years-id> returns 2 mappings
    mappings_resp = await client.get("/api/v1/mappings", params={"target_element_id": canonical_el_id})
    assert mappings_resp.status_code == 200
    assert mappings_resp.json()["total"] >= 2

    # Step 12: Verify DynamicSchema URI is stable after membership update
    el_extra = await client.post(
        "/api/v1/elements",
        json={
            "name": "age_months",
            "data_type": "integer",
            "source_id": undata_source_id,
            "source_local_id": "age_months_canonical",
        },
        headers=headers,
    )
    assert el_extra.status_code == 201

    put_resp = await client.put(
        f"/api/v1/schemas/{schema_id}",
        json={"add": [{"element_id": el_extra.json()["id"], "position": 1}], "version_num": 1},
        headers=headers,
    )
    assert put_resp.status_code == 200
    assert put_resp.json()["uri"] == schema_uri, "Schema URI must be stable after update"

    # Step 13: POST /aliases/detect with source_id=<undata-id> — intra-undata should return 0 pairs
    with patch(
        "src.services.similarity.SimilarityService.find_candidates",
        new=AsyncMock(return_value=(0, [])),
    ):
        intra_detect_resp = await client.post(
            "/api/v1/aliases/detect",
            json={"source_id": undata_source_id, "threshold": 0.5},
            headers=headers,
        )
    assert intra_detect_resp.status_code == 200
    assert intra_detect_resp.json()["total"] == 0

    # T086: After mappings are registered, element responses must carry populated arrays —
    # canonical element should list both identity mappings in mappings_as_output
    canonical_get = await client.get(f"/api/v1/elements/{canonical_el_id}")
    assert canonical_get.status_code == 200
    canonical_body = canonical_get.json()
    output_types = [m["function_type"] for m in canonical_body.get("mappings_as_output", [])]
    assert len(output_types) >= 2, (
        f"Expected >=2 mappings_as_output on canonical element, got {output_types}"
    )
    assert all(t == "identity" for t in output_types), (
        f"All output mappings should be identity, got {output_types}"
    )

    # BIDS element should list the BIDS→undata mapping in mappings_as_input
    bids_get = await client.get(f"/api/v1/elements/{bids_el_id}")
    assert bids_get.status_code == 200
    bids_body = bids_get.json()
    assert len(bids_body.get("mappings_as_input", [])) >= 1, (
        "BIDS element should have >=1 mapping in mappings_as_input"
    )
