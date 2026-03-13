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


# ── T011: $defs extraction from JSON Schema files ────────────────────────────


def test_dandi_load_file_extracts_defs_elements():
    """load_file() extracts elements from $defs entries that have properties (FR-019)."""
    adapter = DANDIAdapter()
    adapter.load_file(str(DANDI_FIXTURE_DIR))
    elements = adapter.extract_elements("file")
    # dandiset.json has $defs.Person with name/email/schemaKey properties
    # Without $defs extraction, only top-level properties are captured
    # Person.name or similar $defs-derived element must appear
    defs_elements = [e for e in elements if "." in (e.source_local_id or "")
                     and e.source_local_id.split(".")[0] not in ("Dandiset", "Asset")]
    assert len(defs_elements) > 0, (
        "Expected elements from $defs entries (e.g. Person.name, Person.email). "
        "load_file() may not be extracting $defs yet (FR-019)."
    )


def test_dandi_load_file_defs_creates_class_payloads():
    """load_file() creates SchemaClassPayload for each $defs entry with properties (FR-019)."""
    adapter = DANDIAdapter()
    adapter.load_file(str(DANDI_FIXTURE_DIR))
    classes = adapter.extract_classes("file")
    class_names = {c.class_name for c in classes}
    # dandiset.json has $defs.Person with properties
    assert "Person" in class_names, (
        f"Expected 'Person' class from $defs extraction, got: {sorted(class_names)}. "
        "extract_classes('file') may not be generating SchemaClassPayload for $defs."
    )


# ── T012: Self-referencing Pydantic model fallback ───────────────────────────


def test_dandi_load_code_self_ref_model_fallback():
    """load_code() falls back to model.model_fields for models returning 0 properties (FR-020)."""

    # Create a mock dandischema module with a self-referencing model
    import pydantic

    class SelfRefModel(pydantic.BaseModel):
        name: str = "test"
        value: int = 0

    # Patch model_json_schema to return empty properties (simulating $ref recursion)
    SelfRefModel.model_json_schema = classmethod(  # type: ignore[method-assign]
        lambda cls, **kw: {"title": "SelfRefModel", "properties": {}}
    )

    adapter = DANDIAdapter()
    # Load only our mock model
    adapter._models = [SelfRefModel]

    elements = adapter.extract_elements("code")

    # Without fallback: 0 elements (model_json_schema returns empty properties)
    # With fallback to model.model_fields: should get 'name' and 'value'
    field_names = {e.name for e in elements}
    assert "name" in field_names or "value" in field_names, (
        f"Expected elements from model.model_fields fallback, got: {field_names}. "
        "load_code() must fall back to model.model_fields when model_json_schema returns 0 props."
    )
