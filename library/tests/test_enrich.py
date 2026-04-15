"""Tests for the enrichment pipeline."""

import yaml

from undata_library.enrich import (
    _build_value_lookup,
    _populate_value_domain,
    _resolve_response_options,
    _update_entity_in_place,
    enrich_elements,
)


# -- value_domain population tests --


def test_populate_value_domain_string():
    assert _populate_value_domain({"data_type": "string"}) == "text"


def test_populate_value_domain_integer():
    assert _populate_value_domain({"data_type": "integer"}) == "numeric"


def test_populate_value_domain_float():
    assert _populate_value_domain({"data_type": "float"}) == "numeric"


def test_populate_value_domain_boolean():
    assert _populate_value_domain({"data_type": "boolean"}) == "boolean"


def test_populate_value_domain_array():
    assert _populate_value_domain({"data_type": "array"}) is None


def test_populate_value_domain_categorical_override():
    sem = {"data_type": "string", "response_options": [{"value": "a"}]}
    assert _populate_value_domain(sem) == "categorical"


def test_populate_value_domain_already_set():
    """If value_domain already set, enrich_elements skips it."""
    assert _populate_value_domain({"data_type": "string"}) == "text"


# -- response_options resolution tests --


def test_resolve_response_options_by_value():
    sem = {"response_options": [{"value": "male", "label": "Male"}]}
    lookup = {"male": "https://schema.undata.live/values/male_abc"}
    count = _resolve_response_options(sem, lookup)
    assert count == 1
    assert (
        sem["response_options"][0]["ontology_term"] == "https://schema.undata.live/values/male_abc"
    )


def test_resolve_response_options_by_label():
    sem = {"response_options": [{"value": "M", "label": "Male"}]}
    lookup = {"male": "https://schema.undata.live/values/male_abc"}
    count = _resolve_response_options(sem, lookup)
    assert count == 1


def test_resolve_response_options_already_uri():
    sem = {"response_options": [{"value": "https://existing.uri"}]}
    count = _resolve_response_options(sem, {"https://existing.uri": "x"})
    assert count == 0  # Skip URIs


def test_resolve_response_options_no_match():
    sem = {"response_options": [{"value": "unknown"}]}
    count = _resolve_response_options(sem, {"other": "x"})
    assert count == 0


# -- value lookup building tests --


def test_build_value_lookup(tmp_path):
    values_dir = tmp_path / "values"
    values_dir.mkdir()

    val = {
        "semantic": {"label": "Male", "value_type": "categorical"},
        "provenance": [{"source": "bids", "raw_value": "M"}],
    }
    (values_dir / "male_abc123.yaml").write_text(yaml.dump(val))

    lookup = _build_value_lookup(values_dir)
    assert "male" in lookup
    assert "m" in lookup  # raw_value
    assert lookup["male"].endswith("male_abc123")


# -- _update_entity_in_place tests --


def test_update_entity_in_place_adds_annotations(tmp_path):
    elem = {
        "semantic": {"data_type": "string"},
        "provenance": [{"source": "test", "class": "T", "name": "x"}],
    }
    f = tmp_path / "test.yaml"
    f.write_text(yaml.dump(elem))

    anns = [{"term_uri": "http://example.org/X", "primary": True}]
    changed = _update_entity_in_place(f, ontology_annotations=anns)
    assert changed is True

    result = yaml.safe_load(f.read_text())
    assert result["semantic"]["ontology_annotations"] == anns


def test_update_entity_in_place_adds_value_domain(tmp_path):
    elem = {
        "semantic": {"data_type": "integer"},
        "provenance": [{"source": "test", "class": "T", "name": "x"}],
    }
    f = tmp_path / "test.yaml"
    f.write_text(yaml.dump(elem))

    changed = _update_entity_in_place(f, value_domain="numeric")
    assert changed is True

    result = yaml.safe_load(f.read_text())
    assert result["semantic"]["value_domain"] == "numeric"


def test_update_entity_in_place_skips_existing_domain(tmp_path):
    elem = {
        "semantic": {"data_type": "integer", "value_domain": "numeric"},
        "provenance": [{"source": "test", "class": "T", "name": "x"}],
    }
    f = tmp_path / "test.yaml"
    f.write_text(yaml.dump(elem))

    changed = _update_entity_in_place(f, value_domain="text")
    assert changed is False


def test_update_entity_in_place_no_changes(tmp_path):
    elem = {
        "semantic": {"data_type": "string"},
        "provenance": [{"source": "test", "class": "T", "name": "x"}],
    }
    f = tmp_path / "test.yaml"
    f.write_text(yaml.dump(elem))

    changed = _update_entity_in_place(f)
    assert changed is False


# -- enrich_elements integration tests --


def _make_staged_element(staging_dir, name, data_type="string", value_domain=None):
    """Helper to create a test element YAML in staging structure."""
    elements_dir = staging_dir / "elements"
    elements_dir.mkdir(parents=True, exist_ok=True)

    sem = {"data_type": data_type}
    if value_domain:
        sem["value_domain"] = value_domain

    elem = {
        "semantic": sem,
        "provenance": [{"source": "test", "class": "TestClass", "name": name}],
    }
    path = elements_dir / f"{name}_abc123.yaml"
    path.write_text(yaml.dump(elem, default_flow_style=False))
    return path


def test_enrich_populates_value_domain(tmp_path):
    staging = tmp_path / "staging"
    _make_staged_element(staging, "age", data_type="integer")
    cache_dir = tmp_path / "ontology-cache"
    cache_dir.mkdir()

    stats = enrich_elements(staging_dir=staging, cache_dir=cache_dir)

    assert stats["total"] >= 1
    assert stats["value_domain_set"] >= 1


def test_enrich_idempotent(tmp_path):
    """Re-running enrich on already-enriched elements produces no changes."""
    staging = tmp_path / "staging"
    _make_staged_element(staging, "species", data_type="string", value_domain="text")
    cache_dir = tmp_path / "ontology-cache"
    cache_dir.mkdir()

    stats = enrich_elements(staging_dir=staging, cache_dir=cache_dir)

    assert stats["total"] == 1
    assert stats["unchanged"] == 1


def test_enrich_dry_run_no_changes(tmp_path):
    staging = tmp_path / "staging"
    _make_staged_element(staging, "weight", data_type="float")
    cache_dir = tmp_path / "ontology-cache"
    cache_dir.mkdir()

    stats = enrich_elements(staging_dir=staging, cache_dir=cache_dir, dry_run=True)

    assert stats["value_domain_set"] == 1

    # File should NOT be changed in dry-run
    data = yaml.safe_load((staging / "elements" / "weight_abc123.yaml").read_text())
    assert data["semantic"].get("value_domain") is None
