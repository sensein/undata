"""Tests for generic source adapters (JSON Schema, LinkML, CSV)."""

import json

import yaml

from undata_library.adapters.csv_dictionary import CSVDictionaryAdapter
from undata_library.adapters.json_schema import JSONSchemaAdapter
from undata_library.adapters.linkml import LinkMLAdapter
from undata_library.models import EntityType


# -- JSON Schema adapter tests --


def test_json_schema_mixed_defs(tmp_path):
    """JSON Schema with class defs + enum defs → correct classification."""
    schema = {
        "$defs": {
            "Subject": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "age": {"type": "integer"},
                },
            },
            "SexEnum": {
                "enum": ["male", "female", "other"],
            },
        },
        "type": "object",
        "title": "TestSchema",
        "properties": {
            "subject": {"$ref": "#/$defs/Subject"},
            "status": {"type": "string"},
        },
    }
    f = tmp_path / "test.json"
    f.write_text(json.dumps(schema))

    adapter = JSONSchemaAdapter()
    entities = adapter.extract(f)

    types = {e.entity_type for e in entities}
    assert EntityType.CLASS in types
    assert EntityType.VALUESET in types
    assert EntityType.ATTRIBUTE in types

    # SexEnum should be a valueset with 3 members
    valuesets = [e for e in entities if e.entity_type == EntityType.VALUESET]
    sex_vs = [v for v in valuesets if v.semantic.get("name") == "SexEnum"]
    assert len(sex_vs) == 1
    assert sorted(sex_vs[0].semantic["members"]) == ["female", "male", "other"]


def test_json_schema_circular_ref(tmp_path):
    """Circular $ref → no infinite loop, partial extraction."""
    schema = {
        "$defs": {
            "Node": {
                "type": "object",
                "properties": {
                    "value": {"type": "string"},
                    "child": {"$ref": "#/$defs/Node"},
                },
            },
        },
        "type": "object",
        "title": "Tree",
        "properties": {"root": {"$ref": "#/$defs/Node"}},
    }
    f = tmp_path / "circular.json"
    f.write_text(json.dumps(schema))

    adapter = JSONSchemaAdapter()
    entities = adapter.extract(f)

    # Should extract without error
    assert len(entities) > 0
    # Node class should appear
    classes = [e for e in entities if e.entity_type == EntityType.CLASS]
    assert any("Node" in e.provenance.get("name", "") for e in classes)


# -- LinkML adapter tests --


def test_linkml_classes_slots_enums(tmp_path):
    schema = {
        "name": "test_schema",
        "classes": {
            "Subject": {
                "description": "A research subject",
                "slots": ["age", "sex"],
            },
        },
        "slots": {
            "age": {"range": "integer", "description": "Age in years"},
            "sex": {"range": "string", "description": "Biological sex"},
        },
        "enums": {
            "SexEnum": {
                "description": "Biological sex values",
                "permissible_values": {
                    "male": {"meaning": "PATO:0000384"},
                    "female": {"meaning": "PATO:0000383"},
                },
            },
        },
    }
    f = tmp_path / "test.yaml"
    f.write_text(yaml.dump(schema))

    adapter = LinkMLAdapter()
    entities = adapter.extract(f)

    types = {e.entity_type for e in entities}
    assert EntityType.CLASS in types
    assert EntityType.ATTRIBUTE in types
    assert EntityType.VALUESET in types
    assert EntityType.ENUM_VALUE in types

    # SexEnum valueset with 2 members
    valuesets = [e for e in entities if e.entity_type == EntityType.VALUESET]
    assert len(valuesets) == 1
    assert sorted(valuesets[0].semantic["members"]) == ["female", "male"]


# -- CSV adapter tests --


def test_csv_basic(tmp_path):
    """CSV with 3 rows → 3 elements."""
    csv_content = "variable_name,field_type,field_label\nage,integer,Age in years\nsex,text,Biological sex\nweight,float,Weight in kg\n"
    f = tmp_path / "dd.csv"
    f.write_text(csv_content)

    adapter = CSVDictionaryAdapter()
    entities = adapter.extract(f)

    assert len(entities) == 3
    assert all(e.entity_type == EntityType.ATTRIBUTE for e in entities)

    names = {e.provenance["name"] for e in entities}
    assert names == {"age", "sex", "weight"}

    # Type inference
    age = [e for e in entities if e.provenance["name"] == "age"][0]
    assert age.semantic["data_type"] == "integer"


def test_csv_no_type_column(tmp_path):
    """CSV without type column → defaults to string."""
    csv_content = "name,description\nfoo,A foo field\nbar,A bar field\n"
    f = tmp_path / "dd.csv"
    f.write_text(csv_content)

    adapter = CSVDictionaryAdapter()
    entities = adapter.extract(f)

    assert len(entities) == 2
    assert all(e.semantic["data_type"] == "string" for e in entities)


def test_csv_with_choices(tmp_path):
    """CSV with select_choices → response_options."""
    csv_content = 'variable_name,field_type,select_choices\nsex,dropdown,"1, Male | 2, Female | 3, Other"\n'
    f = tmp_path / "dd.csv"
    f.write_text(csv_content)

    adapter = CSVDictionaryAdapter()
    entities = adapter.extract(f)

    assert len(entities) == 1
    sem = entities[0].semantic
    assert sem.get("response_options") is not None
    assert len(sem["response_options"]) == 3


def test_csv_source_ref(tmp_path):
    """Every entity has non-null source_ref with file + checksum."""
    csv_content = "variable_name,field_type\nfoo,string\n"
    f = tmp_path / "dd.csv"
    f.write_text(csv_content)

    adapter = CSVDictionaryAdapter()
    entities = adapter.extract(f)

    assert len(entities) == 1
    ref = entities[0].source_ref
    assert ref.file is not None
    assert ref.checksum != ""
