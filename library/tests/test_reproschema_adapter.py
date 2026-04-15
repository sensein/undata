"""Tests for ReproSchema adapter — extract entities from activity/item JSON-LD."""

from __future__ import annotations

import json
from pathlib import Path

from undata_library.adapters.reproschema import ReproSchemaAdapter
from undata_library.models import EntityType


def _create_mock_library(tmp_path: Path) -> Path:
    """Create a minimal mock reproschema-library structure."""
    lib = tmp_path / "reproschema-library"
    act_dir = lib / "activities" / "PHQ9"
    items_dir = act_dir / "items"
    items_dir.mkdir(parents=True)

    # Activity schema
    (act_dir / "PHQ9_schema").write_text(
        json.dumps(
            {
                "@context": "https://raw.githubusercontent.com/ReproNim/reproschema/master/contexts/generic",
                "@type": "reproschema:Activity",
                "description": {"en": "Patient Health Questionnaire-9"},
                "ui": {"order": ["phq9_1", "phq9_2", "phq9_total"]},
            }
        ),
        encoding="utf-8",
    )

    # Items
    (items_dir / "phq9_1").write_text(
        json.dumps(
            {
                "question": {"en": "Little interest or pleasure in doing things"},
                "responseOptions": {
                    "valueType": "integer",
                    "minValue": 0,
                    "maxValue": 3,
                    "choices": [
                        {"value": 0, "name": "Not at all"},
                        {"value": 1, "name": "Several days"},
                        {"value": 2, "name": "More than half the days"},
                        {"value": 3, "name": "Nearly every day"},
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    (items_dir / "phq9_2").write_text(
        json.dumps(
            {
                "question": {"en": "Feeling down, depressed, or hopeless"},
                "responseOptions": {"valueType": "integer", "minValue": 0, "maxValue": 3},
            }
        ),
        encoding="utf-8",
    )

    (items_dir / "phq9_total").write_text(
        json.dumps(
            {
                "question": {"en": "PHQ-9 total score"},
                "description": {"en": "Sum of all 9 items"},
                "responseOptions": {"valueType": "integer", "minValue": 0, "maxValue": 27},
            }
        ),
        encoding="utf-8",
    )

    return lib


def test_extract_activity_as_class(tmp_path):
    lib = _create_mock_library(tmp_path)
    adapter = ReproSchemaAdapter()
    entities = adapter.extract(lib)

    classes = [e for e in entities if e.entity_type == EntityType.CLASS]
    assert len(classes) == 1
    assert classes[0].provenance["name"] == "PHQ9"


def test_extract_items_as_attributes(tmp_path):
    lib = _create_mock_library(tmp_path)
    adapter = ReproSchemaAdapter()
    entities = adapter.extract(lib)

    attrs = [e for e in entities if e.entity_type == EntityType.ATTRIBUTE]
    names = [a.provenance["name"] for a in attrs]
    assert "phq9_1" in names
    assert "phq9_2" in names
    assert "phq9_total" in names


def test_response_options_extracted(tmp_path):
    """Response options become VALUESET + ENUM_VALUE entities via LinkML enums."""
    lib = _create_mock_library(tmp_path)
    adapter = ReproSchemaAdapter()
    entities = adapter.extract(lib)

    # The phq9_1 slot should reference the enum via type_ref
    by_name = {e.provenance["name"]: e for e in entities if e.entity_type == EntityType.ATTRIBUTE}
    phq1 = by_name["phq9_1"]
    assert phq1.semantic.get("type_ref") == "phq9_1_options"

    # VALUESET entity for the enum
    valuesets = [e for e in entities if e.entity_type == EntityType.VALUESET]
    phq1_vs = [v for v in valuesets if v.provenance["name"] == "phq9_1_options"]
    assert len(phq1_vs) == 1
    assert len(phq1_vs[0].semantic["members"]) == 4

    # ENUM_VALUE entities for each choice
    enum_vals = [
        e
        for e in entities
        if e.entity_type == EntityType.ENUM_VALUE
        and e.provenance.get("class") == "phq9_1_options"
    ]
    assert len(enum_vals) == 4
    val_names = sorted(e.provenance["name"] for e in enum_vals)
    assert val_names == ["0", "1", "2", "3"]


def test_min_max_extracted(tmp_path):
    lib = _create_mock_library(tmp_path)
    adapter = ReproSchemaAdapter()
    entities = adapter.extract(lib)

    by_name = {e.provenance["name"]: e for e in entities if e.entity_type == EntityType.ATTRIBUTE}
    total = by_name["phq9_total"]
    assert total.semantic.get("min_value") == 0
    assert total.semantic.get("max_value") == 27


def test_data_type_inferred(tmp_path):
    lib = _create_mock_library(tmp_path)
    adapter = ReproSchemaAdapter()
    entities = adapter.extract(lib)

    by_name = {e.provenance["name"]: e for e in entities if e.entity_type == EntityType.ATTRIBUTE}
    # phq9_1 has response options (choices), so its range is the enum
    # "phq9_1_options" which maps to data_type "string" in the LinkML
    # type map (enum names are not in _LINKML_TYPE_MAP)
    assert by_name["phq9_1"].semantic["data_type"] == "string"


def test_provenance_source(tmp_path):
    lib = _create_mock_library(tmp_path)
    adapter = ReproSchemaAdapter()
    entities = adapter.extract(lib)

    for e in entities:
        assert e.provenance["source"] == "reproschema"
