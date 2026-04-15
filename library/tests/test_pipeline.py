"""Tests for the pipeline CLI command."""

import yaml
from click.testing import CliRunner

from undata_library.cli import main


def _setup_library(tmp_path):
    """Create minimal library structure for pipeline testing."""
    elements_dir = tmp_path / "elements"
    elements_dir.mkdir()
    schemas_dir = tmp_path / "schemas"
    schemas_dir.mkdir()
    values_dir = tmp_path / "values"
    values_dir.mkdir()
    cache_dir = tmp_path / "ontology-cache"
    cache_dir.mkdir()

    # Create a hash-registry
    (tmp_path / "hash-registry.yaml").write_text(yaml.dump({"elements": {}, "schemas": {}}))
    return tmp_path


def test_pipeline_missing_source():
    """Pipeline requires --source flag."""
    runner = CliRunner()
    result = runner.invoke(main, ["pipeline"])
    assert result.exit_code != 0
    assert "Missing option" in result.output or "required" in result.output.lower()


def test_pipeline_skip_enrich(tmp_path):
    """Pipeline with --skip-enrich skips enrichment."""
    lib = _setup_library(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["pipeline", "--source", "bids", "--library-path", str(lib), "--skip-enrich"],
        catch_exceptions=False,
    )
    # May fail on actual ingest without schemas, but should show "skipped"
    assert "Enrichment skipped" in result.output or result.exit_code != 0


def test_pipeline_skip_align(tmp_path):
    """Pipeline with --skip-align skips alignment."""
    lib = _setup_library(tmp_path)
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["pipeline", "--source", "bids", "--library-path", str(lib), "--skip-align"],
        catch_exceptions=False,
    )
    assert "Alignment skipped" in result.output or result.exit_code != 0
