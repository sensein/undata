"""Tests for TransformRecord, FunctionSpec, and transform hashing."""

from undata_library.hashing import build_transform_uri
from undata_library.models import FunctionSpec, MappingFunctionType, TransformRecord


def test_function_spec_all_expression_types():
    for et in ("arithmetic", "named_function", "template", "lookup_table", "none"):
        fs = FunctionSpec(
            function_type=MappingFunctionType.identity,
            input_type="string",
            output_type="string",
            expression_type=et,
        )
        assert fs.expression_type == et


def test_transform_record_roundtrip():
    tr = TransformRecord(
        source_element="https://schema.undata.live/elements/age_abc",
        target_element="https://schema.undata.live/elements/age_def",
        function=FunctionSpec(
            function_type=MappingFunctionType.unit_conversion,
            input_type="float",
            output_type="float",
            expression="value * 12",
            expression_type="arithmetic",
            parameters={"factor": 12},
        ),
        confidence=0.95,
    )
    d = tr.model_dump()
    tr2 = TransformRecord.model_validate(d)
    assert tr2.source_element == tr.source_element
    assert tr2.function.expression == "value * 12"
    assert tr2.function.parameters == {"factor": 12}


def test_mapping_function_type_includes_new_variants():
    assert MappingFunctionType.type_conversion == "type_conversion"
    assert MappingFunctionType.value_mapping == "value_mapping"
    # Ensure all 7 variants exist
    assert len(MappingFunctionType) == 7


def test_build_transform_uri():
    uri = build_transform_uri("age", "age_iso", "abc123456789")
    assert uri == "https://schema.undata.live/transforms/age_to_age_iso_abc123456789"
