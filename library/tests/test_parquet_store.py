"""Tests for ParquetStore — Parquet-based entity storage."""

import json

import pytest

from undata_library.storage.parquet_store import ParquetStore


@pytest.fixture
def store(tmp_path):
    return ParquetStore(tmp_path)


def _make_entity(name: str, source: str = "test", sha: str | None = None, **extra):
    return {
        "sha256": sha or f"sha_{name}",
        "file_name": f"{name}.yaml",
        "semantic": {"data_type": "string", "description": f"test {name}", **extra},
        "provenance": [{"source": source, "class": "Test", "name": name}],
        "ontology_annotations": [],
    }


class TestWriteAndRead:
    def test_write_batch_creates_parquet(self, store, tmp_path):
        entities = [_make_entity("age"), _make_entity("sex")]
        written = store.write_batch("elements", entities, source="test")
        assert written == 2
        assert (tmp_path / "elements" / "test.parquet").exists()

    def test_read_by_sha256(self, store):
        store.write_batch("elements", [_make_entity("age")], source="test")
        result = store.read("elements", "sha_age")
        assert result is not None
        assert result["sha256"] == "sha_age"
        assert result["file_name"] == "age.yaml"

    def test_read_by_prefix(self, store):
        store.write_batch("elements", [_make_entity("age")], source="test")
        result = store.read("elements", "sha_a")
        assert result is not None
        assert result["sha256"] == "sha_age"

    def test_read_not_found(self, store):
        store.write_batch("elements", [_make_entity("age")], source="test")
        assert store.read("elements", "nonexistent") is None

    def test_semantic_fields_flattened(self, store):
        store.write_batch("elements", [_make_entity("age", data_type="integer")], source="test")
        result = store.read("elements", "sha_age")
        assert result["data_type"] == "integer"
        assert result["description"] == "test age"


class TestDeduplication:
    def test_same_sha_merges_provenance(self, store):
        e1 = _make_entity("age", source="bids", sha="shared_sha")
        e2 = _make_entity("age", source="nwb", sha="shared_sha")
        store.write_batch("elements", [e1], source="bids")
        store.write_batch("elements", [e2], source="nwb")
        # Read from bids file (where first write happened + merge)
        result = store.read("elements", "shared_sha")
        assert result is not None
        prov = result["provenance"]
        sources = [p["source"] for p in prov]
        assert "bids" in sources

    def test_dedup_within_batch(self, store):
        e1 = _make_entity("age", source="s1", sha="dup_sha")
        e2 = _make_entity("age", source="s2", sha="dup_sha")
        store.write_batch("elements", [e1, e2], source="mixed")
        assert store.count("elements") == 1


class TestListAndCount:
    def test_list_all(self, store):
        store.write_batch("elements", [_make_entity("a"), _make_entity("b")], source="test")
        items = list(store.list("elements"))
        assert len(items) == 2

    def test_list_by_source(self, store):
        store.write_batch("elements", [_make_entity("a")], source="bids")
        store.write_batch("elements", [_make_entity("b")], source="nwb")
        bids = list(store.list("elements", source="bids"))
        assert len(bids) == 1
        assert bids[0]["sha256"] == "sha_a"

    def test_count(self, store):
        store.write_batch("elements", [_make_entity(f"e{i}") for i in range(100)], source="test")
        assert store.count("elements") == 100

    def test_count_by_source(self, store):
        store.write_batch("elements", [_make_entity("a")], source="s1")
        store.write_batch("elements", [_make_entity("b")], source="s2")
        assert store.count("elements", source="s1") == 1
        assert store.count("elements", source="s2") == 1


class TestIndex:
    def test_build_index(self, store, tmp_path):
        store.write_batch("elements", [_make_entity("a")], source="bids")
        store.write_batch("elements", [_make_entity("b")], source="nwb")
        index_path = store.build_index("elements")
        assert index_path.exists()
        import pyarrow.parquet as pq
        table = pq.read_table(index_path)
        assert table.num_rows == 2


class TestScaleAndSize:
    def test_10k_entities_roundtrip(self, store):
        """Write 10K entities, read back, verify count."""
        entities = [_make_entity(f"elem_{i:05d}", sha=f"sha10k_{i:05d}") for i in range(10_000)]
        store.write_batch("elements", entities, source="scale_test")
        assert store.count("elements") == 10_000
        # Spot check
        assert store.read("elements", "sha10k_05000") is not None

    def test_parquet_smaller_than_yaml(self, store, tmp_path):
        """Parquet file should be significantly smaller than equivalent YAML."""
        import yaml
        entities = [_make_entity(f"elem_{i:05d}", sha=f"sha_size_{i:05d}") for i in range(1_000)]
        store.write_batch("elements", entities, source="size_test")

        parquet_size = (tmp_path / "elements" / "size_test.parquet").stat().st_size

        # Estimate YAML size
        yaml_size = sum(
            len(yaml.dump(e, default_flow_style=False).encode())
            for e in entities
        )

        ratio = yaml_size / parquet_size
        assert ratio > 2, f"Parquet should be >2x smaller than YAML, got {ratio:.1f}x"


class TestEntityTypes:
    def test_schemas(self, store):
        entity = {
            "sha256": "schema_sha",
            "file_name": "subject.yaml",
            "semantic": {"properties": ["age", "sex"], "description": "Subject"},
            "provenance": [{"source": "bids", "class": "", "name": "Subject"}],
            "ontology_annotations": [],
        }
        store.write_batch("schemas", [entity], source="bids")
        result = store.read("schemas", "schema_sha")
        assert result is not None
        assert result["properties"] == ["age", "sex"]

    def test_values(self, store):
        entity = {
            "sha256": "val_sha",
            "file_name": "male.yaml",
            "semantic": {"value_type": "categorical", "label": "male"},
            "provenance": [{"source": "bids", "class": "", "name": "male"}],
            "ontology_annotations": [],
        }
        store.write_batch("values", [entity], source="bids")
        assert store.count("values") == 1

    def test_valuesets(self, store):
        entity = {
            "sha256": "vs_sha",
            "file_name": "sex_options.yaml",
            "semantic": {"name": "sex_options", "members": ["male", "female"]},
            "provenance": [{"source": "bids", "class": "", "name": "sex_options"}],
            "ontology_annotations": [],
        }
        store.write_batch("valuesets", [entity], source="bids")
        result = store.read("valuesets", "vs_sha")
        assert result["members"] == ["male", "female"]
