"""Unit tests for LinkMLAdapter — must FAIL before implementation (TDD)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from undata.adapters.linkml_adapter import LinkMLAdapter
from undata.models import NormalizedElement, SchemaClassPayload

FIXTURE = Path(__file__).parent.parent / "fixtures" / "linkml_sample.yaml"


@pytest.fixture
def adapter():
    a = LinkMLAdapter()
    a.load_file(str(FIXTURE))
    return a


def test_load_file_returns_elements(adapter):
    elements = adapter.extract_elements()
    assert len(elements) > 0
    assert all(isinstance(e, NormalizedElement) for e in elements)


def test_elements_have_source_name_linkml(adapter):
    elements = adapter.extract_elements()
    assert all(e.source_name == "linkml" for e in elements)


def test_slots_extracted_by_name(adapter):
    elements = adapter.extract_elements()
    names = {e.name for e in elements}
    assert {"name", "age", "active", "tags"}.issubset(names)


def test_data_types_correct(adapter):
    elements = adapter.extract_elements()
    by_name = {e.name: e for e in elements}
    assert by_name["name"].data_type == "string"
    assert by_name["age"].data_type == "number"
    assert by_name["active"].data_type == "boolean"


def test_multivalued_slot_is_array(adapter):
    elements = adapter.extract_elements()
    by_name = {e.name: e for e in elements}
    assert by_name["tags"].data_type == "array"
    assert by_name["tags"].multivalued is True


def test_required_slot_marked(adapter):
    elements = adapter.extract_elements()
    by_name = {e.name: e for e in elements}
    assert by_name["name"].required is True
    assert by_name["age"].required is False


def test_source_local_id_format(adapter):
    elements = adapter.extract_elements()
    slids = {e.source_local_id for e in elements}
    assert "test_schema.name" in slids
    assert "test_schema.age" in slids


def test_classes_extracted(adapter):
    classes = adapter.extract_classes()
    assert len(classes) > 0
    assert all(isinstance(c, SchemaClassPayload) for c in classes)


def test_class_names_correct(adapter):
    classes = adapter.extract_classes()
    names = {c.class_name for c in classes}
    assert {"Person", "Dataset"}.issubset(names)


def test_class_schema_format_yaml(adapter):
    classes = adapter.extract_classes()
    assert all(c.schema_format == "yaml" for c in classes)


def test_class_element_source_local_ids(adapter):
    classes = adapter.extract_classes()
    by_name = {c.class_name: c for c in classes}
    person = by_name["Person"]
    assert "test_schema.name" in person.element_source_local_ids
    assert "test_schema.age" in person.element_source_local_ids


def test_load_file_empty_path_raises():
    a = LinkMLAdapter()
    with pytest.raises(ValueError):
        a.load_file("")


def test_load_file_nonexistent_raises():
    a = LinkMLAdapter()
    with pytest.raises((FileNotFoundError, OSError, Exception)):
        a.load_file("/nonexistent/does_not_exist_xyz.yaml")


def test_get_version_info_has_content_hash(adapter):
    info = adapter.get_version_info()
    assert "content_hash" in info
    assert info["content_hash"]


def test_get_version_info_version_tag(adapter):
    info = adapter.get_version_info()
    # Fixture version is "0.1.0"
    assert info["version_tag"] == "0.1.0"


def test_load_file_emits_info_log():
    """G1: load_file() must emit an INFO-level structured log (Constitution §IV)."""
    records: list[logging.LogRecord] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    _logger = logging.getLogger("undata.adapters.linkml_adapter")
    prev_level = _logger.level
    _logger.setLevel(logging.INFO)
    cap = _Capture()
    _logger.addHandler(cap)
    try:
        a = LinkMLAdapter()
        a.load_file(str(FIXTURE))
    finally:
        _logger.removeHandler(cap)
        _logger.setLevel(prev_level)

    msgs = " ".join(r.getMessage().lower() for r in records)
    assert "loaded" in msgs or "linkml" in msgs or "yaml" in msgs, (
        f"Expected INFO log; got messages: {[r.getMessage() for r in records]}"
    )
