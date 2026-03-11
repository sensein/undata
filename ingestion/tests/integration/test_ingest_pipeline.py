"""Integration tests for IngestionPipeline using respx mock backend."""

import pytest
import respx
from httpx import Response

from undata.ingestion import IngestionPipeline
from undata.models import IngestionResult, NormalizedElement

BACKEND_URL = "http://testbackend/api/v1"
TOKEN = "test-token-abc"

SAMPLE_ELEMENTS = [
    NormalizedElement(
        name="subject_age",
        data_type="number",
        description="Age of subject",
        required=False,
        multivalued=False,
        allowed_values=None,
        constraints={},
        source_local_id="subject_age",
        source_name="BIDS",
    ),
    NormalizedElement(
        name="session_id",
        data_type="string",
        description="Session identifier",
        required=False,
        multivalued=False,
        allowed_values=None,
        constraints={},
        source_local_id="session_id",
        source_name="BIDS",
    ),
]


@pytest.mark.asyncio
async def test_pipeline_submits_elements_to_backend():
    with respx.mock(base_url=BACKEND_URL) as mock:
        mock.post("/sources").mock(
            return_value=Response(
                200,
                json={"id": "src-001", "name": "BIDS", "uri": "http://localhost/schema/src-001"},
            )
        )
        mock.post("/elements/bulk").mock(
            return_value=Response(
                200,
                json={"succeeded": 2, "failed": 0, "failures": []},
            )
        )

        pipeline = IngestionPipeline(backend_url=BACKEND_URL, token=TOKEN)
        result = await pipeline.ingest(
            source_name="BIDS",
            source_format="yaml",
            elements=SAMPLE_ELEMENTS,
            version_info={"version_tag": "1.9.0", "content_hash": "abc123"},
        )

    assert isinstance(result, IngestionResult)
    assert result.elements_succeeded == 2
    assert result.elements_failed == 0
    assert result.source_name == "BIDS"


@pytest.mark.asyncio
async def test_pipeline_dry_run_skips_backend():
    with respx.mock(base_url=BACKEND_URL, assert_all_called=False) as mock:
        mock.post("/sources").mock(return_value=Response(200, json={}))
        mock.post("/elements/bulk").mock(return_value=Response(200, json={}))

        pipeline = IngestionPipeline(backend_url=BACKEND_URL, token=TOKEN)
        result = await pipeline.ingest(
            source_name="BIDS",
            source_format="yaml",
            elements=SAMPLE_ELEMENTS,
            version_info={"version_tag": "1.9.0", "content_hash": "abc123"},
            dry_run=True,
        )

    assert result.elements_submitted == 2
    assert result.elements_succeeded == 2
    assert mock.calls.call_count == 0


@pytest.mark.asyncio
async def test_pipeline_reports_partial_failures():
    with respx.mock(base_url=BACKEND_URL) as mock:
        mock.post("/sources").mock(
            return_value=Response(200, json={"id": "src-001", "name": "BIDS", "uri": "http://x"})
        )
        mock.post("/elements/bulk").mock(
            return_value=Response(
                200,
                json={
                    "succeeded": 1,
                    "failed": 1,
                    "failures": [{"index": 1, "error": "duplicate", "element_name": "session_id"}],
                },
            )
        )

        pipeline = IngestionPipeline(backend_url=BACKEND_URL, token=TOKEN)
        result = await pipeline.ingest(
            source_name="BIDS",
            source_format="yaml",
            elements=SAMPLE_ELEMENTS,
            version_info={"version_tag": "1.9.0", "content_hash": "abc123"},
        )

    assert result.elements_succeeded == 1
    assert result.elements_failed == 1
    assert len(result.failures) == 1
