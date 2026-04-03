"""Test enrichment species precision — genus removed when species exists."""

from undata_library.enrich import _prefer_species_over_genus


def test_species_preferred_over_genus():
    """When both genus and species match, genus is removed."""
    annotations = [
        {
            "term_uri": "http://purl.obolibrary.org/obo/NCBITaxon_10088",
            "term_label": "Mus",
            "score": 0.85,
            "primary": True,
        },
        {
            "term_uri": "http://purl.obolibrary.org/obo/NCBITaxon_10090",
            "term_label": "Mus musculus",
            "score": 0.82,
            "primary": False,
        },
        {
            "term_uri": "http://purl.obolibrary.org/obo/NCIT_C12345",
            "term_label": "Something else",
            "score": 0.80,
            "primary": False,
        },
    ]
    filtered = _prefer_species_over_genus(annotations)
    labels = [a["term_label"] for a in filtered]
    assert "Mus musculus" in labels
    assert "Mus" not in labels
    assert "Something else" in labels


def test_no_genus_no_change():
    """When no genus/species overlap, nothing removed."""
    annotations = [
        {
            "term_uri": "http://purl.obolibrary.org/obo/NCBITaxon_9606",
            "term_label": "Homo sapiens",
            "score": 0.9,
        },
        {
            "term_uri": "http://purl.obolibrary.org/obo/NCIT_C100",
            "term_label": "Age",
            "score": 0.85,
        },
    ]
    filtered = _prefer_species_over_genus(annotations)
    assert len(filtered) == 2


def test_non_ncbitaxon_unaffected():
    """Non-NCBITaxon annotations are never removed."""
    annotations = [
        {
            "term_uri": "http://purl.obolibrary.org/obo/NCIT_C100",
            "term_label": "Mouse",
            "score": 0.9,
        },
        {
            "term_uri": "http://purl.obolibrary.org/obo/NCIT_C200",
            "term_label": "Mouse model",
            "score": 0.85,
        },
    ]
    filtered = _prefer_species_over_genus(annotations)
    assert len(filtered) == 2
