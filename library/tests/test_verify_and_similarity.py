"""Tests for ontology verification and semantic similarity."""

import yaml

from undata_library.similarity import (
    compute_similarity,
    range_overlap_score,
    valueset_jaccard,
)
from undata_library.verify import verify_elements
from undata_library.ontology_cache import OntologyCache


class TestRangeOverlap:
    def test_identical_ranges(self):
        assert range_overlap_score(0, 100, 0, 100) == 1.0

    def test_no_overlap(self):
        assert range_overlap_score(0, 50, 60, 100) == 0.0

    def test_partial_overlap(self):
        score = range_overlap_score(0, 100, 50, 150)
        assert 0.0 < score < 1.0

    def test_none_values(self):
        assert range_overlap_score(None, 100, 0, 100) == 0.0


class TestValuesetJaccard:
    def test_identical(self):
        assert valueset_jaccard(["a", "b", "c"], ["a", "b", "c"]) == 1.0

    def test_no_overlap(self):
        assert valueset_jaccard(["a", "b"], ["c", "d"]) == 0.0

    def test_partial(self):
        score = valueset_jaccard(["a", "b", "c"], ["b", "c", "d"])
        assert 0.4 < score < 0.7  # 2/4

    def test_empty(self):
        assert valueset_jaccard([], ["a"]) == 0.0


class TestComputeSimilarity:
    def test_identical_elements(self):
        elem = {
            "semantic": {"data_type": "string", "ontology_term": "http://example.org/X"},
            "provenance": [{"name": "field_x", "source": "a"}],
        }
        result = compute_similarity(elem, elem)
        # ontology_match=1.0 (0.4) + semantic_embedding=1.0 (0.3) = 0.7 without ranges/valuesets
        assert result["score"] >= 0.7
        assert result["components"]["ontology_match"] == 1.0
        assert result["components"]["semantic_embedding"] >= 0.99

    def test_same_name_different_type(self):
        elem_a = {
            "semantic": {"data_type": "string"},
            "provenance": [{"name": "age", "source": "a"}],
        }
        elem_b = {
            "semantic": {"data_type": "integer"},
            "provenance": [{"name": "age", "source": "b"}],
        }
        result = compute_similarity(elem_a, elem_b)
        assert result["components"]["semantic_embedding"] > 0.9
        assert result["components"]["ontology_match"] == 0.0

    def test_shared_valueset_boosts_score(self):
        elem_a = {
            "semantic": {
                "data_type": "string",
                "response_options": [{"value": "male"}, {"value": "female"}],
            },
            "provenance": [{"name": "sex", "source": "a"}],
        }
        elem_b = {
            "semantic": {
                "data_type": "string",
                "response_options": [{"value": "male"}, {"value": "female"}, {"value": "other"}],
            },
            "provenance": [{"name": "sex", "source": "b"}],
        }
        result = compute_similarity(elem_a, elem_b)
        assert result["components"]["valueset_jaccard"] > 0.5

    def test_no_similarity(self):
        elem_a = {
            "semantic": {"data_type": "string"},
            "provenance": [{"name": "completely_different", "source": "a"}],
        }
        elem_b = {
            "semantic": {"data_type": "integer"},
            "provenance": [{"name": "unrelated_field", "source": "b"}],
        }
        result = compute_similarity(elem_a, elem_b)
        assert result["score"] < 0.5


class TestVerify:
    def test_valid_term_passes(self, tmp_path):
        # Create a minimal cache
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / "test.yaml").write_text(
            yaml.dump(
                {
                    "ontology": "TEST",
                    "terms": {
                        "http://example.org/age": {
                            "label": "Age",
                            "synonyms": ["age"],
                            "parents": [],
                            "deprecated": False,
                        },
                    },
                }
            )
        )

        # Create an element
        elements_dir = tmp_path / "elements"
        elements_dir.mkdir()
        (elements_dir / "age_test.yaml").write_text(
            yaml.dump(
                {
                    "semantic": {"data_type": "float", "ontology_term": "http://example.org/age"},
                    "provenance": [{"source": "test", "class": "T", "name": "age"}],
                }
            )
        )

        cache = OntologyCache(cache_dir)
        warnings = verify_elements(elements_dir, cache=cache)
        assert len(warnings) == 0

    def test_missing_term_warns(self, tmp_path):
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / "test.yaml").write_text(yaml.dump({"ontology": "TEST", "terms": {}}))

        elements_dir = tmp_path / "elements"
        elements_dir.mkdir()
        (elements_dir / "missing_test.yaml").write_text(
            yaml.dump(
                {
                    "semantic": {
                        "data_type": "string",
                        "ontology_term": "http://example.org/nonexistent",
                    },
                    "provenance": [{"source": "test", "class": "T", "name": "missing"}],
                }
            )
        )

        cache = OntologyCache(cache_dir)
        warnings = verify_elements(elements_dir, cache=cache)
        assert len(warnings) == 1
        assert "not found" in warnings[0]["issue"]

    def test_deprecated_term_warns(self, tmp_path):
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / "test.yaml").write_text(
            yaml.dump(
                {
                    "ontology": "TEST",
                    "terms": {
                        "http://example.org/old": {
                            "label": "Old Term",
                            "synonyms": [],
                            "parents": [],
                            "deprecated": True,
                        },
                    },
                }
            )
        )

        elements_dir = tmp_path / "elements"
        elements_dir.mkdir()
        (elements_dir / "old_test.yaml").write_text(
            yaml.dump(
                {
                    "semantic": {"data_type": "string", "ontology_term": "http://example.org/old"},
                    "provenance": [{"source": "test", "class": "T", "name": "old"}],
                }
            )
        )

        cache = OntologyCache(cache_dir)
        warnings = verify_elements(elements_dir, cache=cache)
        assert any("deprecated" in w["issue"] for w in warnings)
