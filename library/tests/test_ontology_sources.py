"""Tests for ontology source management — loading, checksums, deduplication."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from undata_library.ontology_store import OntologyStore


@pytest.fixture
def store(tmp_path):
    return OntologyStore(tmp_path / "test-store")


@pytest.fixture
def sample_ttl(tmp_path):
    """Create a minimal TTL ontology file."""
    ttl = tmp_path / "test.ttl"
    ttl.write_text(
        """@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix test: <http://example.org/test/> .

test:Term1 a owl:Class ; rdfs:label "Alpha Term" .
test:Term2 a owl:Class ; rdfs:label "Beta Term" .
test:Term3 a owl:Class ; rdfs:label "Gamma Term" .
""",
        encoding="utf-8",
    )
    return ttl


def test_add_source_loads_terms(store, sample_ttl):
    result = store.add_source("test-onto", sample_ttl, fmt="ttl")
    assert result["name"] == "test-onto"
    assert result["term_count"] == 3
    assert result["checksum"] is not None
    assert "skipped" not in result


def test_add_source_idempotent(store, sample_ttl):
    """Same file loaded twice should skip the second time (checksum match)."""
    r1 = store.add_source("test-onto", sample_ttl, fmt="ttl")
    r2 = store.add_source("test-onto", sample_ttl, fmt="ttl")
    assert r1["term_count"] == 3
    assert r2.get("skipped") is True
    assert r2["checksum"] == r1["checksum"]


def test_add_source_reloads_on_change(store, sample_ttl):
    """Changed file should reload (different checksum)."""
    r1 = store.add_source("test-onto", sample_ttl, fmt="ttl")
    assert r1["term_count"] == 3

    # Modify the file
    sample_ttl.write_text(
        sample_ttl.read_text()
        + '\n<http://example.org/test/Term4> a <http://www.w3.org/2002/07/owl#Class> ; <http://www.w3.org/2000/01/rdf-schema#label> "Delta Term" .\n',
        encoding="utf-8",
    )
    r2 = store.add_source("test-onto", sample_ttl, fmt="ttl")
    assert r2["term_count"] == 4
    assert r2["checksum"] != r1["checksum"]
    assert "skipped" not in r2


def test_list_loaded_no_duplicates(store, sample_ttl):
    """list_loaded should never return duplicate names."""
    store.add_source("test-onto", sample_ttl, fmt="ttl")
    # Simulate what used to cause duplicates
    store.add_source("test-onto", sample_ttl, fmt="ttl")

    loaded = store.list_loaded()
    names = [entry["name"] for entry in loaded]
    assert len(names) == len(set(names)), f"Duplicate names: {names}"
    assert "test-onto" in names


def test_source_meta_has_checksum(store, sample_ttl):
    store.add_source("test-onto", sample_ttl, fmt="ttl")
    meta = store._get_source_meta("test-onto")
    assert meta is not None
    assert meta["checksum"] is not None
    assert meta["term_count"] == 3
    assert meta["format"] == "ttl"


def test_dicom_ttl_generation():
    """DICOM TTL generator produces valid terms."""
    try:
        from undata_library.adapters.standalone_scripts.dicom_to_ttl import generate_dicom_ttl
    except ImportError:
        pytest.skip("pydicom not installed")

    tmp = Path(tempfile.mktemp(suffix=".ttl"))
    try:
        generate_dicom_ttl(tmp)
        content = tmp.read_text()
        assert "a owl:Class" in content
        assert "rdfs:label" in content
        # Should have 4000+ DICOM tags
        count = content.count("a owl:Class")
        assert count > 4000, f"Expected >4000 DICOM tags, got {count}"
    finally:
        tmp.unlink(missing_ok=True)
