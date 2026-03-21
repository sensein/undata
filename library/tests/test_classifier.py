"""Tests for rule-based entity classification."""

from undata_library.adapters.classifier import classify_entity
from undata_library.models import EntityType


def test_json_schema_with_properties_is_class():
    entity_type, confidence = classify_entity(
        "Subject",
        {"type": "object", "properties": {"name": {"type": "string"}, "age": {"type": "integer"}}},
    )
    assert entity_type == EntityType.CLASS
    assert confidence >= 0.9


def test_leaf_string_field_is_attribute():
    entity_type, confidence = classify_entity("age", {"type": "string"})
    assert entity_type == EntityType.ATTRIBUTE
    assert confidence >= 0.8


def test_leaf_integer_is_attribute():
    entity_type, confidence = classify_entity("count", {"type": "integer"})
    assert entity_type == EntityType.ATTRIBUTE
    assert confidence >= 0.8


def test_enum_with_literals_is_valueset():
    entity_type, confidence = classify_entity("units", {"enum": ["meter", "second", "kilogram"]})
    assert entity_type == EntityType.VALUESET
    assert confidence >= 0.8


def test_named_enum_collection_is_valueset():
    entity_type, confidence = classify_entity(
        "modalities",
        {"type": "enum", "members": ["eeg", "mri", "pet"]},
    )
    assert entity_type == EntityType.VALUESET
    assert confidence >= 0.8


def test_linkml_permissible_values_is_valueset():
    entity_type, confidence = classify_entity(
        "SexEnum",
        {"permissible_values": {"male": {}, "female": {}, "other": {}}},
    )
    assert entity_type == EntityType.VALUESET
    assert confidence >= 0.9


def test_const_value_is_enum_value():
    entity_type, confidence = classify_entity("male", {"const": "male", "is_enum_member": True})
    assert entity_type == EntityType.ENUM_VALUE
    assert confidence >= 0.9


def test_ref_attribute_with_type_ref():
    """Attribute referencing another class should be classified as attribute."""
    entity_type, confidence = classify_entity("address", {"$ref": "#/$defs/Address"})
    assert entity_type == EntityType.ATTRIBUTE
    assert confidence >= 0.8


def test_linkml_class_with_slots():
    entity_type, confidence = classify_entity(
        "Subject",
        {"slots": ["age", "sex", "species"]},
    )
    assert entity_type == EntityType.CLASS
    assert confidence >= 0.9


def test_linkml_class_with_is_a():
    entity_type, confidence = classify_entity(
        "NWBFile",
        {"is_a": "NWBContainer"},
    )
    assert entity_type == EntityType.CLASS
    assert confidence >= 0.7


def test_oneof_with_consts_is_valueset():
    entity_type, confidence = classify_entity(
        "StatusEnum",
        {"oneOf": [{"const": "active"}, {"const": "inactive"}, {"const": "unknown"}]},
    )
    assert entity_type == EntityType.VALUESET
    assert confidence >= 0.8


def test_unknown_type_is_attribute_with_low_confidence():
    entity_type, confidence = classify_entity("mystery_field", {})
    assert entity_type == EntityType.ATTRIBUTE
    assert confidence < 0.7


def test_confidence_scores_in_range():
    """All confidence scores must be between 0.0 and 1.0."""
    test_cases = [
        ("class", {"properties": {"a": {}}}),
        ("attr", {"type": "string"}),
        ("enum", {"enum": ["a", "b", "c"]}),
        ("val", {"const": "x"}),
        ("unknown", {}),
    ]
    for name, type_info in test_cases:
        _, confidence = classify_entity(name, type_info)
        assert 0.0 <= confidence <= 1.0, f"Confidence out of range for {name}: {confidence}"
