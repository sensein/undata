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
        assert len(v.provenance) == 1

    def test_multi_provenance_accepted(self):
        data = yaml.safe_load((FIXTURES / "multi-provenance-value.yaml").read_text())
        v = ValueConcept.model_validate(data)
        assert len(v.provenance) == 3
        names = {p.name for p in v.provenance}
        assert names == {"male", "Male", "M"}

    def test_missing_label_fails(self):
        with pytest.raises(ValidationError):
            ValueConcept.model_validate(
                {
                    "semantic": {"value_type": "categorical"},
                    "provenance": [{"source": "test", "class": "", "name": "x"}],
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

    def test_no_ontology_annotations_ok(self):
        v = ValueConcept.model_validate(
            {
                "semantic": {"label": "unknown_value", "value_type": "categorical"},
                "provenance": [{"source": "test", "class": "", "name": "unknown_value"}],
            }
        )
        assert v.semantic.ontology_annotations is None
        assert v.semantic.label == "unknown_value"
