"""Tests for unified provenance model (ProvenanceEntry used for all entity types)."""

from undata_library.models import ProvenanceEntry, SourceRef


def test_provenance_has_prov_o_fields():
    """ProvenanceEntry has PROV-O fields for all entity types."""
    prov = ProvenanceEntry(
        source="bids",
        **{"class": "Participant"},
        name="Participant",
        generated_at="2026-03-20T00:00:00Z",
        attributed_to="urn:undata:ingestion-pipeline",
        activity="ingestion",
        derived_from=None,
    )
    assert prov.generated_at == "2026-03-20T00:00:00Z"
    assert prov.attributed_to == "urn:undata:ingestion-pipeline"
    assert prov.activity == "ingestion"


def test_provenance_has_source_ref():
    """ProvenanceEntry accepts source_ref."""
    ref = SourceRef(
        repo="https://github.com/bids-standard/bids-specification",
        committish="v1.9.0",
        file="schema/objects/entities.yaml",
        checksum="abc123",
    )
    prov = ProvenanceEntry(
        source="bids",
        **{"class": "Participant"},
        name="Participant",
        source_ref=ref,
    )
    assert prov.source_ref is not None
    assert prov.source_ref.repo == "https://github.com/bids-standard/bids-specification"
