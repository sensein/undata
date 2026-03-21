"""Tests for schema provenance alignment with element provenance."""

from undata_library.models import SchemaProvenance


def test_schema_provenance_has_prov_o_fields():
    """SchemaProvenance has the same PROV-O fields as ProvenanceEntry."""
    prov = SchemaProvenance(
        source="bids",
        name="Participant",
        generated_at="2026-03-20T00:00:00Z",
        attributed_to="urn:undata:ingestion-pipeline",
        activity="ingestion",
        derived_from=None,
    )
    assert prov.generated_at == "2026-03-20T00:00:00Z"
    assert prov.attributed_to == "urn:undata:ingestion-pipeline"
    assert prov.activity == "ingestion"
    assert prov.derived_from is None


def test_schema_provenance_has_source_ref():
    """SchemaProvenance accepts source_ref."""
    from undata_library.models import SourceRef

    ref = SourceRef(
        repo="https://github.com/bids-standard/bids-specification",
        committish="v1.9.0",
        file="schema/objects/entities.yaml",
        checksum="abc123",
    )
    prov = SchemaProvenance(
        source="bids",
        name="Participant",
        source_ref=ref,
    )
    assert prov.source_ref is not None
    assert prov.source_ref.repo == "https://github.com/bids-standard/bids-specification"
    assert prov.source_ref.committish == "v1.9.0"
