"""Tests for version diff engine."""

import json
from pathlib import Path

from click.testing import CliRunner

from undata_library.cli import main
from undata_library.diff import diff_file, diff_versions
from undata_library.models import ElementRecord

FIXTURES = Path(__file__).parent / "fixtures"


class TestDiffVersions:
    def test_multi_version_shows_changes(self):
        diffs = diff_file(FIXTURES / "multi-version-element.yaml")
        # v2→v3: description changed, constraints unchanged
        field_names = [d.field for d in diffs]
        assert "description" in field_names

    def test_specific_version_range(self):
        diffs = diff_file(FIXTURES / "multi-version-element.yaml", from_version=1, to_version=2)
        field_names = [d.field for d in diffs]
        # v1→v2: description changed + constraints added
        assert "description" in field_names
        assert "constraints" in field_names

    def test_single_version_no_diff(self):
        diffs = diff_file(FIXTURES / "valid-element.yaml")
        assert len(diffs) == 0  # only 1 version

    def test_breaking_flag_from_changelog(self):
        diffs = diff_file(FIXTURES / "multi-version-element.yaml", from_version=1, to_version=2)
        # v2 changelog has breaking: true
        breaking = [d for d in diffs if d.breaking]
        assert len(breaking) > 0

    def test_nonbreaking_diff(self):
        diffs = diff_file(FIXTURES / "multi-version-element.yaml", from_version=2, to_version=3)
        # v3 changelog has breaking: false
        breaking = [d for d in diffs if d.breaking]
        assert len(breaking) == 0


class TestDiffCLI:
    def test_text_format(self):
        runner = CliRunner()
        result = runner.invoke(
            main, ["diff", str(FIXTURES / "multi-version-element.yaml")]
        )
        assert result.exit_code == 0
        assert "description" in result.output

    def test_json_format(self):
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["diff", str(FIXTURES / "multi-version-element.yaml"), "--format", "json"],
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) > 0
        assert "field" in data[0]

    def test_single_version_message(self):
        runner = CliRunner()
        result = runner.invoke(
            main, ["diff", str(FIXTURES / "valid-element.yaml")]
        )
        assert result.exit_code == 0
        assert "No differences" in result.output
