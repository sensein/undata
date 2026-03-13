"""Unit tests for BIDSAdapter — must FAIL before implementation."""

from pathlib import Path

import pytest

from undata.adapters.bids import BIDSAdapter
from undata.models import NormalizedElement, SchemaClassPayload

BIDS_FIXTURE = Path(__file__).parent.parent / "fixtures" / "bids_schema_sample.yaml"


@pytest.fixture
def bids_adapter(tmp_path):
    """BIDSAdapter loaded with the sample fixture."""
    from pathlib import Path

    fixture = Path(__file__).parent.parent / "fixtures" / "bids_schema_sample.yaml"
    adapter = BIDSAdapter()
    adapter.load(str(fixture))
    return adapter


def test_bids_adapter_returns_normalized_elements(bids_adapter):
    elements = bids_adapter.extract_elements()
    assert len(elements) > 0
    assert all(isinstance(e, NormalizedElement) for e in elements)


def test_bids_element_has_required_fields(bids_adapter):
    elements = bids_adapter.extract_elements()
    e = elements[0]
    assert e.name
    assert e.data_type in ("string", "number", "boolean", "object", "array")
    assert isinstance(e.description, str)
    assert e.source_name == "BIDS"
    assert e.source_local_id


def test_bids_enum_field_has_allowed_values(bids_adapter):
    elements = bids_adapter.extract_elements()
    sex = next((e for e in elements if "sex" in e.name.lower()), None)
    assert sex is not None, "Expected a 'sex' field with enum values"
    assert sex.allowed_values is not None
    assert len(sex.allowed_values) > 0


def test_bids_numeric_field_type(bids_adapter):
    elements = bids_adapter.extract_elements()
    age = next((e for e in elements if "age" in e.name.lower()), None)
    assert age is not None, "Expected an age field"
    assert age.data_type == "number"


def test_bids_version_info_has_content_hash(bids_adapter):
    info = bids_adapter.get_version_info()
    assert "content_hash" in info
    assert info["content_hash"]


# ── T006: load_file() tests ──────────────────────────────────────────────────


def test_bids_load_file_from_yaml():
    """load_file(yaml_path) + extract_elements('file') returns elements."""
    adapter = BIDSAdapter()
    adapter.load_file(str(BIDS_FIXTURE))
    elements = adapter.extract_elements("file")
    assert len(elements) > 0
    assert all(isinstance(e, NormalizedElement) for e in elements)


def test_bids_load_file_extract_classes_extraction_path():
    """extract_classes('file') uses extraction_path='file'."""
    adapter = BIDSAdapter()
    adapter.load_file(str(BIDS_FIXTURE))
    classes = adapter.extract_classes("file")
    assert len(classes) > 0
    assert all(isinstance(c, SchemaClassPayload) for c in classes)
    assert all(c.extraction_path == "file" for c in classes)


def test_bids_load_file_without_library(monkeypatch):
    """load_file() falls back to raw YAML when bidsschematools is absent."""
    import sys

    monkeypatch.setitem(sys.modules, "bidsschematools", None)
    monkeypatch.setitem(sys.modules, "bidsschematools.schema", None)
    adapter = BIDSAdapter()
    adapter.load_file(str(BIDS_FIXTURE))
    elements = adapter.extract_elements("file")
    assert len(elements) > 0


def test_bids_load_file_raises_value_error_on_empty_path():
    """load_file('') raises ValueError — use load_code() for bundled schema."""
    adapter = BIDSAdapter()
    with pytest.raises(ValueError):
        adapter.load_file("")


# ── T016: load_code() tests ──────────────────────────────────────────────────


def test_bids_load_code_returns_elements():
    """load_code() + extract_elements('code') returns BIDS fields via bidsschematools."""
    pytest.importorskip("bidsschematools")
    adapter = BIDSAdapter()
    adapter.load_code()
    elements = adapter.extract_elements("code")
    assert len(elements) > 0
    assert all(isinstance(e, NormalizedElement) for e in elements)


def test_bids_load_code_extract_classes_extraction_path():
    """extract_classes('code') uses extraction_path='code'."""
    pytest.importorskip("bidsschematools")
    from undata.models import SchemaClassPayload

    adapter = BIDSAdapter()
    adapter.load_code()
    classes = adapter.extract_classes("code")
    assert len(classes) > 0
    assert all(isinstance(c, SchemaClassPayload) for c in classes)
    assert all(c.extraction_path == "code" for c in classes)


def test_bids_load_code_raises_import_error(monkeypatch):
    """load_code() raises ImportError when bidsschematools is absent."""
    import sys

    monkeypatch.setitem(sys.modules, "bidsschematools", None)
    monkeypatch.setitem(sys.modules, "bidsschematools.schema", None)
    adapter = BIDSAdapter()
    with pytest.raises(ImportError, match="bidsschematools"):
        adapter.load_code()


# ── T027: extract_elements(mode="both") test ─────────────────────────────────


def test_bids_extract_elements_both_mode():
    """mode='both' with code (bidsschematools) + distinct file fixture returns merged elements."""
    pytest.importorskip("bidsschematools")
    adapter = BIDSAdapter()
    adapter.load_code()
    code_els = adapter.extract_elements("code")
    adapter.load_file(str(BIDS_FIXTURE))
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


# ── T007: Full vocabulary count + vocabulary_type annotation ─────────────────


def test_bids_load_code_full_vocabulary_count():
    """load_code() loads all 9 vocabulary types: ≥ 900 elements total (FR-017)."""
    pytest.importorskip("bidsschematools")
    adapter = BIDSAdapter()
    adapter.load_code()
    elements = adapter.extract_elements("code")
    assert len(elements) >= 900, (
        f"Expected ≥ 900 elements from all 9 vocabulary types, got {len(elements)}. "
        "load_code() may only be loading schema.objects.metadata (449 entries)."
    )


def test_bids_load_code_vocabulary_type_annotation():
    """Each element from load_code() has vocabulary_type in raw_metadata (FR-017)."""
    pytest.importorskip("bidsschematools")
    adapter = BIDSAdapter()
    adapter.load_code()
    elements = adapter.extract_elements("code")
    assert len(elements) > 0
    missing = [e.name for e in elements if "vocabulary_type" not in (e.raw_metadata or {})]
    assert not missing, (
        f"Elements missing raw_metadata['vocabulary_type']: {missing[:5]}... "
        "All elements must have vocabulary_type annotation."
    )


# ── T008: Sidecar-based class grouping ───────────────────────────────────────


def test_bids_extract_classes_uses_sidecar_groups():
    """extract_classes('code') returns modality-based sidecar groups, not _-split singletons.

    With schema.rules.sidecars: ~20-30 modality groups, each with multiple fields.
    With _-split heuristic: ~400+ singletons, most with 1 field.
    """
    pytest.importorskip("bidsschematools")
    adapter = BIDSAdapter()
    adapter.load_code()
    classes = adapter.extract_classes("code")
    # Sidecar-based: ~100-200 named groups. _-split singletons: 900+ (one per field).
    assert len(classes) <= 500, (
        f"Expected ≤ 500 sidecar groups, got {len(classes)}. "
        "Likely using _-split heuristic (creates ~900+ singletons for 1012 fields)."
    )
    assert len(classes) >= 15, f"Expected ≥ 15 sidecar groups, got {len(classes)}"
    # Sidecar groups each contain multiple fields; most singletons have only 1 element
    avg_elements = sum(len(c.element_source_local_ids) for c in classes) / len(classes)
    assert avg_elements >= 2, (
        f"Expected avg ≥ 2 elements per class (sidecar group), got {avg_elements:.1f}. "
        "Likely using _-split singleton heuristic."
    )
