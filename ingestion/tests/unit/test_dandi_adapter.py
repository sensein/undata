"""Unit tests for DANDIAdapter — must FAIL before implementation."""

from pathlib import Path

import pytest

from undata.adapters.dandi import DANDIAdapter
from undata.models import NormalizedElement, SchemaClassPayload

DANDI_FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "dandi" / "releases" / "0.6.7"


@pytest.fixture
def dandi_adapter():
    """DANDIAdapter using dandischema.models introspection."""
    adapter = DANDIAdapter()
    adapter.load("")  # DANDI uses introspection; path unused
    return adapter


def test_dandi_adapter_returns_normalized_elements(dandi_adapter):
    elements = dandi_adapter.extract_elements()
    assert len(elements) > 0
    assert all(isinstance(e, NormalizedElement) for e in elements)


def test_dandi_element_has_required_fields(dandi_adapter):
    elements = dandi_adapter.extract_elements()
    e = elements[0]
    assert e.name
    assert e.data_type in ("string", "number", "boolean", "object", "array")
    assert e.source_name == "DANDI"
    assert e.source_local_id


def test_dandi_array_field_multivalued(dandi_adapter):
    elements = dandi_adapter.extract_elements()
    array_elements = [e for e in elements if e.multivalued]
    assert len(array_elements) > 0, "Expected at least one multivalued (array) field from DANDI"


def test_dandi_version_info_has_content_hash(dandi_adapter):
    info = dandi_adapter.get_version_info()
    assert "content_hash" in info
    assert info["content_hash"]


# ── T005: load_file() tests ──────────────────────────────────────────────────


def test_dandi_load_file_returns_elements():
    """load_file(dir) + extract_elements('file') returns NormalizedElements."""
    adapter = DANDIAdapter()
    adapter.load_file(str(DANDI_FIXTURE_DIR))
    elements = adapter.extract_elements("file")
    assert len(elements) > 0
    assert all(isinstance(e, NormalizedElement) for e in elements)
    assert all(e.source_name == "DANDI" for e in elements)


def test_dandi_load_file_extract_classes_extraction_path():
    """extract_classes('file') uses extraction_path='file'."""
    adapter = DANDIAdapter()
    adapter.load_file(str(DANDI_FIXTURE_DIR))
    classes = adapter.extract_classes("file")
    assert len(classes) > 0
    assert all(isinstance(c, SchemaClassPayload) for c in classes)
    assert all(c.extraction_path == "file" for c in classes)


def test_dandi_load_file_schema_format_json():
    """extract_classes('file') sets schema_format='json' for JSON Schema files."""
    adapter = DANDIAdapter()
    adapter.load_file(str(DANDI_FIXTURE_DIR))
    classes = adapter.extract_classes("file")
    assert all(c.schema_format == "json" for c in classes)


def test_dandi_load_file_raises_value_error_on_empty_path():
    """load_file('') raises ValueError — use load_code() for introspection."""
    adapter = DANDIAdapter()
    with pytest.raises(ValueError):
        adapter.load_file("")


# ── T015: load_code() tests ──────────────────────────────────────────────────


def test_dandi_load_code_returns_elements():
    """load_code() + extract_elements('code') returns dandischema model fields."""
    pytest.importorskip("dandischema")
    adapter = DANDIAdapter()
    adapter.load_code()
    elements = adapter.extract_elements("code")
    assert len(elements) > 0
    assert all(isinstance(e, NormalizedElement) for e in elements)
    assert all(e.source_name == "DANDI" for e in elements)


def test_dandi_load_code_extract_classes_extraction_path():
    """extract_classes('code') uses extraction_path='code', schema_format='code'."""
    pytest.importorskip("dandischema")
    adapter = DANDIAdapter()
    adapter.load_code()
    classes = adapter.extract_classes("code")
    assert len(classes) > 0
    assert all(c.extraction_path == "code" for c in classes)
    assert all(c.schema_format == "code" for c in classes)


# ── T026: extract_elements(mode="both") test ─────────────────────────────────


def test_dandi_extract_elements_both_mode():
    """mode='both' merges code + file elements; contains all elements from both paths."""
    pytest.importorskip("dandischema")
    adapter = DANDIAdapter()
    adapter.load_code()
    code_els = adapter.extract_elements("code")
    adapter.load_file(str(DANDI_FIXTURE_DIR))
    file_els = adapter.extract_elements("file")
    both_els = adapter.extract_elements("both")

    assert len(both_els) > 0
    assert all(isinstance(e, NormalizedElement) for e in both_els)

    # "both" must be a union: unique SLIDs from each path must all appear in result
    code_slids = {e.source_local_id for e in code_els if e.source_local_id}
    file_slids = {e.source_local_id for e in file_els if e.source_local_id}
    both_slids = {e.source_local_id for e in both_els if e.source_local_id}
    unique_code = code_slids - file_slids
    unique_file = file_slids - code_slids
    assert unique_code.issubset(both_slids), "Both mode lost code-only elements"
    assert unique_file.issubset(both_slids), "Both mode lost file-only elements"
