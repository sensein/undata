"""Tests for two-mode identity hash (ontology-anchored vs structural fallback)."""

from undata_library.hashing import compute_identity_hash, determine_hash_mode


def _onto_ann(uri, relation="skos:exactMatch", match_level="concept_match", primary=True):
    return {
        "term_uri": uri,
        "term_label": "X",
        "ontology": "test",
        "mapping_relation": relation,
        "match_level": match_level,
        "score": 0.97,
        "model": "test",
        "primary": primary,
    }


def test_ontology_anchored_same_concept_same_hash():
    """Two elements with same data_type+unit+ontology → same hash regardless of class/name."""
    sem = {"data_type": "float", "unit": "year"}
    prov_a = [{"class": "participant", "name": "age", "description": "Age in years"}]
    prov_b = [{"class": "Subject", "name": "subject_age", "description": "Subject age"}]

    hash_a, _ = compute_identity_hash(
        sem, prov_a, ontology_anchored=True, primary_ontology_uri="NCIT:C25150"
    )
    hash_b, _ = compute_identity_hash(
        sem, prov_b, ontology_anchored=True, primary_ontology_uri="NCIT:C25150"
    )
    assert hash_a == hash_b


def test_ontology_anchored_different_concept_different_hash():
    """Same data shape but different ontology → different hash."""
    sem = {"data_type": "float", "unit": "year"}
    prov = [{"class": "Subject", "name": "age"}]

    hash_a, _ = compute_identity_hash(
        sem, prov, ontology_anchored=True, primary_ontology_uri="NCIT:C25150"
    )
    hash_b, _ = compute_identity_hash(
        sem, prov, ontology_anchored=True, primary_ontology_uri="NCIT:C99999"
    )
    assert hash_a != hash_b


def test_fallback_different_description_different_hash():
    """PHQ-9 scenario: same response_options + different description → different hashes."""
    response_opts = [{"value": "0"}, {"value": "1"}, {"value": "2"}, {"value": "3"}]
    sem = {
        "data_type": "integer",
        "min_value": 0,
        "max_value": 3,
        "response_options": response_opts,
    }

    prov_a = [
        {"class": "PHQ9", "name": "phq9_interest", "description": "Little interest in doing things"}
    ]
    prov_b = [
        {
            "class": "PHQ9",
            "name": "phq9_fatigue",
            "description": "Feeling tired or having little energy",
        }
    ]

    hash_a, _ = compute_identity_hash(sem, prov_a, ontology_anchored=False)
    hash_b, _ = compute_identity_hash(sem, prov_b, ontology_anchored=False)
    assert hash_a != hash_b


def test_sex_merge_same_ontology():
    """Sex from BIDS + DANDI: same response_options + same ontology → same hash."""
    sem = {
        "data_type": "string",
        "response_options": [{"value": "female"}, {"value": "male"}, {"value": "other"}],
    }
    prov_a = [{"class": "participant", "name": "sex", "description": "Biological sex"}]
    prov_b = [{"class": "BioSample", "name": "sex", "description": "Sex of the subject"}]

    hash_a, _ = compute_identity_hash(
        sem, prov_a, ontology_anchored=True, primary_ontology_uri="PATO:0000047"
    )
    hash_b, _ = compute_identity_hash(
        sem, prov_b, ontology_anchored=True, primary_ontology_uri="PATO:0000047"
    )
    assert hash_a == hash_b  # merged!


def test_determine_hash_mode_exact_match():
    anns = [_onto_ann("http://example.org/X", "skos:exactMatch")]
    anchored, uri = determine_hash_mode(anns)
    assert anchored is True
    assert uri == "http://example.org/X"


def test_determine_hash_mode_element_match():
    anns = [_onto_ann("http://example.org/X", "skos:closeMatch", "element_match")]
    anchored, uri = determine_hash_mode(anns)
    assert anchored is True


def test_determine_hash_mode_close_match_concept():
    """closeMatch + concept_match → fallback (not anchored)."""
    anns = [_onto_ann("http://example.org/X", "skos:closeMatch", "concept_match")]
    anchored, _ = determine_hash_mode(anns)
    assert anchored is False


def test_determine_hash_mode_no_annotations():
    anchored, uri = determine_hash_mode(None)
    assert anchored is False
    assert uri is None


def test_determine_hash_mode_empty_list():
    anchored, uri = determine_hash_mode([])
    assert anchored is False
    assert uri is None
