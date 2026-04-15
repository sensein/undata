"""Tests for OntologyAnnotation model and hash exclusion."""

from undata_library.hashing import canonical_json
from undata_library.models import MatchLevel, OntologyAnnotation


def test_ontology_annotation_validates():
    ann = OntologyAnnotation(
        term_uri="http://purl.obolibrary.org/obo/NCIT_C25150",
        term_label="Age",
        ontology="ncit",
        mapping_relation="skos:exactMatch",
        match_level=MatchLevel.concept_match,
        score=0.96,
        model="all-MiniLM-L6-v2",
    )
    assert ann.term_uri == "http://purl.obolibrary.org/obo/NCIT_C25150"
    assert ann.primary is False


def test_primary_defaults_false():
    ann = OntologyAnnotation(
        term_uri="x",
        term_label="X",
        ontology="test",
        mapping_relation="skos:relatedMatch",
        match_level=MatchLevel.concept_match,
        score=0.5,
        model="test",
    )
    assert ann.primary is False


def test_match_level_enum():
    assert MatchLevel.concept_match == "concept_match"
    assert MatchLevel.element_match == "element_match"
    assert len(MatchLevel) == 2


def test_ontology_annotations_excluded_from_hash():
    sem_a = {"data_type": "string", "ontology_annotations": [{"term_uri": "x"}]}
    sem_b = {"data_type": "string"}
    # ontology_annotations should be excluded → same canonical JSON
    assert canonical_json(sem_a) == canonical_json(sem_b)


def test_element_match_for_value():
    ann = OntologyAnnotation(
        term_uri="http://purl.obolibrary.org/obo/PATO_0000384",
        term_label="male",
        ontology="pato",
        mapping_relation="skos:exactMatch",
        match_level=MatchLevel.element_match,
        score=0.99,
        model="all-MiniLM-L6-v2",
        primary=True,
    )
    assert ann.match_level == MatchLevel.element_match
    assert ann.primary is True
