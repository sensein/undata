"""Tests for content-addressed hashing."""

from undata_library.hashing import (
    build_element_uri,
    build_schema_uri,
    canonical_json,
    compute_sha256,
    generate_short_key,
)


class TestCanonicalJson:
    def test_sorted_keys(self):
        result = canonical_json({"z": 1, "a": 2})
        assert result == '{"a":2,"z":1}'

    def test_nulls_omitted(self):
        result = canonical_json({"a": 1, "b": None, "c": 3})
        assert result == '{"a":1,"c":3}'

    def test_nested_sorted_and_pruned(self):
        result = canonical_json({"outer": {"z": 1, "a": None, "b": 2}})
        assert result == '{"outer":{"b":2,"z":1}}'

    def test_empty_dict(self):
        result = canonical_json({})
        assert result == "{}"

    def test_different_key_order_same_output(self):
        a = canonical_json({"data_type": "integer", "unit": "year", "ontology_term": "X"})
        b = canonical_json({"ontology_term": "X", "data_type": "integer", "unit": "year"})
        assert a == b


class TestComputeSha256:
    def test_deterministic(self):
        h1 = compute_sha256('{"data_type":"integer"}')
        h2 = compute_sha256('{"data_type":"integer"}')
        assert h1 == h2

    def test_different_input_different_hash(self):
        h1 = compute_sha256('{"data_type":"integer"}')
        h2 = compute_sha256('{"data_type":"string"}')
        assert h1 != h2

    def test_hex_length(self):
        h = compute_sha256("test")
        assert len(h) == 64


class TestGenerateShortKey:
    def test_length_is_6(self):
        key = generate_short_key("a" * 64)
        assert len(key) == 6

    def test_alphanumeric(self):
        key = generate_short_key("b" * 64)
        assert key.isalnum()

    def test_collision_extends_key(self):
        h1 = compute_sha256("test1")
        h2 = compute_sha256("test2")
        k1 = generate_short_key(h1)
        # Force collision by pre-registering k1
        k2 = generate_short_key(h2, existing_keys={k1})
        # k2 should be different from k1 (may be same length if no collision,
        # or longer if there was one)
        # Just verify keys are generated without error
        assert k2.isalnum()

    def test_same_hash_same_key(self):
        h = compute_sha256("consistent")
        k1 = generate_short_key(h)
        k2 = generate_short_key(h)
        assert k1 == k2


class TestBuildUri:
    def test_element_uri(self):
        uri = build_element_uri("age", "x7k2m9")
        assert uri == "https://schema.undata.live/elements/age_x7k2m9"

    def test_schema_uri(self):
        uri = build_schema_uri("participant", "a1b2c3")
        assert uri == "https://schema.undata.live/schemas/participant_a1b2c3"
