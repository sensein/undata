"""Edge-case tests across all modules: empty inputs, malformed YAML, missing fields, Unicode."""

from undata_library.enrich import _populate_value_domain, _update_entity_in_place, enrich_elements
from undata_library.hashing import canonical_json, compute_identity_hash, compute_sha256
from undata_library.utils import safe_load_yaml, sanitize_filename, write_yaml


class TestEmptyInputs:
    def test_canonical_json_empty_dict(self):
        result = canonical_json({})
        assert result == "{}"

    def test_compute_sha256_empty_string(self):
        result = compute_sha256("")
        assert len(result) == 64  # SHA-256 hex

    def test_identity_hash_empty_semantic(self):
        sha, canonical = compute_identity_hash({}, [])
        assert len(sha) == 64

    def test_enrich_empty_staging(self, tmp_path):
        staging = tmp_path / "staging"
        staging.mkdir()
        stats = enrich_elements(staging_dir=staging)
        assert stats["total"] == 0

    def test_populate_value_domain_empty(self):
        assert _populate_value_domain({}) is None

    def test_sanitize_empty_string(self):
        assert sanitize_filename("") == ""


class TestMalformedData:
    def test_safe_load_binary_content(self, tmp_path):
        f = tmp_path / "binary.yaml"
        f.write_bytes(b"\x00\x01\x02\xff\xfe")
        assert safe_load_yaml(f) is None

    def test_update_entity_non_yaml(self, tmp_path):
        f = tmp_path / "bad.yaml"
        f.write_text("not: [valid: yaml: {{")
        result = _update_entity_in_place(f, value_domain="text")
        assert result is False

    def test_update_entity_no_semantic(self, tmp_path):
        f = tmp_path / "no_sem.yaml"
        write_yaml(f, {"provenance": [{"source": "test"}]})
        result = _update_entity_in_place(f, value_domain="text")
        assert result is False

    def test_identity_hash_none_provenance(self):
        sha, _ = compute_identity_hash({"data_type": "string"}, None)
        assert len(sha) == 64

    def test_canonical_json_nested_none(self):
        result = canonical_json({"a": None, "b": "val"})
        # None values should be excluded
        assert "null" not in result or "a" not in result


class TestMissingFields:
    def test_enrich_element_no_provenance(self, tmp_path):
        staging = tmp_path / "staging"
        d = staging / "elements"
        d.mkdir(parents=True)
        write_yaml(d / "orphan.yaml", {"semantic": {"data_type": "string"}})
        stats = enrich_elements(staging_dir=staging)
        assert stats["total"] == 1

    def test_identity_hash_minimal_semantic(self):
        sha, _ = compute_identity_hash({"data_type": "string"}, [])
        assert len(sha) == 64


class TestUnicode:
    def test_unicode_filename_sanitization(self):
        result = sanitize_filename("Ünïcödé/Nàme:Wïth Spëcîal")
        assert "/" not in result
        assert ":" not in result
        assert " " not in result

    def test_unicode_yaml_roundtrip(self, tmp_path):
        f = tmp_path / "unicode.yaml"
        data = {
            "semantic": {"data_type": "string", "description": "日本語テスト — Müller's field"},
            "provenance": [{"source": "test", "class": "Ü", "name": "nàme"}],
        }
        write_yaml(f, data)
        loaded = safe_load_yaml(f)
        assert loaded is not None
        assert loaded["semantic"]["description"] == "日本語テスト — Müller's field"

    def test_canonical_json_unicode(self):
        result = canonical_json({"name": "Müller", "data_type": "string"})
        # JSON may escape non-ASCII as \u00fc — check key is present
        assert "name" in result
        assert "data_type" in result
