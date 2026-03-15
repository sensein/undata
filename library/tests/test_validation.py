"""Tests for YAML validation against library schema."""

from pathlib import Path

import pytest

from undata_library.validation import validate_directory, validate_file

FIXTURES = Path(__file__).parent / "fixtures"


class TestValidateFile:
    def test_valid_element_passes(self):
        report = validate_file(FIXTURES / "valid-element.yaml")
        assert report.valid, f"Expected valid, got violations: {report.violations}"

    def test_valid_mapping_passes(self):
        report = validate_file(FIXTURES / "valid-mapping.yaml")
        assert report.valid, f"Expected valid, got violations: {report.violations}"

    def test_multi_version_element_passes(self):
        report = validate_file(FIXTURES / "multi-version-element.yaml")
        assert report.valid, f"Expected valid, got violations: {report.violations}"

    def test_missing_field_fails(self):
        report = validate_file(FIXTURES / "invalid-element-missing-field.yaml")
        assert not report.valid
        fields = [v.field for v in report.violations]
        assert any("source_local_id" in f for f in fields), (
            f"Expected source_local_id violation, got: {fields}"
        )

    def test_bad_enum_fails(self):
        report = validate_file(FIXTURES / "invalid-element-bad-enum.yaml")
        assert not report.valid
        messages = [v.message for v in report.violations]
        assert any("data_type" in m.lower() or "input" in m.lower() for m in messages), (
            f"Expected data_type enum violation, got: {messages}"
        )

    def test_nonexistent_file(self):
        report = validate_file(Path("/nonexistent/file.yaml"))
        assert not report.valid

    def test_invalid_yaml_syntax(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("{{invalid yaml::")
        report = validate_file(bad)
        assert not report.valid


class TestValidateDirectory:
    def test_scans_all_fixtures(self):
        reports = validate_directory(FIXTURES)
        assert len(reports) == 5  # 5 fixture files

    def test_mixed_valid_invalid(self):
        reports = validate_directory(FIXTURES)
        valid = [r for r in reports if r.valid]
        invalid = [r for r in reports if not r.valid]
        assert len(valid) == 3  # valid-element, valid-mapping, multi-version
        assert len(invalid) == 2  # missing-field, bad-enum
