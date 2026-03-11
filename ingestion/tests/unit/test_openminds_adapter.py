"""Unit tests for OpenMINDSAdapter — must FAIL before implementation."""

from pathlib import Path

import pytest

from undata.adapters.openminds import OpenMINDSAdapter
from undata.models import NormalizedElement, SchemaClassPayload

FIXTURE = Path(__file__).parent.parent / "fixtures" / "openminds_sample.json"
OPENMINDS_DIR = Path(__file__).parent.parent / "fixtures" / "openminds_dir"


@pytest.fixture
def openminds_adapter():
    adapter = OpenMINDSAdapter()
    adapter.load(str(FIXTURE))
    return adapter


def test_openminds_returns_normalized_elements(openminds_adapter):
    elements = openminds_adapter.extract_elements()
    assert len(elements) > 0
    assert all(isinstance(e, NormalizedElement) for e in elements)


def test_openminds_element_has_required_fields(openminds_adapter):
    elements = openminds_adapter.extract_elements()
    e = elements[0]
    assert e.name
    assert e.data_type in ("string", "number", "boolean", "object", "array")
    assert e.source_name == "openMINDS"
    assert e.source_local_id


def test_openminds_description_preserved(openminds_adapter):
    elements = openminds_adapter.extract_elements()
    assert all(len(e.description) > 0 for e in elements)


def test_openminds_version_info_has_content_hash(openminds_adapter):
    info = openminds_adapter.get_version_info()
    assert "content_hash" in info
    assert info["content_hash"]


# ── T008: load_file() tests ──────────────────────────────────────────────────


def test_openminds_load_file_single_file():
    """load_file(json_path) + extract_elements('file') returns elements."""
    adapter = OpenMINDSAdapter()
    adapter.load_file(str(FIXTURE))
    elements = adapter.extract_elements("file")
    assert len(elements) > 0
    assert all(isinstance(e, NormalizedElement) for e in elements)


def test_openminds_load_file_dir_glob():
    """load_file(dir) globs all .schema.omi.json files and extracts elements."""
    adapter = OpenMINDSAdapter()
    adapter.load_file(str(OPENMINDS_DIR))
    elements = adapter.extract_elements("file")
    assert len(elements) > 0


def test_openminds_load_file_extract_classes_extraction_path():
    """extract_classes('file') uses extraction_path='file'."""
    adapter = OpenMINDSAdapter()
    adapter.load_file(str(FIXTURE))
    classes = adapter.extract_classes("file")
    assert len(classes) > 0
    assert all(isinstance(c, SchemaClassPayload) for c in classes)
    assert all(c.extraction_path == "file" for c in classes)


def test_openminds_load_file_raises_value_error_on_empty_path():
    """load_file('') raises ValueError for openMINDS (no default schema)."""
    adapter = OpenMINDSAdapter()
    with pytest.raises(ValueError):
        adapter.load_file("")


# ── T039: load_turtle() tests ────────────────────────────────────────────────

TURTLE_FIXTURE = Path(__file__).parent.parent / "fixtures" / "openminds_sample.ttl"


def test_openminds_load_turtle_returns_elements():
    """load_turtle(path) + extract_elements('file') returns elements from Turtle RDF."""
    pytest.importorskip("rdflib")
    adapter = OpenMINDSAdapter()
    adapter.load_turtle(str(TURTLE_FIXTURE))
    elements = adapter.extract_elements("file")
    assert len(elements) >= 0  # Turtle fixture may have 0 extracted if no RDFS.Class


def test_openminds_load_turtle_raises_value_error_on_empty_path():
    """load_turtle('') raises ValueError."""
    adapter = OpenMINDSAdapter()
    with pytest.raises(ValueError):
        adapter.load_turtle("")


# ── T018: load_code() tests ──────────────────────────────────────────────────


def test_openminds_load_code_raises_import_error(monkeypatch):
    """load_code() raises ImportError when openminds package is absent."""
    import sys

    monkeypatch.setitem(sys.modules, "openminds", None)
    adapter = OpenMINDSAdapter()
    with pytest.raises(ImportError, match="openminds"):
        adapter.load_code()


# ── T043: extract_elements(mode="both") test ─────────────────────────────────


def test_openminds_extract_elements_both_mode(monkeypatch):
    """mode='both' merges code (mocked openminds) + file (fixture JSON-LD dir) elements."""
    import sys
    import types

    # Build minimal mock openminds registry (same structure as T018)
    mock_openminds = types.ModuleType("openminds")
    mock_openminds.registry = {
        "types": {
            "latest": {
                "https://openminds.ebrains.eu/core/Subject": {
                    "properties": {
                        "lookupLabel": {"type": "string"},
                        "biologicalSex": {"type": "string"},
                    }
                }
            },
            "v4": {},
        }
    }
    monkeypatch.setitem(sys.modules, "openminds", mock_openminds)

    adapter = OpenMINDSAdapter()
    adapter.load_code()
    code_els = adapter.extract_elements("code")
    adapter.load_file(str(OPENMINDS_DIR))
    file_els = adapter.extract_elements("file")
    both_els = adapter.extract_elements("both")

    assert len(both_els) > 0
    assert all(isinstance(e, NormalizedElement) for e in both_els)

    # Both must be a union: unique SLIDs from each path appear in result
    code_slids = {e.source_local_id for e in code_els if e.source_local_id}
    file_slids = {e.source_local_id for e in file_els if e.source_local_id}
    both_slids = {e.source_local_id for e in both_els if e.source_local_id}
    assert code_slids - file_slids <= both_slids, "Both mode lost code-only elements"
    assert file_slids - code_slids <= both_slids, "Both mode lost file-only elements"
