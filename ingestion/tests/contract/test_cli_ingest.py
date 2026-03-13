"""CLI contract tests for `undata ingest` — must FAIL before implementation."""

import json
from pathlib import Path

from typer.testing import CliRunner

from undata.cli import app

DANDI_FIXTURE_DIR = (
    Path(__file__).parent.parent / "fixtures" / "dandi" / "releases" / "0.6.7"
)

runner = CliRunner()


def test_ingest_dry_run_exits_zero(monkeypatch):
    """--dry-run with a known-small source should exit 0 and print element counts."""
    monkeypatch.setenv("UNDATA_TOKEN", "test-token")
    result = runner.invoke(
        app,
        ["ingest", "bids", "--dry-run", "--output-format", "text"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    assert "elements" in result.output.lower()


def test_ingest_json_output_format(monkeypatch):
    monkeypatch.setenv("UNDATA_TOKEN", "test-token")
    result = runner.invoke(
        app,
        ["ingest", "bids", "--dry-run", "--output-format", "json"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "results" in data
    assert "total_succeeded" in data


def test_ingest_missing_token_exits_nonzero():
    """Missing token without --dry-run should exit non-zero."""
    result = runner.invoke(app, ["ingest", "bids"])
    assert result.exit_code != 0


def test_ingest_file_mode_missing_path_exits_nonzero():
    """--extraction-mode=file without --source-path exits non-zero for path-required adapters."""
    result = runner.invoke(
        app,
        ["ingest", "bids", "--dry-run", "--extraction-mode", "file"],
    )
    assert result.exit_code != 0


def test_ingest_both_mode_missing_path_exits_nonzero():
    """--extraction-mode=both without --source-path exits non-zero for path-required adapters."""
    result = runner.invoke(
        app,
        ["ingest", "dandi", "--dry-run", "--extraction-mode", "both"],
    )
    assert result.exit_code != 0


def test_ingest_file_mode_dry_run_succeeds(monkeypatch):
    """SC-005: --extraction-mode file --source-path <dir> --dry-run exits 0 with elements."""
    monkeypatch.setenv("UNDATA_TOKEN", "test-token")
    result = runner.invoke(
        app,
        [
            "ingest",
            "dandi",
            "--dry-run",
            "--extraction-mode",
            "file",
            "--source-path",
            str(DANDI_FIXTURE_DIR),
            "--output-format",
            "json",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["total_succeeded"] > 0
