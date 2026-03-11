"""Unit tests for AliasDetector — must FAIL before implementation."""

from undata.alias_detection import SYNONYM_TABLE, AliasDetector, normalize_name


def test_normalize_name_strips_prefixes():
    assert normalize_name("sub_age") == "age"
    assert normalize_name("participant_age") == "age"
    assert normalize_name("subject_age") == "age"


def test_normalize_name_replaces_synonyms():
    assert normalize_name("session_id") == "visit_id"  # session→visit
    assert normalize_name("task_id") == "task_id"  # task has no synonym, unchanged


def test_synonym_table_is_populated():
    assert len(SYNONYM_TABLE) > 0
    assert "subject" in SYNONYM_TABLE or "participant" in SYNONYM_TABLE


def test_alias_detector_exact_name_match():
    """Two elements with same normalized name and compatible types are aliases."""
    elements = [
        {
            "id": "e1",
            "name": "subject_age",
            "data_type": "number",
            "multivalued": False,
            "description": "Age of subject",
            "source": {"name": "BIDS"},
        },
        {
            "id": "e2",
            "name": "participant_age",
            "data_type": "number",
            "multivalued": False,
            "description": "Age of participant",
            "source": {"name": "DANDI"},
        },
    ]
    detector = AliasDetector(backend_url="http://x", token="t", threshold=0.92)
    candidates = detector._detect_exact_aliases(elements)
    assert len(candidates) >= 1
    match = candidates[0]
    assert match.predicate == "skos:exactMatch"
    assert match.detection_method == "exact_name"


def test_alias_detector_type_gate_blocks_incompatible():
    """Elements with different data types should NOT be aliased."""
    elements = [
        {
            "id": "e1",
            "name": "subject_age",
            "data_type": "number",
            "multivalued": False,
            "description": "Age",
            "source": {"name": "BIDS"},
        },
        {
            "id": "e2",
            "name": "participant_age",
            "data_type": "string",
            "multivalued": False,
            "description": "Age",
            "source": {"name": "DANDI"},
        },
    ]
    detector = AliasDetector(backend_url="http://x", token="t", threshold=0.92)
    candidates = detector._detect_exact_aliases(elements)
    assert len(candidates) == 0


def test_alias_detector_cardinality_gate():
    """Elements with different multivalued flags should NOT be aliased."""
    elements = [
        {
            "id": "e1",
            "name": "subject_age",
            "data_type": "number",
            "multivalued": False,
            "description": "Age",
            "source": {"name": "BIDS"},
        },
        {
            "id": "e2",
            "name": "participant_age",
            "data_type": "number",
            "multivalued": True,
            "description": "Age",
            "source": {"name": "DANDI"},
        },
    ]
    detector = AliasDetector(backend_url="http://x", token="t", threshold=0.92)
    candidates = detector._detect_exact_aliases(elements)
    assert len(candidates) == 0
