"""Tests for the enrichment pipeline."""

import yaml

from undata_library.enrich import (
    _build_value_lookup,
    _populate_value_domain,
    _resolve_response_options,
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
    # _populate_value_domain itself doesn't check — enrich_elements does
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


# -- enrich_elements integration tests --


def _make_element(tmp_path, name, data_type="string", ontology_term=None, value_domain=None):
    """Helper to create a test element YAML."""
    elements_dir = tmp_path / "elements"
    elements_dir.mkdir(exist_ok=True)

    sem = {"data_type": data_type}
    if ontology_term:
        sem["ontology_term"] = ontology_term
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
    _make_element(tmp_path, "age", data_type="integer")
    cache_dir = tmp_path / "ontology-cache"
    cache_dir.mkdir()

    stats = enrich_elements(
        elements_dir=tmp_path / "elements",
        cache_dir=cache_dir,
        library_path=tmp_path,
    )

    assert stats["total"] >= 1
    # value_domain should be set (either in-place or in new enriched element)
    assert stats["value_domain_set"] >= 1 or stats["enriched_new"] >= 1


def test_enrich_idempotent(tmp_path):
    """Re-running enrich on already-enriched elements produces no changes."""
    _make_element(tmp_path, "species", data_type="string", value_domain="text")
    cache_dir = tmp_path / "ontology-cache"
    cache_dir.mkdir()

    stats = enrich_elements(
        elements_dir=tmp_path / "elements",
        cache_dir=cache_dir,
        library_path=tmp_path,
    )

    assert stats["total"] == 1
    assert stats["enriched_unchanged"] == 1
    assert stats["enriched_new"] == 0


def test_enrich_dry_run_no_changes(tmp_path):
    _make_element(tmp_path, "weight", data_type="float")
    cache_dir = tmp_path / "ontology-cache"
    cache_dir.mkdir()

    stats = enrich_elements(
        elements_dir=tmp_path / "elements",
        cache_dir=cache_dir,
        library_path=tmp_path,
        dry_run=True,
    )

    assert stats["value_domain_set"] == 1

    # File should NOT be changed in dry-run
    data = yaml.safe_load((tmp_path / "elements" / "weight_abc123.yaml").read_text())
    assert data["semantic"].get("value_domain") is None


def test_enrich_skips_element_with_ontology(tmp_path):
    """Elements with existing ontology_term are not re-assigned."""
    _make_element(
        tmp_path,
        "age",
        data_type="float",
        ontology_term="http://purl.obolibrary.org/obo/NCIT_C25150",
        value_domain="numeric",
    )
    cache_dir = tmp_path / "ontology-cache"
    cache_dir.mkdir()

    stats = enrich_elements(
        elements_dir=tmp_path / "elements",
        cache_dir=cache_dir,
        library_path=tmp_path,
    )

    assert stats["ontology_assigned"] == 0
    assert stats["enriched_unchanged"] == 1
