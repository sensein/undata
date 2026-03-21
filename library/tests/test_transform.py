"""Tests for transform generation engine."""

import yaml

from undata_library.models import MappingFunctionType
from undata_library.transform import (
    _detect_pattern,
    _reverse_function,
    generate_transforms,
)


# -- Pattern detection tests --


def test_identity_pattern():
    """Same type + same unit → identity."""
    sem_a = {"data_type": "string", "unit": "year"}
    sem_b = {"data_type": "string", "unit": "year"}
    func = _detect_pattern(sem_a, sem_b)
    assert func is not None
    assert func.function_type == MappingFunctionType.identity


def test_unit_conversion_years_to_months():
    """Same type + different unit (year → month) → unit_conversion with factor=12."""
    sem_a = {"data_type": "float", "unit": "year"}
    sem_b = {"data_type": "float", "unit": "month"}
    func = _detect_pattern(sem_a, sem_b)
    assert func is not None
    assert func.function_type == MappingFunctionType.unit_conversion
    assert func.expression == "value * 12.0"
    assert func.parameters["factor"] == 12.0


def test_type_conversion_float_to_iso8601():
    """float → string with ISO8601 context → type_conversion."""
    sem_a = {"data_type": "float", "unit": "year"}
    sem_b = {"data_type": "string", "unit": "iso8601_duration"}
    func = _detect_pattern(sem_a, sem_b)
    assert func is not None
    assert func.function_type == MappingFunctionType.type_conversion
    assert func.expression == "iso8601_duration_from_years"


def test_value_mapping_overlapping_enums():
    """Overlapping response_options → value_mapping."""
    sem_a = {
        "data_type": "string",
        "response_options": [{"value": "male"}, {"value": "female"}, {"value": "other"}],
    }
    sem_b = {
        "data_type": "string",
        "response_options": [{"value": "male"}, {"value": "female"}, {"value": "unknown"}],
    }
    func = _detect_pattern(sem_a, sem_b)
    assert func is not None
    assert func.function_type == MappingFunctionType.value_mapping
    assert func.expression_type == "lookup_table"


def test_structural_object_to_primitive():
    """object ↔ string → structural."""
    sem_a = {"data_type": "object"}
    sem_b = {"data_type": "string"}
    func = _detect_pattern(sem_a, sem_b)
    assert func is not None
    assert func.function_type == MappingFunctionType.structural


def test_unknown_incompatible_types():
    """boolean vs array → unknown."""
    sem_a = {"data_type": "boolean"}
    sem_b = {"data_type": "array"}
    func = _detect_pattern(sem_a, sem_b)
    assert func is not None
    assert func.function_type == MappingFunctionType.unknown


def test_same_hash_no_transform(tmp_path):
    """Elements with identical semantic hash → no transform generated."""
    elements_dir = tmp_path / "elements"
    elements_dir.mkdir()

    sem = {
        "data_type": "string",
        "ontology_annotations": [
            {
                "term_uri": "http://example.org/X",
                "term_label": "X",
                "ontology": "test",
                "mapping_relation": "skos:exactMatch",
                "match_level": "concept_match",
                "score": 0.97,
                "model": "test",
                "primary": True,
            }
        ],
    }
    for name in ("a_abc123456789", "b_def123456789"):
        elem = {"semantic": sem, "provenance": [{"source": "test", "class": "X", "name": "x"}]}
        (elements_dir / f"{name}.yaml").write_text(yaml.dump(elem))

    stats = generate_transforms(elements_dir, tmp_path)
    assert stats["transforms_created"] == 0


def test_bidirectional_transforms(tmp_path):
    """Different types → both forward and reverse transforms written."""
    elements_dir = tmp_path / "elements"
    elements_dir.mkdir()

    onto_ann = [
        {
            "term_uri": "http://example.org/age",
            "term_label": "Age",
            "ontology": "test",
            "mapping_relation": "skos:exactMatch",
            "match_level": "concept_match",
            "score": 0.97,
            "model": "test",
            "primary": True,
        }
    ]
    elem_a = {
        "semantic": {
            "data_type": "float",
            "unit": "year",
            "ontology_annotations": onto_ann,
        },
        "provenance": [{"source": "bids", "class": "Subject", "name": "age"}],
    }
    elem_b = {
        "semantic": {
            "data_type": "float",
            "unit": "month",
            "ontology_annotations": onto_ann,
        },
        "provenance": [{"source": "custom", "class": "Subject", "name": "age_months"}],
    }
    (elements_dir / "age_aaa123456789.yaml").write_text(yaml.dump(elem_a))
    (elements_dir / "age_bbb123456789.yaml").write_text(yaml.dump(elem_b))

    stats = generate_transforms(elements_dir, tmp_path)
    assert stats["transforms_created"] == 2  # forward + reverse

    transform_files = list((tmp_path / "transforms").glob("*.yaml"))
    assert len(transform_files) == 2


def test_transform_has_sha256(tmp_path):
    """Transform YAML includes sha256 field."""
    elements_dir = tmp_path / "elements"
    elements_dir.mkdir()

    for name, dt in [("a_aaa123456789", "float"), ("b_bbb123456789", "string")]:
        (elements_dir / f"{name}.yaml").write_text(
            yaml.dump(
                {
                    "semantic": {
                        "data_type": dt,
                        "ontology_annotations": [
                            {
                                "term_uri": "http://example.org/X",
                                "term_label": "X",
                                "ontology": "test",
                                "mapping_relation": "skos:exactMatch",
                                "match_level": "concept_match",
                                "score": 0.97,
                                "model": "test",
                                "primary": True,
                            }
                        ],
                    },
                    "provenance": [{"source": "test", "class": "C", "name": "x"}],
                }
            )
        )

    generate_transforms(elements_dir, tmp_path)
    for f in (tmp_path / "transforms").glob("*.yaml"):
        data = yaml.safe_load(f.read_text())
        assert "sha256" in data
        assert len(data["sha256"]) == 64


def test_reverse_unit_conversion():
    """Reverse of year→month factor=12 is month→year factor=1/12."""
    from undata_library.models import FunctionSpec

    forward = FunctionSpec(
        function_type=MappingFunctionType.unit_conversion,
        input_type="float",
        output_type="float",
        expression="value * 12.0",
        expression_type="arithmetic",
        parameters={"factor": 12.0, "unit_from": "year", "unit_to": "month"},
    )
    reverse = _reverse_function(forward)
    assert reverse.input_type == "float"
    assert reverse.output_type == "float"
    assert reverse.parameters["unit_from"] == "month"
    assert reverse.parameters["unit_to"] == "year"
    assert abs(reverse.parameters["factor"] - 1.0 / 12.0) < 1e-10
