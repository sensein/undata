"""Unit tests for ValidationService."""

import pytest

from undata.validation import ValidationService

MINIMAL_SCHEMA_YAML = """
id: https://test.org/schema
name: TestSchema
prefixes:
  linkml: https://w3id.org/linkml/
default_range: string
classes:
  TestRecord:
    slots:
      - subject_id
      - subject_age
      - sex
slots:
  subject_id:
    range: string
    required: true
  subject_age:
    range: float
    required: false
  sex:
    range: SexEnum
    required: false
enums:
  SexEnum:
    permissible_values:
      male: {}
      female: {}
      other: {}
"""


@pytest.fixture
def svc(tmp_path):
    schema_file = tmp_path / "schema.yaml"
    schema_file.write_text(MINIMAL_SCHEMA_YAML)
    return ValidationService(schema_path=str(schema_file), target_class="TestRecord")


def test_conformant_record_passes(svc):
    record = {"subject_id": "sub-01", "subject_age": 28.0, "sex": "male"}
    report = svc.validate(record)
    assert report["status"] == "PASS"
    assert report["violations"] == []


def test_missing_required_field_fails(svc):
    record = {"subject_age": 28.0}  # missing required subject_id
    report = svc.validate(record)
    assert report["status"] == "FAIL"
    violations = report["violations"]
    assert len(violations) > 0
    assert any(v["severity"] == "ERROR" for v in violations)
    assert any("subject_id" in v["field"] for v in violations)


def test_invalid_enum_value_fails(svc):
    record = {"subject_id": "sub-01", "sex": "unknown_value"}
    report = svc.validate(record)
    assert report["status"] == "FAIL"
    violations = report["violations"]
    assert any("sex" in v["field"] for v in violations)


def test_report_includes_json_export(svc):
    import json

    record = {"subject_id": "sub-01"}
    report = svc.validate(record)
    json_str = svc.to_json(report)
    parsed = json.loads(json_str)
    assert "status" in parsed
    assert "violations" in parsed


def test_report_includes_text_export(svc):
    record = {}  # all fields missing
    report = svc.validate(record)
    text = svc.to_text(report)
    assert "FAIL" in text or "PASS" in text
