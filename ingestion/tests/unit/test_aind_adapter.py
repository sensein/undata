"""Unit tests for AINDAdapter — must FAIL before implementation (TDD)."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "aind"


@pytest.fixture()
def adapter():
    from undata.adapters.aind import AINDAdapter

    return AINDAdapter()


def test_aind_adapter_source_name(adapter):
    """AINDAdapter must report source_name='aind' and source_format='json-schema'."""
    assert adapter.source_name == "aind"
    assert adapter.source_format == "json-schema"


def test_aind_adapter_extract_elements_from_fixtures(adapter):
    """extract_elements() with bundled fixtures yields >0 NormalizedElements with source_name='aind'."""  # noqa: E501
    from undata.models import NormalizedElement

    adapter.load(str(FIXTURES_DIR))
    elements = adapter.extract_elements()

    assert len(elements) > 0
    assert all(isinstance(e, NormalizedElement) for e in elements)
    assert all(e.source_name == "aind" for e in elements)


def test_aind_adapter_required_flag(adapter):
    """Fields listed in JSON Schema 'required' array are marked required=True."""
    adapter.load(str(FIXTURES_DIR))
    elements = adapter.extract_elements()

    # subject_id is required in subject_schema.json
    subject_id_elements = [e for e in elements if e.name == "subject_id"]
    assert subject_id_elements, "Expected at least one 'subject_id' element"
    # At least one should be required
    assert any(e.required for e in subject_id_elements)


def test_aind_adapter_description_preserved(adapter):
    """Properties with descriptions have non-empty description in NormalizedElement."""
    adapter.load(str(FIXTURES_DIR))
    elements = adapter.extract_elements()

    # subject_id has a description in subject_schema.json
    subject_id_el = next((e for e in elements if e.name == "subject_id" and e.description), None)
    assert subject_id_el is not None, "subject_id should have a description"
    assert "subject" in subject_id_el.description.lower()


def test_aind_adapter_content_hash_stable(adapter):
    """get_version_info()['content_hash'] is stable across two calls with same fixtures."""
    adapter.load(str(FIXTURES_DIR))
    info1 = adapter.get_version_info()
    info2 = adapter.get_version_info()
    assert info1["content_hash"] == info2["content_hash"]
    assert len(info1["content_hash"]) == 64  # SHA-256 hex


def test_aind_adapter_data_type_mapping(adapter):
    """String JSON Schema types map to 'string' data_type in NormalizedElement."""
    adapter.load(str(FIXTURES_DIR))
    elements = adapter.extract_elements()

    # subject_id should be string type
    subject_id_el = next((e for e in elements if e.name == "subject_id"), None)
    assert subject_id_el is not None
    assert subject_id_el.data_type == "string"


# ── T009: load_file() tests ──────────────────────────────────────────────────


def test_aind_load_file_from_dir():
    """load_file(dir_path) + extract_elements('file') returns elements."""
    from undata.adapters.aind import AINDAdapter
    from undata.models import NormalizedElement

    a = AINDAdapter()
    a.load_file(str(FIXTURES_DIR))
    elements = a.extract_elements("file")
    assert len(elements) > 0
    assert all(isinstance(e, NormalizedElement) for e in elements)


def test_aind_load_file_extract_classes_extraction_path():
    """extract_classes('file') uses extraction_path='file'."""
    from undata.adapters.aind import AINDAdapter
    from undata.models import SchemaClassPayload

    a = AINDAdapter()
    a.load_file(str(FIXTURES_DIR))
    classes = a.extract_classes("file")
    assert len(classes) > 0
    assert all(isinstance(c, SchemaClassPayload) for c in classes)
    assert all(c.extraction_path == "file" for c in classes)


def test_aind_load_file_default_uses_bundled_fixtures():
    """load_file('') uses default fixtures dir — no ValueError for AIND."""
    from undata.adapters.aind import AINDAdapter

    a = AINDAdapter()
    a.load_file("")  # must NOT raise
    elements = a.extract_elements("file")
    assert len(elements) > 0


# ── T019: load_code() ImportError tests ─────────────────────────────────────


def test_aind_load_code_raises_import_error_absent(monkeypatch):
    """load_code() raises ImportError when aind_data_schema is not installed."""
    import sys

    from undata.adapters.aind import AINDAdapter

    monkeypatch.setitem(sys.modules, "aind_data_schema", None)
    monkeypatch.setitem(sys.modules, "aind_data_schema.core", None)
    a = AINDAdapter()
    with pytest.raises(ImportError) as exc_info:
        a.load_code()
    assert "aind" in str(exc_info.value).lower()


def test_aind_load_code_raises_import_error_pyo3(monkeypatch):
    """load_code() raises ImportError for pyo3-ffi C-extension failure (Python 3.14)."""
    import sys

    from undata.adapters.aind import AINDAdapter

    # Simulate pyo3 C-extension ImportError
    monkeypatch.setitem(
        sys.modules,
        "aind_data_schema",
        None,
    )
    a = AINDAdapter()
    with pytest.raises(ImportError) as exc_info:
        a.load_code()
    assert "aind" in str(exc_info.value).lower()


# ── T044: extract_elements(mode="both") graceful degradation ─────────────────


def test_aind_extract_elements_both_mode_graceful_fallback(monkeypatch, caplog):
    """Both-mode falls back to file-only with WARN when load_code() raises ImportError.

    Simulates Python 3.14 environment where aind_data_schema is unavailable.
    All returned elements must have extraction_path='file' (not 'code').
    """
    import logging
    import sys

    from undata.adapters.aind import AINDAdapter
    from undata.models import NormalizedElement

    # Simulate aind_data_schema being absent (Python 3.14 / bridge venv unavailable)
    monkeypatch.setitem(sys.modules, "aind_data_schema", None)
    monkeypatch.setitem(sys.modules, "aind_data_schema.core", None)

    a = AINDAdapter()
    a.load_file(str(FIXTURES_DIR))

    with caplog.at_level(logging.WARNING, logger="undata.adapters.aind"):
        both_els = a.extract_elements("both")

    # Must return file-only elements (non-empty)
    assert len(both_els) > 0
    assert all(isinstance(e, NormalizedElement) for e in both_els)

    # All elements must come from file path (no code elements since load_code failed)
    for el in both_els:
        assert el.extraction_path in ("file", "both"), (
            f"Unexpected extraction_path={el.extraction_path!r} on {el.source_local_id}"
        )

    # WARN log must be emitted
    warn_records = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any("aind" in r.message.lower() or "both" in r.message.lower() for r in warn_records), (
        "Expected WARNING about code-path unavailability in both-mode"
    )


# ── T022: Extended AIND fixtures test (skipif schemas not present) ─────────--


AIND_EXTENDED_SCHEMAS_DIR = Path(__file__).parent.parent.parent.parent / "schemas" / "aind"


@pytest.mark.skipif(
    not AIND_EXTENDED_SCHEMAS_DIR.exists(),
    reason="Run `bash scripts/fetch-schemas.sh` first to download extended AIND fixtures",
)
def test_aind_load_file_extended_schemas():
    """load_file(path) loads ≥ 20 elements from extended AIND JSON Schema files in schemas/aind/.

    Requires `bash ingestion/scripts/fetch-schemas.sh` to populate schemas/aind/ first.
    """
    from undata.adapters.aind import AINDAdapter

    adapter = AINDAdapter()
    adapter.load_file(str(AIND_EXTENDED_SCHEMAS_DIR))
    elements = adapter.extract_elements("file")
    assert len(elements) >= 20, (
        f"Expected ≥ 20 elements from extended AIND schemas in {AIND_EXTENDED_SCHEMAS_DIR}, "
        f"got {len(elements)}."
    )
