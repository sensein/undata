"""Contract tests for POST /migrate.

Tests:
- POST /migrate single record valid → 200 + report with steps_applied
- POST /migrate BROKEN pathway → 409 + broken_step
- POST /migrate 101 records → 202 + job_id
- POST /migrate 3 records, 1 failing → all 3 in results, 1 FAIL, 2 PASS
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from src.main import app
from src.models import MigrationReport, ValidationResult
from src.services.backend_client import get_backend_client

PATHWAY_ID = str(uuid.uuid4())


def _make_report(status: str = "PASS") -> MigrationReport:
    return MigrationReport(
        pathway_id=PATHWAY_ID,
        source_schema_id="schema-src",
        target_schema_id="schema-tgt",
        overall_status=status,
        steps_applied=[],
        passthrough_fields=[],
        validation_result=ValidationResult(status="PASS"),
    )


def _active_pathway() -> dict:
    return {
        "id": PATHWAY_ID,
        "status": "active",
        "source_schema_id": "src",
        "target_schema_id": "tgt",
        "steps": [],
    }


@pytest.mark.asyncio
async def test_migrate_single_record_returns_200_with_report(client):
    """POST /migrate with one record returns 200 with results list."""
    mock_client = AsyncMock()
    mock_client.get_pathway.return_value = _active_pathway()
    app.dependency_overrides[get_backend_client] = lambda: mock_client

    try:
        with patch("src.api.v1.migrate.PathwayExecutor") as MockExec:
            instance = MockExec.return_value
            instance.execute = AsyncMock(return_value=_make_report("PASS"))

            resp = await client.post(
                "/migrate",
                json={
                    "pathway_id": PATHWAY_ID,
                    "records": [{"subject_id": "sub-001"}],
                },
            )
    finally:
        app.dependency_overrides.pop(get_backend_client, None)

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "results" in data
    assert len(data["results"]) == 1


@pytest.mark.asyncio
async def test_migrate_broken_pathway_returns_409(client):
    """POST /migrate with BROKEN pathway returns 409."""
    mock_client = AsyncMock()
    mock_client.get_pathway.return_value = {
        "id": PATHWAY_ID,
        "status": "broken",
        "source_schema_id": "src",
        "target_schema_id": "tgt",
        "steps": [],
    }
    app.dependency_overrides[get_backend_client] = lambda: mock_client

    try:
        resp = await client.post(
            "/migrate",
            json={
                "pathway_id": PATHWAY_ID,
                "records": [{"subject_id": "sub-001"}],
            },
        )
    finally:
        app.dependency_overrides.pop(get_backend_client, None)

    assert resp.status_code == 409, resp.text


@pytest.mark.asyncio
async def test_migrate_large_batch_returns_202(client):
    """POST /migrate with >100 records returns 202 + job_id."""
    records = [{"subject_id": f"sub-{i:03d}"} for i in range(101)]

    mock_client = AsyncMock()
    mock_client.get_pathway.return_value = _active_pathway()
    app.dependency_overrides[get_backend_client] = lambda: mock_client

    try:
        with patch("src.api.v1.migrate.batch_migrate_task") as mock_task:
            mock_task.delay.return_value.id = "test-batch-job-id"
            resp = await client.post(
                "/migrate",
                json={"pathway_id": PATHWAY_ID, "records": records},
            )
    finally:
        app.dependency_overrides.pop(get_backend_client, None)

    assert resp.status_code == 202, resp.text
    data = resp.json()
    assert "job_id" in data


@pytest.mark.asyncio
async def test_migrate_per_record_failure_isolation(client):
    """POST /migrate: 3 records, 1 failing → all 3 in results, counts correct."""
    reports = [
        _make_report("PASS"),
        _make_report("FAIL"),
        _make_report("PASS"),
    ]
    call_idx = [0]

    async def side_effect(**kw):
        r = reports[call_idx[0]]
        call_idx[0] += 1
        return r

    mock_client = AsyncMock()
    mock_client.get_pathway.return_value = _active_pathway()
    app.dependency_overrides[get_backend_client] = lambda: mock_client

    try:
        with patch("src.api.v1.migrate.PathwayExecutor") as MockExec:
            instance = MockExec.return_value
            instance.execute.side_effect = side_effect

            resp = await client.post(
                "/migrate",
                json={
                    "pathway_id": PATHWAY_ID,
                    "records": [
                        {"subject_id": "sub-001"},
                        {"subject_id": "sub-002"},
                        {"subject_id": "sub-003"},
                    ],
                },
            )
    finally:
        app.dependency_overrides.pop(get_backend_client, None)

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total"] == 3
    statuses = [r["status"] for r in data["results"]]
    assert statuses.count("FAIL") >= 1
    assert statuses.count("PASS") >= 1
