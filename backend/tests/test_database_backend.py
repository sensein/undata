"""Protocol conformance tests for DatabaseBackend against real PostgreSQL.

Ports the same test scenarios from library/tests/test_storage_protocol.py
but adapted for async DatabaseBackend.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest

from src.storage.database_backend import DatabaseBackend
from undata_library.models import CurationFlag, FlagStatus, FlagType, RunSummary


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


@pytest.fixture
def backend(db_session):
    return DatabaseBackend(db_session)


class TestEntityStoreConformance:
    """Entity CRUD tests — mirrors library conformance tests."""

    async def test_round_trip(self, backend):
        data = _sample_element()
        eid = await backend.entities.write("elements", data)
        result = await backend.entities.read("elements", eid)
        assert result is not None
        assert result["semantic"]["data_type"] == "float"
        assert result["semantic"]["unit"] == "years"
        assert result["provenance"][0]["source"] == "bids"

    async def test_list_after_writes(self, backend):
        await backend.entities.write("elements", _sample_element(name="age"))
        await backend.entities.write("elements", _sample_element(name="weight"))
        items = [item async for item in backend.entities.list("elements")]
        assert len(items) == 2

    async def test_exists_after_write(self, backend):
        eid = await backend.entities.write("elements", _sample_element())
        assert await backend.entities.exists("elements", eid)

    async def test_exists_returns_false(self, backend):
        assert not await backend.entities.exists("elements", "nonexistent_abc123")

    async def test_delete(self, backend):
        eid = await backend.entities.write("elements", _sample_element())
        assert await backend.entities.delete("elements", eid)
        assert not await backend.entities.exists("elements", eid)

    async def test_delete_returns_false(self, backend):
        assert not await backend.entities.delete("elements", "nonexistent_abc123")

    async def test_count(self, backend):
        assert await backend.entities.count("elements") == 0
        await backend.entities.write("elements", _sample_element(name="age"))
        await backend.entities.write("elements", _sample_element(name="weight"))
        assert await backend.entities.count("elements") == 2

    async def test_merge_provenance_appends(self, backend):
        data = _sample_element(source="bids", name="age")
        eid = await backend.entities.write("elements", data)
        new_prov = [{"source": "nwb", "class": "Subject", "name": "age", "description": "NWB age"}]
        result = await backend.entities.merge_provenance("elements", eid, new_prov)
        assert len(result["provenance"]) == 2
        sources = {p["source"] for p in result["provenance"]}
        assert sources == {"bids", "nwb"}

    async def test_merge_provenance_deduplicates(self, backend):
        data = _sample_element(source="bids", name="age")
        eid = await backend.entities.write("elements", data)
        same_prov = [
            {"source": "bids", "class": "Subject", "name": "age", "description": "duplicate"}
        ]
        result = await backend.entities.merge_provenance("elements", eid, same_prov)
        assert len(result["provenance"]) == 1

    async def test_all_entity_types(self, backend):
        samples = {
            "elements": _sample_element(),
            "schemas": _sample_schema(),
            "values": _sample_value(),
            "valuesets": _sample_valueset(),
        }
        for etype, data in samples.items():
            eid = await backend.entities.write(etype, data)
            result = await backend.entities.read(etype, eid)
            assert result is not None, f"Round-trip failed for {etype}"

    async def test_filter_by_source(self, backend):
        await backend.entities.write("elements", _sample_element(source="bids", name="age"))
        await backend.entities.write("elements", _sample_element(source="nwb", name="weight"))
        bids_items = [item async for item in backend.entities.list("elements", source="bids")]
        assert len(bids_items) == 1
        assert bids_items[0]["provenance"][0]["source"] == "bids"

    async def test_filter_has_annotations(self, backend):
        await backend.entities.write("values", _sample_value(label="male"))
        no_annot = _sample_element(name="age")
        await backend.entities.write("elements", no_annot)
        annotated = [item async for item in backend.entities.list("values", has_annotations=True)]
        assert len(annotated) == 1

    async def test_filter_data_type(self, backend):
        float_elem = _sample_element(name="age")
        float_elem["semantic"]["data_type"] = "float"
        str_elem = _sample_element(name="name")
        str_elem["semantic"]["data_type"] = "string"
        await backend.entities.write("elements", float_elem)
        await backend.entities.write("elements", str_elem)
        floats = [item async for item in backend.entities.list("elements", data_type="float")]
        assert len(floats) == 1
        assert floats[0]["semantic"]["data_type"] == "float"

    async def test_invalid_entity_type_raises(self, backend):
        with pytest.raises((ValueError, KeyError)):
            await backend.entities.write("invalid_type", {})

    async def test_list_empty(self, backend):
        items = [item async for item in backend.entities.list("elements")]
        assert items == []

    async def test_read_missing(self, backend):
        assert await backend.entities.read("elements", "nonexistent") is None

    async def test_find_by_hash(self, backend):
        data = _sample_element(name="age")
        data["sha256"] = "abcdef123456789000000000000000000000000000000000000000000000abcd"
        await backend.entities.write("elements", data, identifier="age_abcdef123456")
        result = await backend.entities.find_by_hash("elements", "abcdef123456")
        assert result is not None
        assert result["semantic"]["data_type"] == "float"

    async def test_find_by_hash_missing(self, backend):
        assert await backend.entities.find_by_hash("elements", "nonexistent00") is None


class TestFlagStoreConformance:
    """Curation flag lifecycle tests."""

    async def test_flag_lifecycle(self, backend):
        flag = _sample_flag()
        flag_id = await backend.flags.write_flag(flag)
        assert flag_id

        pending = await backend.flags.read_flags(status=FlagStatus.pending)
        assert len(pending) == 1
        assert pending[0].flag_type == FlagType.low_confidence

        resolved = await backend.flags.resolve_flag(
            flag_id, FlagStatus.approved, "curator@test", "Confirmed match"
        )
        assert resolved is not None
        assert resolved.status == FlagStatus.approved
        assert resolved.resolved_by == "curator@test"

        approved = await backend.flags.read_flags(status=FlagStatus.approved)
        assert len(approved) == 1

        still_pending = await backend.flags.read_flags(status=FlagStatus.pending)
        assert len(still_pending) == 0

    async def test_filter_by_flag_type(self, backend):
        flag1 = _sample_flag()
        flag2 = CurationFlag(
            id=str(uuid.uuid4()),
            entity_type="element",
            entity_ref="weight_def456",
            flag_type=FlagType.ambiguous_match,
            context={"reason": "multiple candidates"},
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        await backend.flags.write_flag(flag1)
        await backend.flags.write_flag(flag2)
        low_conf = await backend.flags.read_flags(flag_type=FlagType.low_confidence)
        assert len(low_conf) == 1

    async def test_resolve_missing(self, backend):
        result = await backend.flags.resolve_flag(
            str(uuid.uuid4()), FlagStatus.approved, "test"
        )
        assert result is None


class TestRunStoreConformance:
    """Run summary lifecycle tests."""

    async def test_run_lifecycle(self, backend):
        summary = _sample_summary("bids")
        rid = await backend.runs.save_summary(summary)
        assert rid

        previous = await backend.runs.load_previous("bids")
        assert previous is not None
        assert previous.source == "bids"
        assert previous.entity_counts == {"extract": {"elements": 100}}

    async def test_load_previous_unknown(self, backend):
        assert await backend.runs.load_previous("unknown_source") is None

    async def test_list_runs(self, backend):
        await backend.runs.save_summary(_sample_summary("bids"))
        await backend.runs.save_summary(_sample_summary("nwb"))
        all_runs = await backend.runs.list_runs()
        assert len(all_runs) == 2
        bids_runs = await backend.runs.list_runs(source="bids")
        assert len(bids_runs) == 1

    async def test_list_runs_with_limit(self, backend):
        await backend.runs.save_summary(_sample_summary("bids"))
        await backend.runs.save_summary(_sample_summary("bids"))
        limited = await backend.runs.list_runs(source="bids", limit=1)
        assert len(limited) == 1
