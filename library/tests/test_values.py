"""Tests for ValueConcept model and validation."""

from pathlib import Path

import yaml
from pydantic import ValidationError
import pytest

from undata_library.models import ValueConcept

FIXTURES = Path(__file__).parent / "fixtures"


class TestValueConcept:
    def test_valid_value_parses(self):
        data = yaml.safe_load((FIXTURES / "valid-value.yaml").read_text())
        v = ValueConcept.model_validate(data)
        assert v.semantic.label == "male"
        assert v.semantic.ontology_term == "http://purl.obolibrary.org/obo/PATO_0000384"
        assert len(v.provenance) == 1

    def test_multi_provenance_accepted(self):
        data = yaml.safe_load((FIXTURES / "multi-provenance-value.yaml").read_text())
        v = ValueConcept.model_validate(data)
        assert len(v.provenance) == 3
        raw_values = {p.raw_value for p in v.provenance}
        assert raw_values == {"male", "Male", "M"}

    def test_missing_label_fails(self):
        with pytest.raises(ValidationError):
            ValueConcept.model_validate(
                {
                    "semantic": {"value_type": "categorical"},
                    "provenance": [{"source": "test", "raw_value": "x"}],
                }
            )

    def test_missing_provenance_fails(self):
        with pytest.raises(ValidationError):
            ValueConcept.model_validate(
                {
                    "semantic": {"label": "male", "value_type": "categorical"},
                    "provenance": [],
                }
            )

    def test_no_ontology_term_ok(self):
        v = ValueConcept.model_validate(
            {
                "semantic": {"label": "unknown_value", "value_type": "categorical"},
                "provenance": [{"source": "test", "raw_value": "unknown_value"}],
            }
        )
        assert v.semantic.ontology_term is None
        assert v.semantic.label == "unknown_value"
