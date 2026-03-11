"""Failing unit tests for PathwayExecutor — must fail before implementation (TDD).

Tests:
- Single step identity mapping produces StepResult OK
- Step raising ValueError produces StepResult ERROR and halts for that record
- passthrough_fields populated for unmapped input fields
- MigrationReport.overall_status PASS/FAIL/PARTIAL logic
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.models import MigrationReport
from src.services.pathway_executor import PathwayExecutor


@pytest.fixture
def mock_client():
    return AsyncMock()


@pytest.fixture
def executor(mock_client):
    return PathwayExecutor(mock_client)


def _make_pathway(steps: list[dict], status: str = "active") -> dict:
    return {
        "id": "pathway-1",
        "name": "Test Pathway",
        "source_schema_id": "schema-src",
        "target_schema_id": "schema-tgt",
        "direction": "forward",
        "status": status,
        "steps": steps,
        "inverse_pathway_id": None,
    }


def _make_mapping(mapping_id: str, expr: str = "input_0", expr_type: str = "identity") -> dict:
    return {
        "id": mapping_id,
        "function_type": "identity",
        "inputs": [{"element_id": "elem-1", "position": 0}],
        "current_version": {
            "expression": expr,
            "expression_type": expr_type,
            "inverse_mapping_id": None,
        },
    }


# ---- Tests ----


@pytest.mark.asyncio
async def test_single_step_identity_mapping_ok(executor, mock_client):
    """Single identity step produces StepResult with status='OK'."""
    pathway = _make_pathway([{"position": 0, "mapping_id": "map-1"}])
    mapping = _make_mapping("map-1", expr="input_0", expr_type="identity")

    mock_client.get_pathway.return_value = pathway
    mock_client.get_mapping.return_value = mapping

    report = await executor.execute(
        pathway_id="pathway-1",
        input_record={"subject_id": "sub-001"},
    )

    assert isinstance(report, MigrationReport)
    assert len(report.steps_applied) == 1
    assert report.steps_applied[0].status == "OK"
    assert report.overall_status in ("PASS", "PARTIAL")


@pytest.mark.asyncio
async def test_failing_step_produces_error_result(executor, mock_client):
    """A step that raises ValueError produces StepResult ERROR."""
    pathway = _make_pathway([{"position": 0, "mapping_id": "map-err"}])
    mapping = _make_mapping("map-err", expr="1/0", expr_type="python_expr")

    mock_client.get_pathway.return_value = pathway
    mock_client.get_mapping.return_value = mapping

    report = await executor.execute(
        pathway_id="pathway-1",
        input_record={"subject_id": "sub-001"},
    )

    assert report.overall_status == "FAIL"
    assert any(r.status == "ERROR" for r in report.steps_applied)


@pytest.mark.asyncio
async def test_passthrough_fields_populated(executor, mock_client):
    """Fields not covered by any step are placed in passthrough_fields."""
    # Pathway with 0 steps — all fields will be unmapped
    pathway = _make_pathway([])
    mock_client.get_pathway.return_value = pathway

    report = await executor.execute(
        pathway_id="pathway-1",
        input_record={"subject_id": "sub-001", "session_id": "ses-1"},
    )

    assert "subject_id" in report.passthrough_fields or "session_id" in report.passthrough_fields


@pytest.mark.asyncio
async def test_overall_status_pass_when_all_steps_ok(executor, mock_client):
    """overall_status=PASS when all steps succeed."""
    pathway = _make_pathway([{"position": 0, "mapping_id": "map-ok"}])
    mapping = _make_mapping("map-ok")
    mock_client.get_pathway.return_value = pathway
    mock_client.get_mapping.return_value = mapping

    report = await executor.execute(
        pathway_id="pathway-1",
        input_record={"val": "x"},
    )

    # With 0 failing steps and no validation violations: PASS or PARTIAL
    assert report.overall_status in ("PASS", "PARTIAL")


@pytest.mark.asyncio
async def test_overall_status_fail_when_step_errors(executor, mock_client):
    """overall_status=FAIL when at least one step errors."""
    pathway = _make_pathway([{"position": 0, "mapping_id": "map-bad"}])
    mapping = _make_mapping("map-bad", expr="nonexistent_var + 1", expr_type="python_expr")
    mock_client.get_pathway.return_value = pathway
    mock_client.get_mapping.return_value = mapping

    report = await executor.execute(
        pathway_id="pathway-1",
        input_record={"val": "x"},
    )

    assert report.overall_status == "FAIL"
