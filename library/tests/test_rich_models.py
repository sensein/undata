"""Tests for enriched SemanticIdentity + PROV-O provenance."""

from pathlib import Path

import yaml

from undata_library.hashing import canonical_json, compute_sha256
from undata_library.models import (
    ElementRecord,
    ResponseOption,
)

FIXTURES = Path(__file__).parent / "fixtures"


class TestResponseOption:
    def test_parses(self):
        opt = ResponseOption(value="male", label="Male", ontology_term="PATO:0000384")
        assert opt.value == "male"
        assert opt.ontology_term == "PATO:0000384"

    def test_without_ontology(self):
        opt = ResponseOption(value="other", label="Other")
        assert opt.ontology_term is None


class TestEnrichedSemanticIdentity:
    def test_min_max_in_hash(self):
        sem_a = {"data_type": "float", "min_value": 0, "max_value": 150}
        sem_b = {"data_type": "float", "min_value": 0, "max_value": 100}
        hash_a = compute_sha256(canonical_json(sem_a))
        hash_b = compute_sha256(canonical_json(sem_b))
        assert hash_a != hash_b  # Different ranges → different hash

    def test_same_range_same_hash(self):
        sem_a = {"data_type": "float", "min_value": 0, "max_value": 150}
        sem_b = {"data_type": "float", "min_value": 0, "max_value": 150}
        assert compute_sha256(canonical_json(sem_a)) == compute_sha256(canonical_json(sem_b))

    def test_question_text_excluded_from_hash(self):
        sem_a = {"data_type": "string", "question_text": "What is your name?"}
        sem_b = {"data_type": "string", "question_text": "Name?"}
        sem_c = {"data_type": "string"}
        hash_a = compute_sha256(canonical_json(sem_a))
        hash_b = compute_sha256(canonical_json(sem_b))
        hash_c = compute_sha256(canonical_json(sem_c))
        assert hash_a == hash_b == hash_c  # question_text excluded

    def test_value_domain_excluded_from_hash(self):
        sem_a = {"data_type": "string", "value_domain": "categorical"}
        sem_b = {"data_type": "string", "value_domain": "text"}
        assert compute_sha256(canonical_json(sem_a)) == compute_sha256(canonical_json(sem_b))

    def test_response_options_in_hash(self):
        sem_a = {
            "data_type": "string",
            "response_options": [
                {"value": "male", "label": "Male"},
                {"value": "female", "label": "Female"},
            ],
        }
        sem_b = {
            "data_type": "string",
            "response_options": [
                {"value": "male", "label": "Male"},
            ],
        }
        hash_a = compute_sha256(canonical_json(sem_a))
        hash_b = compute_sha256(canonical_json(sem_b))
        assert hash_a != hash_b  # Different options → different hash

    def test_response_options_order_independent(self):
        sem_a = {
            "data_type": "string",
            "response_options": [
                {"value": "female", "label": "F"},
                {"value": "male", "label": "M"},
            ],
        }
        sem_b = {
            "data_type": "string",
            "response_options": [
                {"value": "male", "label": "M"},
                {"value": "female", "label": "F"},
            ],
        }
        assert compute_sha256(canonical_json(sem_a)) == compute_sha256(canonical_json(sem_b))

    def test_constraints_minimum_excluded(self):
        """constraints.minimum/maximum are deprecated — excluded from hash."""
        sem_a = {"data_type": "float", "constraints": {"minimum": 0, "maximum": 100}}
        sem_b = {"data_type": "float", "constraints": {"minimum": 0, "maximum": 200}}
        sem_c = {"data_type": "float"}
        hash_a = compute_sha256(canonical_json(sem_a))
        hash_b = compute_sha256(canonical_json(sem_b))
        hash_c = compute_sha256(canonical_json(sem_c))
        assert hash_a == hash_b == hash_c  # deprecated fields excluded


class TestProvOProvenance:
    def test_prov_o_fields_parse(self):
        data = yaml.safe_load((FIXTURES / "valid-element-rich.yaml").read_text())
        record = ElementRecord.model_validate(data)
        assert len(record.provenance) == 2

        p0 = record.provenance[0]
        assert p0.generated_at == "2026-03-17T12:00:00Z"
        assert p0.attributed_to == "urn:undata:ingestion-pipeline"
        assert p0.activity == "ingestion"
        assert p0.derived_from is None

        p1 = record.provenance[1]
        assert p1.activity == "curation"
        assert "orcid" in p1.attributed_to
        assert p1.derived_from is not None

    def test_rich_semantic_parses(self):
        data = yaml.safe_load((FIXTURES / "valid-element-rich.yaml").read_text())
        record = ElementRecord.model_validate(data)
        assert record.semantic.min_value == 0
        assert record.semantic.max_value == 150
        assert record.semantic.question_text == "How old is the participant?"
        assert record.semantic.value_domain == "numeric"
