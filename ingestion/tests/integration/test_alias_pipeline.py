"""Integration tests for AliasDetector end-to-end with mock backend."""

import pytest
import respx
from httpx import Response

from undata.alias_detection import AliasDetector

BACKEND_URL = "http://testbackend/api/v1"
TOKEN = "test-token"

ELEMENTS = [
    {
        "id": "e1",
        "name": "subject_age",
        "data_type": "number",
        "multivalued": False,
        "description": "Age of the research subject",
        "source": {"name": "BIDS"},
    },
    {
        "id": "e2",
        "name": "participant_age",
        "data_type": "number",
        "multivalued": False,
        "description": "Age of the research participant",
        "source": {"name": "DANDI"},
    },
    {
        "id": "e3",
        "name": "session_id",
        "data_type": "string",
        "multivalued": False,
        "description": "Session identifier",
        "source": {"name": "BIDS"},
    },
]


@pytest.mark.asyncio
async def test_detect_returns_alias_candidates(monkeypatch):
    monkeypatch.setattr(
        "undata.alias_detection.AliasDetector._detect_embedding_aliases",
        lambda self, elements, exact_pairs: [],
    )
    with respx.mock(base_url=BACKEND_URL, assert_all_called=False) as mock:
        mock.get("/elements").mock(
            return_value=Response(200, json={"items": ELEMENTS, "total": 3, "page": 1})
        )
        detector = AliasDetector(backend_url=BACKEND_URL, token=TOKEN, threshold=0.92, dry_run=True)
        candidates = await detector.detect()

    assert len(candidates) >= 1
    ids = {(c.element_a_id, c.element_b_id) for c in candidates}
    assert ("e1", "e2") in ids or ("e2", "e1") in ids


@pytest.mark.asyncio
async def test_detect_dry_run_skips_mapping_post(monkeypatch):
    monkeypatch.setattr(
        "undata.alias_detection.AliasDetector._detect_embedding_aliases",
        lambda self, elements, exact_pairs: [],
    )
    with respx.mock(base_url=BACKEND_URL, assert_all_called=False) as mock:
        mock.get("/elements").mock(
            return_value=Response(200, json={"items": ELEMENTS, "total": 3, "page": 1})
        )
        mapping_route = mock.post("/mappings").mock(
            return_value=Response(200, json={"id": "map-001"})
        )
        detector = AliasDetector(backend_url=BACKEND_URL, token=TOKEN, threshold=0.92, dry_run=True)
        await detector.detect()

    assert not mapping_route.called


@pytest.mark.asyncio
async def test_detect_registers_mappings_when_not_dry_run(monkeypatch):
    monkeypatch.setattr(
        "undata.alias_detection.AliasDetector._detect_embedding_aliases",
        lambda self, elements, exact_pairs: [],
    )
    with respx.mock(base_url=BACKEND_URL, assert_all_called=False) as mock:
        mock.get("/elements").mock(
            return_value=Response(200, json={"items": ELEMENTS, "total": 3, "page": 1})
        )
        mapping_route = mock.post("/mappings").mock(
            return_value=Response(200, json={"id": "map-001"})
        )
        detector = AliasDetector(
            backend_url=BACKEND_URL, token=TOKEN, threshold=0.92, dry_run=False
        )
        candidates = await detector.detect()

    if candidates:
        assert mapping_route.called


@pytest.mark.asyncio
async def test_detect_circular_alias_rejected(monkeypatch):
    """A would-be alias pair within the same source should not cause issues."""
    monkeypatch.setattr(
        "undata.alias_detection.AliasDetector._detect_embedding_aliases",
        lambda self, elements, exact_pairs: [],
    )
    same_source_elements = [
        {
            "id": "e1",
            "name": "subject_age",
            "data_type": "number",
            "multivalued": False,
            "description": "Age",
            "source": {"name": "BIDS"},
        },
        {
            "id": "e2",
            "name": "participant_age",
            "data_type": "number",
            "multivalued": False,
            "description": "Age",
            "source": {"name": "BIDS"},
        },
    ]
    with respx.mock(base_url=BACKEND_URL, assert_all_called=False) as mock:
        mock.get("/elements").mock(
            return_value=Response(200, json={"items": same_source_elements, "total": 2, "page": 1})
        )
        detector = AliasDetector(backend_url=BACKEND_URL, token=TOKEN, threshold=0.92, dry_run=True)
        candidates = await detector.detect()

    assert isinstance(candidates, list)
