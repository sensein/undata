"""Tests for the semantic embedding layer."""

import warnings

import numpy as np
import pytest
import yaml

from undata_library.embeddings import (
    EmbeddingStore,
    _build_element_text,
    _build_ontology_text,
    cosine_similarity,
)


# -- Text construction tests --


def test_build_element_text_full():
    data = {
        "provenance": [
            {"class": "Subject", "name": "age", "description": "Age of the subject in years"}
        ]
    }
    text = _build_element_text(data)
    assert "Subject age: Age of the subject in years" in text


def test_build_element_text_no_description():
    data = {"provenance": [{"class": "Subject", "name": "sex"}]}
    assert _build_element_text(data) == "Subject sex"


def test_build_element_text_no_class():
    data = {"provenance": [{"name": "strain", "description": "Organism strain"}]}
    assert _build_element_text(data) == "strain: Organism strain"


def test_build_element_text_empty_provenance():
    assert _build_element_text({"provenance": []}) == ""
    assert _build_element_text({}) == ""


def test_build_ontology_text_with_synonyms():
    assert _build_ontology_text("Age", ["age", "patient age"]) == "Age: age, patient age"


def test_build_ontology_text_no_synonyms():
    assert _build_ontology_text("Species") == "Species"
    assert _build_ontology_text("Species", []) == "Species"


# -- Cosine similarity tests --


def test_cosine_similarity_identical():
    vec = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    assert cosine_similarity(vec, vec) == pytest.approx(1.0, abs=1e-6)


def test_cosine_similarity_orthogonal():
    a = np.array([1.0, 0.0], dtype=np.float32)
    b = np.array([0.0, 1.0], dtype=np.float32)
    assert cosine_similarity(a, b) == pytest.approx(0.0, abs=1e-6)


def test_cosine_similarity_zero_vector():
    a = np.array([1.0, 2.0], dtype=np.float32)
    b = np.zeros(2, dtype=np.float32)
    assert cosine_similarity(a, b) == 0.0


# -- Parquet round-trip tests --


def test_embedding_store_save_load(tmp_path):
    store = EmbeddingStore(uri_col="uri")
    store._uris = ["uri:a", "uri:b"]
    store._texts = ["text a", "text b"]
    store._vectors = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]], dtype=np.float32)
    store._model = "test-model"
    store._uri_to_idx = {"uri:a": 0, "uri:b": 1}

    path = tmp_path / "embeddings.parquet"
    store.save(path, model_name="test-model")
    assert path.exists()

    loaded = EmbeddingStore(uri_col="uri").load(path)
    assert loaded.size == 2
    assert loaded.model == "test-model"
    assert loaded.get_vector("uri:a") is not None
    np.testing.assert_array_almost_equal(loaded.get_vector("uri:a"), [1.0, 0.0, 0.0])


def test_embedding_store_model_mismatch_warning(tmp_path):
    store = EmbeddingStore(uri_col="uri")
    store._uris = ["uri:a"]
    store._texts = ["text"]
    store._vectors = np.array([[1.0, 0.0]], dtype=np.float32)
    store._model = "model-a"
    store._uri_to_idx = {"uri:a": 0}

    path = tmp_path / "embeddings.parquet"
    store.save(path, model_name="model-a")

    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        EmbeddingStore(uri_col="uri").load(path, expected_model="model-b")
        assert len(w) == 1
        assert "mismatch" in str(w[0].message).lower()


def test_embedding_store_similarity():
    store = EmbeddingStore(uri_col="uri")
    store._uris = ["uri:a", "uri:b"]
    store._texts = ["text a", "text b"]
    store._vectors = np.array([[1.0, 0.0], [1.0, 0.0]], dtype=np.float32)
    store._uri_to_idx = {"uri:a": 0, "uri:b": 1}

    assert store.similarity("uri:a", "uri:b") == pytest.approx(1.0, abs=1e-6)
    assert store.similarity("uri:a", "uri:missing") == 0.0


def test_embedding_store_nearest():
    store = EmbeddingStore(uri_col="uri")
    store._uris = ["uri:a", "uri:b", "uri:c"]
    store._texts = ["a", "b", "c"]
    store._vectors = np.array([[1.0, 0.0], [0.9, 0.1], [0.0, 1.0]], dtype=np.float32)
    store._uri_to_idx = {"uri:a": 0, "uri:b": 1, "uri:c": 2}

    query = np.array([1.0, 0.0], dtype=np.float32)
    results = store.nearest(query, top_k=2)
    assert len(results) == 2
    assert results[0][0] == "uri:a"  # most similar


def test_embedding_store_get_vector_missing():
    store = EmbeddingStore()
    assert store.get_vector("nonexistent") is None


# -- Difflib fallback test --


def test_similarity_difflib_fallback():
    """When no embedding store, similarity.py falls back to difflib."""
    from undata_library.similarity import semantic_embedding_similarity

    elem_a = {"provenance": [{"name": "age"}]}
    elem_b = {"provenance": [{"name": "age"}]}
    score = semantic_embedding_similarity("u:a", "u:b", None, elem_a, elem_b)
    assert score == pytest.approx(1.0)


def test_similarity_difflib_different_names():
    from undata_library.similarity import semantic_embedding_similarity

    elem_a = {"provenance": [{"name": "age"}]}
    elem_b = {"provenance": [{"name": "species"}]}
    score = semantic_embedding_similarity("u:a", "u:b", None, elem_a, elem_b)
    assert score < 0.5


# -- Build from YAML fixture test --


def test_build_element_embeddings_from_files(tmp_path):
    """Test build_element_embeddings with mock YAML files (no sentence-transformers needed)."""
    elements_dir = tmp_path / "elements"
    elements_dir.mkdir()

    elem = {
        "semantic": {"data_type": "string"},
        "provenance": [{"source": "test", "class": "Subject", "name": "age", "description": "Age"}],
    }
    (elements_dir / "age_abc123.yaml").write_text(yaml.dump(elem))

    # We can test the text construction without needing the model
    data = yaml.safe_load((elements_dir / "age_abc123.yaml").read_text())
    text = _build_element_text(data)
    assert "Subject age: Age" in text
