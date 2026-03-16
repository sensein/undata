"""Tests for v2 Pydantic models."""

import yaml
from pathlib import Path
from pydantic import ValidationError
import pytest

from undata_library.models import ElementRecord, SchemaRecord

FIXTURES = Path(__file__).parent / "fixtures"


class TestElementRecord:
    def test_valid_element_parses(self):
        data = yaml.safe_load((FIXTURES / "valid-element-v2.yaml").read_text())
        record = ElementRecord.model_validate(data)
        assert record.semantic.data_type.value == "integer"
        assert record.semantic.unit == "year"
        assert len(record.provenance) == 2

    def test_missing_data_type_fails(self):
        data = yaml.safe_load((FIXTURES / "invalid-element-no-datatype.yaml").read_text())
        with pytest.raises(ValidationError) as exc_info:
            ElementRecord.model_validate(data)
        errors = exc_info.value.errors()
        fields = [".".join(str(p) for p in e["loc"]) for e in errors]
        assert any("data_type" in f for f in fields)

    def test_bad_enum_fails(self):
        data = yaml.safe_load((FIXTURES / "invalid-element-bad-enum.yaml").read_text())
        with pytest.raises(ValidationError):
            ElementRecord.model_validate(data)

    def test_multiple_provenance_entries(self):
        data = yaml.safe_load((FIXTURES / "multi-provenance-element.yaml").read_text())
        record = ElementRecord.model_validate(data)
        assert len(record.provenance) == 3
        sources = {p.source for p in record.provenance}
        assert sources == {"bids", "nwb", "dandi"}

    def test_provenance_requires_at_least_one(self):
        with pytest.raises(ValidationError):
            ElementRecord.model_validate({
                "semantic": {"data_type": "string"},
                "provenance": [],
            })


class TestSchemaRecord:
    def test_valid_schema_parses(self):
        data = yaml.safe_load((FIXTURES / "valid-schema-v2.yaml").read_text())
        record = SchemaRecord.model_validate(data)
        assert len(record.semantic.properties) == 3
        assert record.semantic.subclass_of is None
        assert len(record.provenance) == 2

    def test_schema_with_subclass(self):
        record = SchemaRecord.model_validate({
            "semantic": {
                "properties": ["https://schema.undata.live/elements/age_x7k2m9"],
                "subclass_of": "https://schema.undata.live/schemas/base_a1b2c3",
            },
            "provenance": [{"source": "nwb", "name": "TimeSeries"}],
        })
        assert record.semantic.subclass_of == "https://schema.undata.live/schemas/base_a1b2c3"
