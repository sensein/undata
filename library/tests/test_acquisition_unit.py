"""Unit tests for acquisition module — no network required."""

from undata_library.acquisition import (
    build_source_ref_from_cache,
    list_bundled_sources,
    load_source_def,
)
from undata_library.models import SourceDefinition


class TestLoadSourceDef:
    def test_load_bundled_bids(self):
        sd = load_source_def("bids")
        assert sd.name == "bids"
        assert sd.adapter == "bids"

    def test_load_bundled_dandi(self):
        sd = load_source_def("dandi")
        assert sd.name == "dandi"

    def test_load_bundled_nwb(self):
        sd = load_source_def("nwb")
        assert sd.name == "nwb"

    def test_load_bundled_openminds(self):
        sd = load_source_def("openminds")
        assert sd.name == "openminds"

    def test_load_bundled_aind(self):
        sd = load_source_def("aind")
        assert sd.name == "aind"

    def test_load_nonexistent_raises(self):
        import pytest

        with pytest.raises((FileNotFoundError, ValueError)):
            load_source_def("nonexistent_source_xyz")

    def test_load_custom_yaml(self, tmp_path):
        from undata_library.utils import write_yaml

        custom = tmp_path / "custom.yaml"
        write_yaml(
            custom,
            {
                "name": "custom",
                "adapter": "json_schema",
                "repo": "https://example.com/repo",
                "acquisition": "git_clone",
            },
        )
        sd = load_source_def(str(custom))
        assert sd.name == "custom"
        assert sd.adapter == "json_schema"


class TestListBundledSources:
    def test_returns_at_least_five(self):
        sources = list_bundled_sources()
        assert len(sources) >= 5
        assert "bids" in sources
        assert "dandi" in sources

    def test_returns_strings(self):
        sources = list_bundled_sources()
        assert all(isinstance(s, str) for s in sources)


class TestBuildSourceRefFromCache:
    def test_with_committish_file(self, tmp_path):
        sd = SourceDefinition(
            name="test",
            adapter="json_schema",
            repo="https://github.com/example/repo",
            acquisition="git_clone",
        )
        (tmp_path / "_resolved_committish").write_text("abc123def456")

        ref = build_source_ref_from_cache(sd, tmp_path)
        assert ref.repo == "https://github.com/example/repo"
        assert ref.committish == "abc123def456"

    def test_without_committish_file(self, tmp_path):
        sd = SourceDefinition(
            name="test",
            adapter="json_schema",
            repo="https://github.com/example/repo",
            acquisition="git_clone",
        )
        ref = build_source_ref_from_cache(sd, tmp_path)
        assert ref.repo == "https://github.com/example/repo"
        assert ref.committish is None or ref.committish == ""
