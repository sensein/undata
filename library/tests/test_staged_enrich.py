"""Tests for staged in-place enrichment across all entity types (T029)."""

import yaml

from undata_library.enrich import (
    _update_entity_in_place,
    enrich_all,
    enrich_elements,
    enrich_schemas,
    enrich_values,
)


def _write_yaml(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8")


def _make_staging(tmp_path):
    """Create a staging dir with one entity per type."""
    staging = tmp_path / "staging"
    _write_yaml(
        staging / "elements" / "age.yaml",
        {
            "semantic": {"data_type": "float", "unit": "year"},
            "provenance": [{"source": "bids", "class": "participant", "name": "age"}],
        },
    )
    _write_yaml(
        staging / "values" / "male.yaml",
        {
            "semantic": {"label": "male", "value_type": "categorical"},
            "provenance": [{"source": "bids", "class": "participant", "name": "male"}],
        },
    )
    _write_yaml(
        staging / "schemas" / "participant.yaml",
        {
            "semantic": {"properties": ["age", "sex"], "description": "Participant"},
            "provenance": [{"source": "bids", "class": "participant", "name": "participant"}],
        },
    )
    _write_yaml(
        staging / "valuesets" / "sex.yaml",
        {
            "semantic": {"name": "sex", "members": []},
            "provenance": [{"source": "bids", "class": "participant", "name": "sex"}],
        },
    )
    return staging


class TestNoNewFilesCreated:
    """T029a: enrichment never creates new files."""

    def test_element_enrichment_no_new_files(self, tmp_path):
        staging = tmp_path / "staging"
        _write_yaml(
            staging / "elements" / "age.yaml",
            {
                "semantic": {"data_type": "float"},
                "provenance": [{"source": "test", "class": "T", "name": "age"}],
            },
        )
        before = set((staging / "elements").glob("*.yaml"))

        enrich_elements(staging_dir=staging)

        after = set((staging / "elements").glob("*.yaml"))
        assert before == after

    def test_value_enrichment_no_new_files(self, tmp_path):
        staging = tmp_path / "staging"
        _write_yaml(
            staging / "values" / "male.yaml",
            {
                "semantic": {"label": "male", "value_type": "categorical"},
                "provenance": [{"source": "test", "class": "T", "name": "male"}],
            },
        )
        before = set((staging / "values").glob("*.yaml"))

        enrich_values(staging_dir=staging)

        after = set((staging / "values").glob("*.yaml"))
        assert before == after

    def test_schema_enrichment_no_new_files(self, tmp_path):
        staging = tmp_path / "staging"
        _write_yaml(
            staging / "schemas" / "participant.yaml",
            {
                "semantic": {"properties": [], "description": "Test"},
                "provenance": [{"source": "test", "class": "T", "name": "p"}],
            },
        )
        before = set((staging / "schemas").glob("*.yaml"))

        enrich_schemas(staging_dir=staging)

        after = set((staging / "schemas").glob("*.yaml"))
        assert before == after


class TestValueDomainSet:
    """T029c: value_domain is set after enrichment."""

    def test_integer_gets_numeric(self, tmp_path):
        staging = tmp_path / "staging"
        _write_yaml(
            staging / "elements" / "count.yaml",
            {
                "semantic": {"data_type": "integer"},
                "provenance": [{"source": "test", "class": "T", "name": "count"}],
            },
        )

        stats = enrich_elements(staging_dir=staging)
        assert stats["value_domain_set"] == 1

        data = yaml.safe_load((staging / "elements" / "count.yaml").read_text())
        assert data["semantic"]["value_domain"] == "numeric"

    def test_categorical_from_response_options(self, tmp_path):
        staging = tmp_path / "staging"
        _write_yaml(
            staging / "elements" / "sex.yaml",
            {
                "semantic": {
                    "data_type": "string",
                    "response_options": [{"value": "male"}, {"value": "female"}],
                },
                "provenance": [{"source": "test", "class": "T", "name": "sex"}],
            },
        )

        stats = enrich_elements(staging_dir=staging)
        assert stats["value_domain_set"] == 1

        data = yaml.safe_load((staging / "elements" / "sex.yaml").read_text())
        assert data["semantic"]["value_domain"] == "categorical"


class TestIdempotency:
    """T029h: enrichment is idempotent."""

    def test_enrich_elements_idempotent(self, tmp_path):
        staging = tmp_path / "staging"
        _write_yaml(
            staging / "elements" / "age.yaml",
            {
                "semantic": {"data_type": "float", "value_domain": "numeric"},
                "provenance": [{"source": "test", "class": "T", "name": "age"}],
            },
        )

        stats1 = enrich_elements(staging_dir=staging)
        stats2 = enrich_elements(staging_dir=staging)

        assert stats1["unchanged"] == 1
        assert stats2["unchanged"] == 1

    def test_enrich_values_idempotent(self, tmp_path):
        staging = tmp_path / "staging"
        _write_yaml(
            staging / "values" / "male.yaml",
            {
                "semantic": {
                    "label": "male",
                    "value_type": "categorical",
                    "ontology_annotations": [{"term_uri": "http://x", "primary": True}],
                },
                "provenance": [{"source": "test", "class": "T", "name": "male"}],
            },
        )

        stats = enrich_values(staging_dir=staging)
        assert stats["unchanged"] == 1

    def test_enrich_schemas_idempotent(self, tmp_path):
        staging = tmp_path / "staging"
        _write_yaml(
            staging / "schemas" / "p.yaml",
            {
                "semantic": {
                    "properties": [],
                    "ontology_annotations": [{"term_uri": "http://x", "primary": True}],
                },
                "provenance": [{"source": "test", "class": "T", "name": "p"}],
            },
        )

        stats = enrich_schemas(staging_dir=staging)
        assert stats["unchanged"] == 1


class TestEnrichAll:
    """T029g: dependency order enforced in enrich_all."""

    def test_enrich_all_returns_all_types(self, tmp_path):
        staging = _make_staging(tmp_path)
        results = enrich_all(staging_dir=staging)

        assert "elements" in results
        assert "values" in results
        assert "valuesets" in results
        assert "schemas" in results

    def test_enrich_all_processes_elements(self, tmp_path):
        staging = _make_staging(tmp_path)
        results = enrich_all(staging_dir=staging)

        assert results["elements"]["total"] == 1

    def test_enrich_all_processes_values(self, tmp_path):
        staging = _make_staging(tmp_path)
        results = enrich_all(staging_dir=staging)

        assert results["values"]["total"] == 1

    def test_enrich_all_empty_staging(self, tmp_path):
        staging = tmp_path / "empty_staging"
        staging.mkdir()

        results = enrich_all(staging_dir=staging)

        for entity_type in ("elements", "values", "valuesets", "schemas"):
            assert results[entity_type]["total"] == 0


class TestUpdateInPlace:
    """Direct tests of _update_entity_in_place."""

    def test_adds_description(self, tmp_path):
        f = tmp_path / "e.yaml"
        _write_yaml(
            f,
            {
                "semantic": {"data_type": "string"},
                "provenance": [{"source": "t", "class": "T", "name": "x"}],
            },
        )

        changed = _update_entity_in_place(f, description="A test field")
        assert changed is True

        data = yaml.safe_load(f.read_text())
        assert data["semantic"]["description"] == "A test field"

    def test_skips_existing_description(self, tmp_path):
        f = tmp_path / "e.yaml"
        _write_yaml(
            f,
            {
                "semantic": {"data_type": "string", "description": "Original"},
                "provenance": [{"source": "t", "class": "T", "name": "x"}],
            },
        )

        changed = _update_entity_in_place(f, description="New")
        assert changed is False

        data = yaml.safe_load(f.read_text())
        assert data["semantic"]["description"] == "Original"

    def test_multiple_updates_at_once(self, tmp_path):
        f = tmp_path / "e.yaml"
        _write_yaml(
            f,
            {
                "semantic": {"data_type": "float"},
                "provenance": [{"source": "t", "class": "T", "name": "x"}],
            },
        )

        anns = [{"term_uri": "http://example.org/Y", "primary": True}]
        changed = _update_entity_in_place(
            f, ontology_annotations=anns, value_domain="numeric", description="Test"
        )
        assert changed is True

        data = yaml.safe_load(f.read_text())
        assert data["semantic"]["ontology_annotations"] == anns
        assert data["semantic"]["value_domain"] == "numeric"
        assert data["semantic"]["description"] == "Test"
