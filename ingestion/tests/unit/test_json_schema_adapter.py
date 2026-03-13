"""Unit tests for GenericJSONSchemaAdapter — must FAIL before implementation (TDD)."""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path

import pytest

from undata.adapters.json_schema import GenericJSONSchemaAdapter
from undata.models import NormalizedElement, SchemaClassPayload

FIXTURE = Path(__file__).parent.parent / "fixtures" / "generic_schema_sample.json"
DANDI_FIXTURE = Path(__file__).parent.parent / "fixtures" / "dandi" / "releases" / "0.6.7"


@pytest.fixture
def adapter():
    a = GenericJSONSchemaAdapter()
    a.load_file(str(FIXTURE))
    return a


def test_load_file_returns_normalized_elements(adapter):
    elements = adapter.extract_elements()
    assert len(elements) > 0
    assert all(isinstance(e, NormalizedElement) for e in elements)


def test_elements_have_source_name_generic_json(adapter):
    elements = adapter.extract_elements()
    assert all(e.source_name == "generic-json" for e in elements)


def test_top_level_properties_extracted(adapter):
    elements = adapter.extract_elements()
    names = {e.name for e in elements}
    assert {"id", "count", "active", "status"}.issubset(names)


def test_data_types_correct(adapter):
    elements = adapter.extract_elements()
    by_name = {e.name: e for e in elements if e.source_local_id.startswith("SampleObject.")}
    assert by_name["id"].data_type == "string"
    assert by_name["count"].data_type == "number"
    assert by_name["active"].data_type == "boolean"


def test_enum_field_has_allowed_values(adapter):
    elements = adapter.extract_elements()
    status_els = [e for e in elements if e.name == "status"]
    assert status_els, "Expected 'status' element"
    assert status_els[0].allowed_values == ["active", "inactive"]


def test_required_field_marked(adapter):
    elements = adapter.extract_elements()
    id_els = [e for e in elements if e.name == "id"]
    assert id_els, "Expected 'id' element"
    assert id_els[0].required is True


def test_defs_entry_creates_class_payload(adapter):
    classes = adapter.extract_classes()
    class_names = {c.class_name for c in classes}
    assert "Address" in class_names


def test_defs_properties_extracted_as_elements(adapter):
    elements = adapter.extract_elements()
    slids = {e.source_local_id for e in elements}
    assert "Address.street" in slids
    assert "Address.city" in slids


def test_ref_resolved_no_raw_ref_string(adapter):
    elements = adapter.extract_elements()
    for e in elements:
        assert "$ref" not in e.data_type, (
            f"Element {e.name!r} has raw $ref in data_type: {e.data_type!r}"
        )


def test_load_file_empty_path_raises_value_error():
    a = GenericJSONSchemaAdapter()
    with pytest.raises(ValueError):
        a.load_file("")


def test_load_file_nonexistent_raises():
    a = GenericJSONSchemaAdapter()
    with pytest.raises((FileNotFoundError, OSError)):
        a.load_file("/nonexistent/does_not_exist_xyz.json")


def test_empty_schema_returns_empty_lists():
    a = GenericJSONSchemaAdapter()
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        json.dump({}, f)
        tmp_path = f.name
    a.load_file(tmp_path)
    assert a.extract_elements() == []
    assert a.extract_classes() == []


def test_get_version_info_has_content_hash(adapter):
    info = adapter.get_version_info()
    assert "content_hash" in info
    assert info["content_hash"]


def test_load_file_emits_info_log():
    """G1: load_file() must emit an INFO-level structured log (Constitution §IV).

    Adds a temporary in-memory handler to the logger so we don't depend on fd
    capture — the StreamHandler(sys.stderr) is initialized at module import time
    before pytest sets up any capture context, making capsys/capfd unreliable.
    """
    records: list[logging.LogRecord] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    _logger = logging.getLogger("undata.adapters.json_schema")
    prev_level = _logger.level
    _logger.setLevel(logging.INFO)
    cap = _Capture()
    _logger.addHandler(cap)
    try:
        a = GenericJSONSchemaAdapter()
        a.load_file(str(FIXTURE))
    finally:
        _logger.removeHandler(cap)
        _logger.setLevel(prev_level)

    msgs = " ".join(r.getMessage().lower() for r in records)
    assert "loaded" in msgs or "generic" in msgs or "json" in msgs, (
        f"Expected INFO log; got messages: {[r.getMessage() for r in records]}"
    )


@pytest.mark.skipif(
    not (DANDI_FIXTURE / "dandiset.json").exists(),
    reason="DANDI fixture not present — run scripts/fetch-schemas.sh first",
)
def test_load_dandi_dandiset_fixture():
    """G2, SC-001: GenericJSONSchemaAdapter works on real DANDI dandiset.json."""
    a = GenericJSONSchemaAdapter()
    a.load_file(str(DANDI_FIXTURE / "dandiset.json"))
    elements = a.extract_elements()
    assert len(elements) > 0, "Expected elements from DANDI dandiset.json"
    assert all(e.source_name == "generic-json" for e in elements)


# ── anyOf / complex-composition handling (US3 scenario 3 partial coverage) ────

ANYOF_FIXTURE = Path(__file__).parent.parent / "fixtures" / "anyof_schema_sample.json"


def test_anyof_schema_extracted_without_crash():
    """anyOf fields must not crash extraction — they degrade to data_type='string'."""
    a = GenericJSONSchemaAdapter()
    a.load_file(str(ANYOF_FIXTURE))
    elements = a.extract_elements()
    assert len(elements) > 0
    names = {e.name for e in elements}
    assert "simple_field" in names
    assert "union_field" in names
    assert "nullable_field" in names


def test_anyof_fields_degrade_to_string():
    """anyOf without a top-level 'type' key degrades to data_type='string' (no crash).

    NOTE: This is intentional type-coercion loss. US3 scenario 3 (fidelity < 1.0 with
    explicit warnings for anyOf) is deferred to a future feature (009-roundtrip-complex).
    """
    a = GenericJSONSchemaAdapter()
    a.load_file(str(ANYOF_FIXTURE))
    elements = a.extract_elements()
    by_name = {e.name: e for e in elements}
    assert by_name["union_field"].data_type == "string"
    assert by_name["nullable_field"].data_type == "string"


def test_roundtrip_anyof_schema_no_crash():
    """roundtrip_json_schema on anyOf schema must not crash — fidelity in [0, 1]."""
    from undata.roundtrip import roundtrip_json_schema

    result = roundtrip_json_schema(str(ANYOF_FIXTURE))
    assert 0.0 <= result.fidelity_score <= 1.0
    assert isinstance(result.missing_elements, list)
    assert isinstance(result.warnings, list)
