"""Tests for commit stage (rehash → Parquet registry)."""

from undata_library.commit import commit_staged
from undata_library.staging import create_staging_dir, write_staged_batch
from undata_library.storage.parquet_store import ParquetStore


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


def test_committed_entity_has_sha256(tmp_path):
    staging = create_staging_dir(tmp_path, "run1")
    write_staged_batch(
        staging,
        "elements",
        [
            {
                "semantic": {"data_type": "string"},
                "provenance": [
                    {"source": "test", "class": "X", "name": "age", "description": "Age"}
                ],
            }
        ],
        source="test",
    )

    output = tmp_path / "output"
    output.mkdir()
    stats = commit_staged(staging, output)
    assert stats["committed"] >= 1

    store = ParquetStore(output)
    entities = list(store.list("elements"))
    assert len(entities) >= 1
    assert entities[0].get("sha256")
    assert len(entities[0]["sha256"]) == 64


def test_ontology_anchored_merge(tmp_path):
    staging = create_staging_dir(tmp_path, "run1")
    write_staged_batch(
        staging,
        "elements",
        [
            {
                "semantic": {
                    "data_type": "float",
                    "unit": "year",
                    "ontology_annotations": [_ann("http://example.org/AGE")],
                },
                "provenance": [{"source": "bids", "class": "X", "name": "age"}],
            },
            {
                "semantic": {
                    "data_type": "float",
                    "unit": "year",
                    "ontology_annotations": [_ann("http://example.org/AGE")],
                },
                "provenance": [{"source": "nwb", "class": "Y", "name": "age"}],
            },
        ],
        source="test",
    )

    output = tmp_path / "output"
    output.mkdir()
    stats = commit_staged(staging, output)
    assert stats["committed"] + stats["merged"] >= 1

    store = ParquetStore(output)
    entities = list(store.list("elements"))
    assert len(entities) >= 1


def test_fallback_different_description_separate(tmp_path):
    staging = create_staging_dir(tmp_path, "run1")
    write_staged_batch(
        staging,
        "elements",
        [
            {
                "semantic": {"data_type": "string", "description": "First name"},
                "provenance": [{"source": "s1", "class": "A", "name": "name"}],
            },
            {
                "semantic": {"data_type": "string", "description": "Last name"},
                "provenance": [{"source": "s2", "class": "B", "name": "name"}],
            },
        ],
        source="test",
    )

    output = tmp_path / "output"
    output.mkdir()
    stats = commit_staged(staging, output)
    assert stats["committed"] + stats["merged"] >= 2

    store = ParquetStore(output)
    entities = list(store.list("elements"))
    assert len(entities) >= 2
    sha_set = {e["sha256"] for e in entities}
    assert len(sha_set) >= 2  # Different descriptions → different hashes


def test_staging_dir_deleted_after_commit(tmp_path):
    staging = create_staging_dir(tmp_path, "run1")
    write_staged_batch(
        staging,
        "elements",
        [
            {
                "semantic": {"data_type": "string"},
                "provenance": [{"source": "test", "class": "X", "name": "x"}],
            }
        ],
        source="test",
    )

    output = tmp_path / "output"
    output.mkdir()
    commit_staged(staging, output)
    assert not staging.exists()


def test_committed_entity_has_embedding(tmp_path):
    """Committed entities should have embeddings (if sentence-transformers available)."""
    staging = create_staging_dir(tmp_path, "run1")
    write_staged_batch(
        staging,
        "elements",
        [
            {
                "semantic": {"data_type": "float", "unit": "year"},
                "provenance": [
                    {
                        "source": "test",
                        "class": "Subject",
                        "name": "age",
                        "description": "Age of participant in years",
                    }
                ],
            }
        ],
        source="test",
    )

    output = tmp_path / "output"
    output.mkdir()
    commit_staged(staging, output)

    store = ParquetStore(output)
    entities = list(store.list("elements"))
    assert len(entities) >= 1
    emb = entities[0].get("embedding")
    if emb is not None:
        assert isinstance(emb, list)
        assert len(emb) == 384
