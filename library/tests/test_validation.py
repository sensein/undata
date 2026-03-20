"""Tests for v2 YAML validation."""

from pathlib import Path

from undata_library.validation import validate_directory, validate_file

FIXTURES = Path(__file__).parent / "fixtures"


class TestValidateFile:
    def test_valid_element_passes(self):
        report = validate_file(FIXTURES / "valid-element-v2.yaml")
        assert report.valid, f"Violations: {report.violations}"

    def test_valid_schema_passes(self):
        report = validate_file(FIXTURES / "valid-schema-v2.yaml")
        assert report.valid, f"Violations: {report.violations}"

    def test_missing_data_type_fails(self):
        report = validate_file(FIXTURES / "invalid-element-no-datatype.yaml")
        assert not report.valid
        fields = [v.field for v in report.violations]
        assert any("data_type" in f for f in fields)

    def test_bad_enum_fails(self):
        report = validate_file(FIXTURES / "invalid-element-bad-enum.yaml")
        assert not report.valid

    def test_multi_provenance_passes(self):
        report = validate_file(FIXTURES / "multi-provenance-element.yaml")
        assert report.valid

    def test_nonexistent_file(self):
        report = validate_file(Path("/nonexistent.yaml"))
        assert not report.valid


class TestValidateDirectory:
    def test_scans_all_fixtures(self):
        reports = validate_directory(FIXTURES)
        assert len(reports) == 8  # 4 element + 2 value + 2 invalid

    def test_mixed_valid_invalid(self):
        reports = validate_directory(FIXTURES)
        valid = [r for r in reports if r.valid]
        invalid = [r for r in reports if not r.valid]
        assert (
            len(valid) == 6
        )  # valid-element, valid-element-rich, valid-schema, multi-prov-element, valid-value, multi-prov-value
        assert len(invalid) == 2  # no-datatype, bad-enum
