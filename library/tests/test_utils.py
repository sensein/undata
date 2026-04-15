"""Tests for shared utilities."""

import yaml

from undata_library.utils import BASE_URI, safe_load_yaml, sanitize_filename, write_yaml


class TestSafeLoadYaml:
    def test_valid_yaml(self, tmp_path):
        f = tmp_path / "good.yaml"
        f.write_text(yaml.dump({"key": "value"}))
        assert safe_load_yaml(f) == {"key": "value"}

    def test_malformed_yaml(self, tmp_path):
        f = tmp_path / "bad.yaml"
        f.write_text(":\n  - :\n    bad: [")
        assert safe_load_yaml(f) is None

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.yaml"
        f.write_text("")
        assert safe_load_yaml(f) is None

    def test_non_dict_yaml(self, tmp_path):
        f = tmp_path / "list.yaml"
        f.write_text("- a\n- b\n")
        assert safe_load_yaml(f) is None

    def test_missing_file(self, tmp_path):
        assert safe_load_yaml(tmp_path / "missing.yaml") is None

    def test_unicode_content(self, tmp_path):
        f = tmp_path / "unicode.yaml"
        f.write_text(yaml.dump({"name": "Müller", "desc": "日本語テスト"}))
        data = safe_load_yaml(f)
        assert data is not None
        assert data["name"] == "Müller"
        assert data["desc"] == "日本語テスト"


class TestWriteYaml:
    def test_writes_valid_yaml(self, tmp_path):
        f = tmp_path / "out.yaml"
        write_yaml(f, {"key": "value"})
        assert f.exists()
        data = yaml.safe_load(f.read_text())
        assert data == {"key": "value"}

    def test_creates_parent_dirs(self, tmp_path):
        f = tmp_path / "deep" / "nested" / "out.yaml"
        write_yaml(f, {"a": 1})
        assert f.exists()

    def test_roundtrip(self, tmp_path):
        f = tmp_path / "rt.yaml"
        original = {"semantic": {"data_type": "string"}, "provenance": [{"source": "test"}]}
        write_yaml(f, original)
        loaded = safe_load_yaml(f)
        assert loaded == original


class TestSanitizeFilename:
    def test_basic(self):
        assert sanitize_filename("Age") == "age"

    def test_slashes(self):
        assert (
            sanitize_filename("https://openminds.org/props/name")
            == "https___openminds.org_props_name"
        )

    def test_colons(self):
        assert sanitize_filename("ns:localPart") == "ns_localpart"

    def test_backslashes(self):
        assert sanitize_filename("path\\to\\file") == "path_to_file"

    def test_spaces(self):
        assert sanitize_filename("some field name") == "some_field_name"

    def test_truncation(self):
        long_name = "a" * 100
        assert len(sanitize_filename(long_name)) == 60

    def test_custom_max_length(self):
        assert len(sanitize_filename("a" * 100, max_length=20)) == 20

    def test_unicode_name(self):
        result = sanitize_filename("Ünïcödé_Nàme")
        assert "/" not in result
        assert ":" not in result


class TestBaseUri:
    def test_base_uri_value(self):
        assert BASE_URI == "https://schema.undata.live"

    def test_base_uri_is_string(self):
        assert isinstance(BASE_URI, str)
