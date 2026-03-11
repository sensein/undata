"""CLI contract tests for `undata detect-aliases`."""

import respx
from httpx import Response
from typer.testing import CliRunner

from undata.cli import app

runner = CliRunner()

ELEMENTS = [
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
        "source": {"name": "DANDI"},
    },
]


def test_detect_aliases_dry_run_exits_zero(monkeypatch):
    monkeypatch.setenv("UNDATA_TOKEN", "test-token")
    monkeypatch.setattr(
        "undata.alias_detection.AliasDetector._detect_embedding_aliases",
        lambda self, elements, exact_pairs: [],
    )
    with respx.mock(base_url="http://localhost:8002/api/v1", assert_all_called=False) as mock:
        mock.get("/elements").mock(
            return_value=Response(200, json={"items": ELEMENTS, "total": 2, "page": 1})
        )
        result = runner.invoke(app, ["detect-aliases", "--dry-run"], catch_exceptions=False)

    assert result.exit_code == 0


def test_detect_aliases_sssom_output(monkeypatch):
    monkeypatch.setenv("UNDATA_TOKEN", "test-token")
    monkeypatch.setattr(
        "undata.alias_detection.AliasDetector._detect_embedding_aliases",
        lambda self, elements, exact_pairs: [],
    )
    with respx.mock(base_url="http://localhost:8002/api/v1", assert_all_called=False) as mock:
        mock.get("/elements").mock(
            return_value=Response(200, json={"items": ELEMENTS, "total": 2, "page": 1})
        )
        result = runner.invoke(
            app,
            ["detect-aliases", "--dry-run", "--output-format", "sssom-tsv"],
            catch_exceptions=False,
        )

    assert result.exit_code == 0
    # SSSOM TSV should have a header line
    lines = result.output.strip().splitlines()
    assert any(
        "subject_id" in line or "predicate_id" in line or "object_id" in line for line in lines
    ), f"No SSSOM header found. Output: {result.output}"


def test_detect_aliases_dry_run_does_not_call_mappings(monkeypatch):
    monkeypatch.setenv("UNDATA_TOKEN", "test-token")
    monkeypatch.setattr(
        "undata.alias_detection.AliasDetector._detect_embedding_aliases",
        lambda self, elements, exact_pairs: [],
    )
    with respx.mock(base_url="http://localhost:8002/api/v1", assert_all_called=False) as mock:
        mock.get("/elements").mock(
            return_value=Response(200, json={"items": ELEMENTS, "total": 2, "page": 1})
        )
        mappings_route = mock.post("/mappings").mock(return_value=Response(200, json={"id": "m1"}))
        runner.invoke(app, ["detect-aliases", "--dry-run"], catch_exceptions=False)

    assert not mappings_route.called
