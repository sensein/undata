"""Unit tests for NWBAdapter — must FAIL before implementation."""

from pathlib import Path

import pytest

from undata.adapters.nwb import NWBAdapter
from undata.models import NormalizedElement, SchemaClassPayload

FIXTURE = Path(__file__).parent.parent / "fixtures" / "nwb_schema_sample.yaml"


@pytest.fixture
def nwb_adapter():
    adapter = NWBAdapter()
    adapter.load(str(FIXTURE))
    return adapter


def test_nwb_returns_normalized_elements(nwb_adapter):
    elements = nwb_adapter.extract_elements()
    assert len(elements) > 0
    assert all(isinstance(e, NormalizedElement) for e in elements)


def test_nwb_element_has_required_fields(nwb_adapter):
    elements = nwb_adapter.extract_elements()
    e = elements[0]
    assert e.name
    assert e.data_type in ("string", "number", "boolean", "object", "array")
    assert e.source_name == "NWB"
    assert e.source_local_id


def test_nwb_required_field_flag(nwb_adapter):
    elements = nwb_adapter.extract_elements()
    required = [e for e in elements if e.required]
    assert len(required) > 0, "Expected at least one required field in NWB fixture"


def test_nwb_version_info_has_content_hash(nwb_adapter):
    info = nwb_adapter.get_version_info()
    assert "content_hash" in info
    assert info["content_hash"]


# ── T007: load_file() tests ──────────────────────────────────────────────────


def test_nwb_load_file_from_yaml():
    """load_file(yaml_path) + extract_elements('file') returns elements."""
    adapter = NWBAdapter()
    adapter.load_file(str(FIXTURE))
    elements = adapter.extract_elements("file")
    assert len(elements) > 0
    assert all(isinstance(e, NormalizedElement) for e in elements)


def test_nwb_load_file_extract_classes_extraction_path():
    """extract_classes('file') uses extraction_path='file'."""
    adapter = NWBAdapter()
    adapter.load_file(str(FIXTURE))
    classes = adapter.extract_classes("file")
    assert len(classes) > 0
    assert all(isinstance(c, SchemaClassPayload) for c in classes)
    assert all(c.extraction_path == "file" for c in classes)


def test_nwb_load_file_from_url(monkeypatch):
    """load_file(http://...) fetches YAML content via httpx."""
    import httpx

    content = FIXTURE.read_text()

    class _MockResponse:
        text = content

        def raise_for_status(self):
            pass

    monkeypatch.setattr(httpx, "get", lambda url, **kw: _MockResponse())
    adapter = NWBAdapter()
    adapter.load_file("http://example.com/nwb_schema.yaml")
    elements = adapter.extract_elements("file")
    assert len(elements) > 0


def test_nwb_load_file_raises_value_error_on_empty_path():
    """load_file('') raises ValueError — use load_code() for pynwb introspection."""
    adapter = NWBAdapter()
    with pytest.raises(ValueError):
        adapter.load_file("")


# ── T017: load_code() tests ──────────────────────────────────────────────────


def test_nwb_load_code_with_mocked_pynwb(monkeypatch):
    """load_code() with a mocked pynwb type map returns NWB type groups."""
    import sys
    import types

    # Build minimal mock pynwb + hdmf NamespaceCatalog
    mock_pynwb = types.ModuleType("pynwb")

    mock_spec = {
        "neurodata_type_def": "NWBContainer",
        "doc": "A mock NWB container",
        "attributes": [{"name": "description", "dtype": "text", "doc": "Description"}],
        "datasets": [],
    }

    class MockGroupSpec:
        def to_dict(self):
            return mock_spec

    class MockNamespace:
        def get_registered_types(self):
            return ["NWBContainer"]

        def get_spec(self, dt):
            return MockGroupSpec()

    class MockCatalog:
        def get_namespace_names(self):
            return ["core"]

        def get_namespace(self, name):
            return MockNamespace()

    class MockTypeMap:
        namespace_catalog = MockCatalog()

    mock_pynwb.get_type_map = lambda: MockTypeMap()
    monkeypatch.setitem(sys.modules, "pynwb", mock_pynwb)

    # Mock hdmf.spec.GroupSpec
    mock_hdmf_spec = types.ModuleType("hdmf.spec")
    mock_hdmf_spec.GroupSpec = MockGroupSpec
    mock_hdmf = types.ModuleType("hdmf")
    monkeypatch.setitem(sys.modules, "hdmf", mock_hdmf)
    monkeypatch.setitem(sys.modules, "hdmf.spec", mock_hdmf_spec)

    adapter = NWBAdapter()
    adapter.load_code()
    elements = adapter.extract_elements("code")
    assert len(elements) > 0


def test_nwb_load_code_raises_import_error(monkeypatch):
    """load_code() raises ImportError when pynwb is not installed."""
    import sys

    monkeypatch.setitem(sys.modules, "pynwb", None)
    adapter = NWBAdapter()
    with pytest.raises(ImportError, match="pynwb"):
        adapter.load_code()


# ── T042: extract_elements(mode="both") test ─────────────────────────────────


NWB_NAMESPACE_DIR = Path(__file__).parent.parent / "fixtures" / "nwb_namespace_sample"


# ── T015: Directory detection of namespace YAML ──────────────────────────────


def test_nwb_load_file_directory_detects_namespace():
    """load_file(directory) detects *.namespace.yaml and loads all referenced domain YAMLs."""
    adapter = NWBAdapter()
    adapter.load_file(str(NWB_NAMESPACE_DIR))
    elements = adapter.extract_elements("file")
    assert len(elements) > 0, (
        "Expected elements after loading namespace directory. "
        "load_file(dir) must detect *.namespace.yaml and traverse namespaces[].doc[].source."
    )
    names = {e.name for e in elements}
    assert "data" in names or "timestamps" in names, (
        f"Expected 'data' or 'timestamps' from test.types.yaml, got: {names}. "
        "Namespace traversal may not be loading domain YAML files."
    )


# ── T016: Namespace YAML path traversal ──────────────────────────────────────


def test_nwb_load_file_namespace_yaml_traversal():
    """load_file(namespace.yaml) traverses namespaces[].doc[].source (NOT catalog)."""
    namespace_yaml = NWB_NAMESPACE_DIR / "test.namespace.yaml"
    adapter = NWBAdapter()
    adapter.load_file(str(namespace_yaml))
    elements = adapter.extract_elements("file")
    assert len(elements) > 0, (
        "Expected elements after loading namespace YAML path. "
        "load_file(namespace.yaml) must parse namespaces[].doc[].source key."
    )
    names = {e.name for e in elements}
    assert "data" in names or "timestamps" in names, (
        f"Expected 'data' or 'timestamps' from test.types.yaml, got: {names}."
    )


# ── T017: parent_class_name from neurodata_type_inc ──────────────────────────


def test_nwb_extract_classes_parent_class_name_from_namespace():
    """extract_classes() after namespace load emits parent_class_name from neurodata_type_inc."""
    namespace_yaml = NWB_NAMESPACE_DIR / "test.namespace.yaml"
    adapter = NWBAdapter()
    adapter.load_file(str(namespace_yaml))
    classes = adapter.extract_classes("file")
    test_ts = next((c for c in classes if c.class_name == "TestTimeSeries"), None)
    assert test_ts is not None, (
        f"Expected 'TestTimeSeries' class after namespace traversal, got: "
        f"{[c.class_name for c in classes]}."
    )
    assert test_ts.parent_class_name == "NWBDataInterface", (
        f"Expected parent_class_name='NWBDataInterface', got: {test_ts.parent_class_name}. "
        "extract_classes() must read neurodata_type_inc as parent_class_name."
    )


def test_nwb_extract_elements_both_mode(monkeypatch):
    """mode='both' merges code (mocked pynwb) + file (fixture YAML) elements."""
    import sys
    import types

    # Build minimal mock pynwb + hdmf NamespaceCatalog (same as T017)
    mock_pynwb = types.ModuleType("pynwb")

    mock_spec = {
        "neurodata_type_def": "NWBContainer",
        "doc": "A mock NWB container",
        "attributes": [{"name": "description", "dtype": "text", "doc": "Description"}],
        "datasets": [],
    }

    class MockGroupSpec:
        def to_dict(self):
            return mock_spec

    class MockNamespace:
        def get_registered_types(self):
            return ["NWBContainer"]

        def get_spec(self, dt):
            return MockGroupSpec()

    class MockCatalog:
        def get_namespace_names(self):
            return ["core"]

        def get_namespace(self, name):
            return MockNamespace()

    class MockTypeMap:
        namespace_catalog = MockCatalog()

    mock_pynwb.get_type_map = lambda: MockTypeMap()
    monkeypatch.setitem(sys.modules, "pynwb", mock_pynwb)

    mock_hdmf_spec = types.ModuleType("hdmf.spec")
    mock_hdmf_spec.GroupSpec = MockGroupSpec
    mock_hdmf = types.ModuleType("hdmf")
    monkeypatch.setitem(sys.modules, "hdmf", mock_hdmf)
    monkeypatch.setitem(sys.modules, "hdmf.spec", mock_hdmf_spec)

    adapter = NWBAdapter()
    adapter.load_code()
    code_els = adapter.extract_elements("code")
    adapter.load_file(str(FIXTURE))
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
