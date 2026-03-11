"""Contract tests: SchemaAdapter Protocol v2 conformance (T004).

All five adapters must satisfy isinstance(adapter, SchemaAdapter) and
expose load_code(), load_file(), extract_elements(mode), extract_classes(mode).
"""

from __future__ import annotations

import pytest

from undata.adapters.aind import AINDAdapter
from undata.adapters.base import SchemaAdapter
from undata.adapters.bids import BIDSAdapter
from undata.adapters.dandi import DANDIAdapter
from undata.adapters.nwb import NWBAdapter
from undata.adapters.openminds import OpenMINDSAdapter

ADAPTER_CLASSES = [
    AINDAdapter,
    BIDSAdapter,
    DANDIAdapter,
    NWBAdapter,
    OpenMINDSAdapter,
]


@pytest.mark.parametrize("cls", ADAPTER_CLASSES, ids=lambda c: c.__name__)
def test_adapter_satisfies_schema_adapter_protocol(cls):
    """Every adapter must be an instance of SchemaAdapter (structural typing)."""
    adapter = cls()
    assert isinstance(adapter, SchemaAdapter), (
        f"{cls.__name__} does not satisfy SchemaAdapter Protocol v2. "
        "Ensure load_code(), load_file(), extract_elements(mode), "
        "extract_classes(mode) are all implemented."
    )


@pytest.mark.parametrize("cls", ADAPTER_CLASSES, ids=lambda c: c.__name__)
def test_adapter_has_required_methods(cls):
    """Each adapter must expose the dual-path interface methods."""
    adapter = cls()
    for method in (
        "load",
        "load_code",
        "load_file",
        "extract_elements",
        "extract_classes",
        "get_version_info",
    ):
        assert hasattr(adapter, method), f"{cls.__name__} missing method: {method}"
        assert callable(getattr(adapter, method)), f"{cls.__name__}.{method} is not callable"


@pytest.mark.parametrize("cls", ADAPTER_CLASSES, ids=lambda c: c.__name__)
def test_adapter_has_source_attributes(cls):
    """Each adapter must have source_name and source_format class attributes."""
    assert hasattr(cls, "source_name"), f"{cls.__name__} missing source_name"
    assert hasattr(cls, "source_format"), f"{cls.__name__} missing source_format"
    assert isinstance(cls.source_name, str), f"{cls.__name__}.source_name must be str"
    assert isinstance(cls.source_format, str), f"{cls.__name__}.source_format must be str"
