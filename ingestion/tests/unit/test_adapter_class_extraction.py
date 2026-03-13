"""Unit tests for extract_classes() across all schema adapters — T014/T015.

Tests both structured-file paths (BIDS YAML, openMINDS JSON-LD, AIND JSON)
and code-introspection path (DANDI), plus YAML path for NWB.
"""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"


class TestBIDSExtractClasses:
    """T014 — BIDS adapter extract_classes() (YAML path)."""

    def test_extract_classes_returns_payloads(self):
        from undata.adapters.bids import BIDSAdapter
        from undata.models import SchemaClassPayload

        adapter = BIDSAdapter()
        adapter.load(str(FIXTURES_DIR / "bids_schema_sample.yaml"))
        classes = adapter.extract_classes()

        assert len(classes) >= 1
        for cls in classes:
            assert isinstance(cls, SchemaClassPayload)
            assert cls.extraction_path == "file"
            assert cls.schema_format == "yaml"
            assert cls.class_name
            assert isinstance(cls.element_source_local_ids, list)

    def test_extract_classes_nonempty_element_ids(self):
        from undata.adapters.bids import BIDSAdapter

        adapter = BIDSAdapter()
        adapter.load(str(FIXTURES_DIR / "bids_schema_sample.yaml"))
        classes = adapter.extract_classes()

        total_slids = sum(len(c.element_source_local_ids) for c in classes)
        assert total_slids >= 1


class TestOpenMINDSExtractClasses:
    """T014 — openMINDS adapter extract_classes() (JSON-LD path)."""

    def test_extract_classes_returns_single_class(self):
        from undata.adapters.openminds import OpenMINDSAdapter
        from undata.models import SchemaClassPayload

        adapter = OpenMINDSAdapter()
        adapter.load(str(FIXTURES_DIR / "openminds_sample.json"))
        classes = adapter.extract_classes()

        assert len(classes) == 1
        cls = classes[0]
        assert isinstance(cls, SchemaClassPayload)
        assert cls.extraction_path == "file"
        assert cls.schema_format == "jsonld"
        assert cls.class_name

    def test_extract_classes_nonempty_element_ids(self):
        from undata.adapters.openminds import OpenMINDSAdapter

        adapter = OpenMINDSAdapter()
        adapter.load(str(FIXTURES_DIR / "openminds_sample.json"))
        classes = adapter.extract_classes()

        assert any(len(c.element_source_local_ids) > 0 for c in classes)


class TestAINDExtractClasses:
    """T014 — AIND adapter extract_classes() (JSON path)."""

    def test_extract_classes_returns_payloads(self):
        from undata.adapters.aind import AINDAdapter
        from undata.models import SchemaClassPayload

        adapter = AINDAdapter()
        adapter.load(str(FIXTURES_DIR / "aind"))
        classes = adapter.extract_classes()

        assert len(classes) >= 1
        for cls in classes:
            assert isinstance(cls, SchemaClassPayload)
            assert cls.extraction_path == "file"
            assert cls.schema_format == "json"

    def test_extract_classes_nonempty_element_ids(self):
        from undata.adapters.aind import AINDAdapter

        adapter = AINDAdapter()
        adapter.load(str(FIXTURES_DIR / "aind"))
        classes = adapter.extract_classes()

        total_slids = sum(len(c.element_source_local_ids) for c in classes)
        assert total_slids >= 1


class TestDANDIExtractClasses:
    """T015 — DANDI adapter extract_classes() (code-introspection path)."""

    def test_extract_classes_returns_payloads(self):
        pytest.importorskip("dandischema")

        from undata.adapters.dandi import DANDIAdapter
        from undata.models import SchemaClassPayload

        adapter = DANDIAdapter()
        adapter.load("")
        classes = adapter.extract_classes()

        assert len(classes) >= 1
        for cls in classes:
            assert isinstance(cls, SchemaClassPayload)
            assert cls.extraction_path == "code"

    def test_extract_classes_model_names_as_class_names(self):
        pytest.importorskip("dandischema")

        from undata.adapters.dandi import DANDIAdapter

        adapter = DANDIAdapter()
        adapter.load("")
        classes = adapter.extract_classes()

        class_names = {c.class_name for c in classes}
        # DANDI schema includes Subject and BioSample model classes
        assert any(name in ("Subject", "BioSample", "Dandiset") for name in class_names), (
            f"Expected well-known DANDI models in {class_names}"
        )

    def test_extract_classes_source_local_ids_use_dot_prefix(self):
        pytest.importorskip("dandischema")

        from undata.adapters.dandi import DANDIAdapter

        adapter = DANDIAdapter()
        adapter.load("")
        classes = adapter.extract_classes()

        for cls in classes:
            for slid in cls.element_source_local_ids:
                assert "." in slid, f"source_local_id '{slid}' should be 'ModelName.field'"
                model_prefix = slid.split(".")[0]
                assert model_prefix == cls.class_name, (
                    f"Expected prefix '{cls.class_name}' but got '{model_prefix}'"
                )


class TestNWBExtractClasses:
    """T015 — NWB adapter extract_classes() (YAML path)."""

    def test_extract_classes_returns_payloads(self):
        from undata.adapters.nwb import NWBAdapter
        from undata.models import SchemaClassPayload

        adapter = NWBAdapter()
        adapter.load(str(FIXTURES_DIR / "nwb_schema_sample.yaml"))
        classes = adapter.extract_classes()

        assert len(classes) >= 1
        for cls in classes:
            assert isinstance(cls, SchemaClassPayload)
            assert cls.extraction_path == "file"
            assert cls.schema_format == "yaml"

    def test_extract_classes_neurodata_type_as_class_name(self):
        from undata.adapters.nwb import NWBAdapter

        adapter = NWBAdapter()
        adapter.load(str(FIXTURES_DIR / "nwb_schema_sample.yaml"))
        classes = adapter.extract_classes()

        class_names = {c.class_name for c in classes}
        # NWB fixture should include at least one neurodata_type
        assert len(class_names) >= 1
        for name in class_names:
            assert name  # non-empty
