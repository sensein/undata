"""Tests for source definitions and acquisition."""

import yaml

from undata_library.acquisition import list_bundled_sources, load_source_def


def test_all_bundled_defs_load():
    """All 8 bundled source definitions load successfully."""
    names = list_bundled_sources()
    assert set(names) == {
        "aind",
        "bids",
        "dandi",
        "nda",
        "nwb",
        "openminds",
        "openneuro",
        "reproschema",
    }
    for name in names:
        sd = load_source_def(name)
        assert sd.name == name
        assert sd.repo.startswith("https://")
        assert sd.adapter


def test_bids_def_fields():
    sd = load_source_def("bids")
    assert sd.acquisition == "pip_install"
    assert sd.package == "bidsschematools"
    assert sd.isolation == "venv"


def test_nwb_def_fields():
    sd = load_source_def("nwb")
    assert sd.acquisition == "git_clone"
    assert sd.schema_path == "core/*.yaml"
    assert sd.isolation == "none"


def test_custom_yaml_loads(tmp_path):
    custom = {
        "name": "custom",
        "repo": "https://example.com/repo",
        "default_version": "v1.0",
        "acquisition": "download_file",
        "adapter": "json-schema",
        "isolation": "none",
    }
    f = tmp_path / "custom.yaml"
    f.write_text(yaml.dump(custom))
    sd = load_source_def(str(f))
    assert sd.name == "custom"
    assert sd.acquisition == "download_file"


def test_unknown_name_raises():
    try:
        load_source_def("nonexistent")
        assert False, "Should have raised"
    except ValueError as e:
        assert "Unknown source" in str(e)
        assert "Available" in str(e)
