"""Shared test fixtures for migration-api tests."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

import pytest
import respx
from httpx import ASGITransport, AsyncClient

from src.main import app


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """AsyncClient wired to the FastAPI app under test."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_backend():
    """respx mock fixture for BackendClient calls to 002-schema-backend."""
    with respx.mock(base_url="http://backend:8002", assert_all_called=False) as mock:
        yield mock


# ---- Sample data fixtures ----

SAMPLE_ELEMENT_ID_1 = str(uuid.uuid4())
SAMPLE_ELEMENT_ID_2 = str(uuid.uuid4())
SAMPLE_ELEMENT_ID_3 = str(uuid.uuid4())

SAMPLE_SOURCE_SCHEMA_ID = str(uuid.uuid4())
SAMPLE_TARGET_SCHEMA_ID = str(uuid.uuid4())
SAMPLE_MAPPING_ID_A = str(uuid.uuid4())
SAMPLE_MAPPING_ID_B = str(uuid.uuid4())


@pytest.fixture
def sample_element():
    return {
        "id": SAMPLE_ELEMENT_ID_1,
        "name": "subject_id",
        "data_type": "string",
        "description": "Subject identifier",
        "source_local_id": "Subject.id",
        "source_name": "BIDS",
    }


@pytest.fixture
def sample_pathway_request():
    return {
        "name": "BIDS-to-DANDI",
        "source_schema_id": SAMPLE_SOURCE_SCHEMA_ID,
        "target_schema_id": SAMPLE_TARGET_SCHEMA_ID,
        "direction": "forward",
        "steps": [
            {"position": 0, "mapping_id": SAMPLE_MAPPING_ID_A},
        ],
    }


@pytest.fixture
def sample_pathway():
    pathway_id = str(uuid.uuid4())
    return {
        "id": pathway_id,
        "name": "BIDS-to-DANDI",
        "source_schema_id": SAMPLE_SOURCE_SCHEMA_ID,
        "target_schema_id": SAMPLE_TARGET_SCHEMA_ID,
        "direction": "forward",
        "status": "active",
        "steps": [
            {"position": 0, "mapping_id": SAMPLE_MAPPING_ID_A},
        ],
        "inverse_pathway_id": None,
        "version_num": 0,
    }


@pytest.fixture
def sample_schema_request():
    return {
        "name": "TestSchema",
        "version": "2026.03.0",
        "classes": [
            {
                "name": "SubjectMetadata",
                "element_ids": [SAMPLE_ELEMENT_ID_1, SAMPLE_ELEMENT_ID_2],
            }
        ],
        "save": False,
    }
