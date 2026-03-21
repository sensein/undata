"""Tests for workflow engine and output validation."""

import yaml

from undata_library.models import WorkflowSpec
from undata_library.validation import validate_ingestion_output


# -- WorkflowSpec parsing tests --


def test_workflow_spec_parses():
    spec = WorkflowSpec.model_validate(
        {
            "sources": [{"path": "schemas/bids", "adapter": "bids"}],
            "classification": {"overrides": {"units": "valueset"}, "confidence_threshold": 0.8},
            "validation": {"strict": True, "checks": ["data_type_valid"]},
        }
    )
    assert len(spec.sources) == 1
    assert spec.classification.overrides == {"units": "valueset"}
    assert spec.validation.strict is True


def test_workflow_spec_defaults():
    spec = WorkflowSpec.model_validate({})
    assert spec.sources == []
    assert spec.classification.confidence_threshold == 0.7
    assert spec.docker.enabled is False


# -- Validation tests --


def _make_library(tmp_path, elements=None, schemas=None):
    """Create a minimal library for validation."""
    elem_dir = tmp_path / "elements"
    elem_dir.mkdir()
    if elements:
        for name, data in elements.items():
            (elem_dir / name).write_text(yaml.dump(data, default_flow_style=False))

    schema_dir = tmp_path / "schemas"
    schema_dir.mkdir()
    if schemas:
        for name, data in schemas.items():
            (schema_dir / name).write_text(yaml.dump(data, default_flow_style=False))

    return tmp_path


def test_validation_catches_invalid_data_type(tmp_path):
    _make_library(
        tmp_path,
        elements={
            "bad_abc123456789.yaml": {
                "semantic": {"data_type": "INVALID"},
                "provenance": [{"source": "test", "class": "X", "name": "bad"}],
            },
        },
    )
    violations = validate_ingestion_output(tmp_path)
    assert len(violations) == 1
    assert violations[0]["check"] == "data_type_valid"


def test_validation_catches_sha256_mismatch(tmp_path):
    _make_library(
        tmp_path,
        elements={
            "age_abc123456789.yaml": {
                "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
                "semantic": {"data_type": "string"},
                "provenance": [{"source": "test", "class": "X", "name": "age"}],
            },
        },
    )
    violations = validate_ingestion_output(tmp_path)
    assert any(v["check"] == "sha256_integrity" for v in violations)


def test_validation_catches_schema_no_properties(tmp_path):
    _make_library(
        tmp_path,
        schemas={
            "empty_abc123456789.yaml": {
                "semantic": {"properties": []},
                "provenance": [{"source": "test", "name": "empty"}],
            },
        },
    )
    violations = validate_ingestion_output(tmp_path)
    assert any(v["check"] == "schema_has_properties" for v in violations)


def test_validation_passes_clean_library(tmp_path):
    from undata_library.hashing import canonical_json, compute_sha256

    sem = {"data_type": "string"}
    sha = compute_sha256(canonical_json(sem))
    _make_library(
        tmp_path,
        elements={
            "age_abc123456789.yaml": {
                "sha256": sha,
                "semantic": sem,
                "provenance": [{"source": "test", "class": "X", "name": "age"}],
            },
        },
    )
    violations = validate_ingestion_output(tmp_path)
    assert len(violations) == 0
