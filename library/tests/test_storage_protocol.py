"""Protocol conformance tests for StorageBackend implementations.

Any backend (FileBackend, MockBackend, future DatabaseBackend) must pass
these tests. Parametrized over backend fixtures.
"""

from __future__ import annotations

import pytest

import uuid
from datetime import datetime, timezone

from undata_library.models import CurationFlag, FlagStatus, FlagType, RunSummary
from undata_library.storage.protocol import StorageBackend


def _sample_element(source: str = "bids", name: str = "age") -> dict:
    return {
        "semantic": {
            "data_type": "float",
            "unit": "years",
            "ontology_annotations": [],
        },
        "provenance": [
            {
                "source": source,
                "class": "Subject",
                "name": name,
                "description": f"The {name} field",
            },
        ],
    }


def _sample_schema(source: str = "bids") -> dict:
    return {
        "semantic": {
            "properties": ["age", "sex"],
            "subclass_of": None,
            "is_mixin": False,
            "ontology_annotations": [],
        },
        "provenance": [
            {"source": source, "class": "", "name": "Subject", "description": "Subject schema"},
        ],
    }


def _sample_value(source: str = "bids", label: str = "male") -> dict:
    return {
        "semantic": {
            "value_type": "categorical",
            "label": label,
            "description": f"The {label} value",
            "ontology_annotations": [
                {
                    "term_uri": "http://purl.obolibrary.org/obo/PATO_0000384",
                    "term_label": "male",
                    "ontology": "pato",
                    "mapping_relation": "skos:exactMatch",
                    "match_level": "concept_match",
                    "score": 0.95,
                    "model": "test",
                    "primary": True,
                }
            ],
        },
        "provenance": [
            {"source": source, "class": "Sex", "name": label, "description": ""},
        ],
    }


def _sample_valueset(source: str = "bids") -> dict:
    return {
        "semantic": {
            "name": "sex_options",
            "members": ["male_abc123", "female_def456"],
            "description": "Sex options",
            "ontology_annotations": [],
        },
        "provenance": [
            {"source": source, "class": "", "name": "sex_options", "description": ""},
        ],
    }


def _sample_flag() -> CurationFlag:
    return CurationFlag(
        id=str(uuid.uuid4()),
        entity_type="element",
        entity_ref="age_abc123",
        flag_type=FlagType.low_confidence,
        context={"reason": "score below threshold", "score": 0.45},
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def _sample_summary(source: str = "bids") -> RunSummary:
    return RunSummary(
        run_id=f"2026-03-24T12:00:00-{source}",
        source=source,
        started_at=datetime.now(timezone.utc).isoformat(),
        entity_counts={"extract": {"elements": 100}},
    )


class TestEntityStoreConformance:
    """Tests that any EntityStore implementation must pass."""

    @pytest.fixture(params=["file", "mock"])
    def backend(self, request, tmp_path):
        if request.param == "file":
            from undata_library.storage.file_backend import FileBackend

            return FileBackend(tmp_path)
        else:
            from undata_library.storage.mock_backend import MockBackend

            return MockBackend()

    def test_round_trip(self, backend: StorageBackend):
        data = _sample_element()
        eid = backend.entities.write("elements", data)
        result = backend.entities.read("elements", eid)
        assert result is not None
        assert result["semantic"]["data_type"] == "float"
        assert result["semantic"]["unit"] == "years"
        assert result["provenance"][0]["source"] == "bids"

    def test_list_after_writes(self, backend: StorageBackend):
        backend.entities.write("elements", _sample_element(name="age"))
        backend.entities.write("elements", _sample_element(name="weight"))
        items = list(backend.entities.list("elements"))
        assert len(items) == 2

    def test_exists_after_write(self, backend: StorageBackend):
        eid = backend.entities.write("elements", _sample_element())
        assert backend.entities.exists("elements", eid)

    def test_exists_returns_false_for_missing(self, backend: StorageBackend):
        assert not backend.entities.exists("elements", "nonexistent_abc123")

    def test_delete(self, backend: StorageBackend):
        eid = backend.entities.write("elements", _sample_element())
        assert backend.entities.delete("elements", eid)
        assert not backend.entities.exists("elements", eid)

    def test_delete_returns_false_for_missing(self, backend: StorageBackend):
        assert not backend.entities.delete("elements", "nonexistent_abc123")

    def test_count(self, backend: StorageBackend):
        assert backend.entities.count("elements") == 0
        backend.entities.write("elements", _sample_element(name="age"))
        backend.entities.write("elements", _sample_element(name="weight"))
        assert backend.entities.count("elements") == 2

    def test_merge_provenance_appends(self, backend: StorageBackend):
        data = _sample_element(source="bids", name="age")
        eid = backend.entities.write("elements", data)
        new_prov = [{"source": "nwb", "class": "Subject", "name": "age", "description": "NWB age"}]
        result = backend.entities.merge_provenance("elements", eid, new_prov)
        assert len(result["provenance"]) == 2
        sources = {p["source"] for p in result["provenance"]}
        assert sources == {"bids", "nwb"}

    def test_merge_provenance_deduplicates(self, backend: StorageBackend):
        data = _sample_element(source="bids", name="age")
        eid = backend.entities.write("elements", data)
        # Same source+name should not duplicate
        same_prov = [
            {"source": "bids", "class": "Subject", "name": "age", "description": "duplicate"}
        ]
        result = backend.entities.merge_provenance("elements", eid, same_prov)
        assert len(result["provenance"]) == 1

    def test_all_entity_types(self, backend: StorageBackend):
        samples = {
            "elements": _sample_element(),
            "schemas": _sample_schema(),
            "values": _sample_value(),
            "valuesets": _sample_valueset(),
        }
        for etype, data in samples.items():
            eid = backend.entities.write(etype, data)
            result = backend.entities.read(etype, eid)
            assert result is not None, f"Round-trip failed for {etype}"

    def test_filter_by_source(self, backend: StorageBackend):
        backend.entities.write("elements", _sample_element(source="bids", name="age"))
        backend.entities.write("elements", _sample_element(source="nwb", name="weight"))
        bids_items = list(backend.entities.list("elements", source="bids"))
        assert len(bids_items) == 1
        assert bids_items[0]["provenance"][0]["source"] == "bids"

    def test_filter_has_annotations(self, backend: StorageBackend):
        backend.entities.write("values", _sample_value(label="male"))  # has annotations
        no_annot = _sample_element(name="age")  # no annotations
        backend.entities.write("elements", no_annot)
        annotated = list(backend.entities.list("values", has_annotations=True))
        assert len(annotated) == 1

    def test_filter_data_type(self, backend: StorageBackend):
        float_elem = _sample_element(name="age")
        float_elem["semantic"]["data_type"] = "float"
        str_elem = _sample_element(name="name")
        str_elem["semantic"]["data_type"] = "string"
        backend.entities.write("elements", float_elem)
        backend.entities.write("elements", str_elem)
        floats = list(backend.entities.list("elements", data_type="float"))
        assert len(floats) == 1
        assert floats[0]["semantic"]["data_type"] == "float"

    def test_invalid_entity_type_raises(self, backend: StorageBackend):
        with pytest.raises((ValueError, KeyError)):
            backend.entities.write("invalid_type", {})

    def test_list_empty_returns_empty(self, backend: StorageBackend):
        items = list(backend.entities.list("elements"))
        assert items == []

    def test_read_missing_returns_none(self, backend: StorageBackend):
        assert backend.entities.read("elements", "nonexistent") is None

    def test_find_by_hash(self, backend: StorageBackend):
        data = _sample_element(name="age")
        data["sha256"] = "abcdef123456789000000000000000000000000000000000000000000000abcd"
        backend.entities.write("elements", data, identifier="age_abcdef123456")
        result = backend.entities.find_by_hash("elements", "abcdef123456")
        assert result is not None
        assert result["semantic"]["data_type"] == "float"

    def test_find_by_hash_returns_none(self, backend: StorageBackend):
        assert backend.entities.find_by_hash("elements", "nonexistent00") is None


class TestFlagStoreConformance:
    """Tests that any FlagStore implementation must pass."""

    @pytest.fixture(params=["file", "mock"])
    def backend(self, request, tmp_path):
        if request.param == "file":
            from undata_library.storage.file_backend import FileBackend

            return FileBackend(tmp_path)
        else:
            from undata_library.storage.mock_backend import MockBackend

            return MockBackend()

    def test_flag_lifecycle(self, backend: StorageBackend):
        flag = _sample_flag()
        flag_id = backend.flags.write_flag(flag)
        assert flag_id

        pending = backend.flags.read_flags(status=FlagStatus.pending)
        assert len(pending) == 1
        assert pending[0].flag_type == FlagType.low_confidence

        resolved = backend.flags.resolve_flag(
            flag_id, FlagStatus.approved, "curator@test", "Confirmed match"
        )
        assert resolved is not None
        assert resolved.status == FlagStatus.approved
        assert resolved.resolved_by == "curator@test"

        approved = backend.flags.read_flags(status=FlagStatus.approved)
        assert len(approved) == 1

        still_pending = backend.flags.read_flags(status=FlagStatus.pending)
        assert len(still_pending) == 0

    def test_filter_by_flag_type(self, backend: StorageBackend):
        flag1 = _sample_flag()
        flag2 = CurationFlag(
            id=str(uuid.uuid4()),
            entity_type="element",
            entity_ref="weight_def456",
            flag_type=FlagType.ambiguous_match,
            context={"reason": "multiple candidates"},
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        backend.flags.write_flag(flag1)
        backend.flags.write_flag(flag2)
        low_conf = backend.flags.read_flags(flag_type=FlagType.low_confidence)
        assert len(low_conf) == 1

    def test_resolve_missing_returns_none(self, backend: StorageBackend):
        result = backend.flags.resolve_flag("nonexistent", FlagStatus.approved, "test")
        assert result is None


class TestRunStoreConformance:
    """Tests that any RunStore implementation must pass."""

    @pytest.fixture(params=["file", "mock"])
    def backend(self, request, tmp_path):
        if request.param == "file":
            from undata_library.storage.file_backend import FileBackend

            return FileBackend(tmp_path)
        else:
            from undata_library.storage.mock_backend import MockBackend

            return MockBackend()

    def test_run_lifecycle(self, backend: StorageBackend):
        summary = _sample_summary("bids")
        rid = backend.runs.save_summary(summary)
        assert rid

        previous = backend.runs.load_previous("bids")
        assert previous is not None
        assert previous.source == "bids"
        assert previous.entity_counts == {"extract": {"elements": 100}}

    def test_load_previous_returns_none_for_unknown(self, backend: StorageBackend):
        assert backend.runs.load_previous("unknown_source") is None

    def test_list_runs(self, backend: StorageBackend):
        backend.runs.save_summary(_sample_summary("bids"))
        backend.runs.save_summary(_sample_summary("nwb"))
        all_runs = backend.runs.list_runs()
        assert len(all_runs) == 2
        bids_runs = backend.runs.list_runs(source="bids")
        assert len(bids_runs) == 1

    def test_list_runs_with_limit(self, backend: StorageBackend):
        backend.runs.save_summary(_sample_summary("bids"))
        backend.runs.save_summary(_sample_summary("bids"))
        limited = backend.runs.list_runs(source="bids", limit=1)
        assert len(limited) == 1


class TestConcurrentReads:
    """Test that concurrent reads don't corrupt data."""

    @pytest.fixture(params=["file", "mock"])
    def backend(self, request, tmp_path):
        if request.param == "file":
            from undata_library.storage.file_backend import FileBackend

            return FileBackend(tmp_path)
        else:
            from undata_library.storage.mock_backend import MockBackend

            return MockBackend()

    def test_concurrent_list_and_read(self, backend: StorageBackend):
        """Write entities, then read them from multiple iterators simultaneously."""
        for i in range(10):
            backend.entities.write("elements", _sample_element(name=f"field_{i}"))

        # Start two iterators simultaneously
        iter1 = backend.entities.list("elements")
        iter2 = backend.entities.list("elements")
        items1 = list(iter1)
        items2 = list(iter2)
        assert len(items1) == 10
        assert len(items2) == 10
