"""Tests for commit stage (rehash → registry)."""

import yaml

from undata_library.commit import commit_staged
from undata_library.staging import create_staging_dir, write_staged_entity


def _ann(uri, primary=True):
    return {
        "term_uri": uri,
        "term_label": "X",
        "ontology": "test",
        "mapping_relation": "skos:exactMatch",
        "match_level": "concept_match",
        "score": 0.97,
        "model": "test",
        "primary": primary,
    }


def test_committed_file_has_content_addressed_name(tmp_path):
    staging = create_staging_dir(tmp_path, "run1")
    write_staged_entity(
        staging,
        "elements",
        {
            "semantic": {"data_type": "string"},
            "provenance": [{"source": "test", "class": "X", "name": "age", "description": "Age"}],
        },
    )

    output = tmp_path / "output"
    output.mkdir()
    stats = commit_staged(staging, output)

    assert stats["committed"] == 1
    files = list((output / "elements").glob("*.yaml"))
    assert len(files) == 1
    assert "_" in files[0].stem  # name_hash format
    assert len(files[0].stem.split("_")[-1]) == 12  # 12-hex key


def test_sha256_in_committed_file(tmp_path):
    staging = create_staging_dir(tmp_path, "run1")
    write_staged_entity(
        staging,
        "elements",
        {
            "semantic": {"data_type": "float", "unit": "year"},
            "provenance": [{"source": "bids", "class": "participant", "name": "age"}],
        },
    )

    output = tmp_path / "output"
    output.mkdir()
    commit_staged(staging, output)

    f = next((output / "elements").glob("*.yaml"))
    data = yaml.safe_load(f.read_text())
    assert "sha256" in data
    assert len(data["sha256"]) == 64


def test_ontology_anchored_merge(tmp_path):
    """Same concept from 2 sources → same hash → merged."""
    staging = create_staging_dir(tmp_path, "run1")
    ann = [_ann("http://example.org/age")]

    # Source 1
    write_staged_entity(
        staging,
        "elements",
        {
            "semantic": {"data_type": "float", "unit": "year", "ontology_annotations": ann},
            "provenance": [{"source": "bids", "class": "participant", "name": "age"}],
        },
    )
    # Source 2 — same ontology, different source name
    write_staged_entity(
        staging,
        "elements",
        {
            "semantic": {"data_type": "float", "unit": "year", "ontology_annotations": ann},
            "provenance": [{"source": "custom", "class": "Subject", "name": "subject_age"}],
        },
    )

    output = tmp_path / "output"
    output.mkdir()
    stats = commit_staged(staging, output)

    assert stats["committed"] + stats["merged"] == 2
    # Should be 1 file (merged)
    files = list((output / "elements").glob("*.yaml"))
    assert len(files) == 1
    data = yaml.safe_load(files[0].read_text())
    assert len(data["provenance"]) == 2  # combined provenance


def test_fallback_different_description_separate(tmp_path):
    """Different description → different hash → separate files."""
    staging = create_staging_dir(tmp_path, "run1")

    write_staged_entity(
        staging,
        "elements",
        {
            "semantic": {"data_type": "integer"},
            "provenance": [
                {"source": "test", "class": "PHQ9", "name": "item1", "description": "Interest"}
            ],
        },
    )
    write_staged_entity(
        staging,
        "elements",
        {
            "semantic": {"data_type": "integer"},
            "provenance": [
                {"source": "test", "class": "PHQ9", "name": "item2", "description": "Fatigue"}
            ],
        },
    )

    output = tmp_path / "output"
    output.mkdir()
    commit_staged(staging, output)

    files = list((output / "elements").glob("*.yaml"))
    assert len(files) == 2  # separate elements


def test_staging_dir_deleted_after_commit(tmp_path):
    staging = create_staging_dir(tmp_path, "run1")
    write_staged_entity(
        staging,
        "elements",
        {
            "semantic": {"data_type": "string"},
            "provenance": [{"source": "test", "class": "X", "name": "x"}],
        },
    )

    output = tmp_path / "output"
    output.mkdir()
    commit_staged(staging, output)

    assert not staging.exists()
