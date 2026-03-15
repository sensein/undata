"""Tests for index builder."""

import shutil
from pathlib import Path

import yaml

from undata_library.index import build_index, write_index

FIXTURES = Path(__file__).parent / "fixtures"


def _setup_library(tmp_path: Path) -> Path:
    """Create a minimal library structure with fixture files."""
    elements = tmp_path / "elements"
    mappings = tmp_path / "mappings"
    elements.mkdir()
    mappings.mkdir()

    shutil.copy(FIXTURES / "valid-element.yaml", elements / "element-e001.yaml")
    shutil.copy(FIXTURES / "multi-version-element.yaml", elements / "element-e010.yaml")
    shutil.copy(FIXTURES / "valid-mapping.yaml", mappings / "mapping-m001.yaml")

    return tmp_path


class TestBuildIndex:
    def test_counts_elements_and_mappings(self, tmp_path):
        lib = _setup_library(tmp_path)
        idx = build_index(lib)
        assert idx["element_count"] == 2
        assert idx["mapping_count"] == 1

    def test_element_entries_have_required_fields(self, tmp_path):
        lib = _setup_library(tmp_path)
        idx = build_index(lib)
        el = idx["elements"][0]
        assert "id" in el
        assert "name" in el
        assert "current_version" in el
        assert "file" in el

    def test_mapping_entries_have_required_fields(self, tmp_path):
        lib = _setup_library(tmp_path)
        idx = build_index(lib)
        m = idx["mappings"][0]
        assert "id" in m
        assert "status" in m
        assert "file" in m


class TestWriteIndex:
    def test_writes_yaml_file(self, tmp_path):
        lib = _setup_library(tmp_path)
        out = tmp_path / "index.yaml"
        write_index(lib, out)
        assert out.exists()
        data = yaml.safe_load(out.read_text())
        assert data["element_count"] == 2
        assert data["generated_at"] is not None

    def test_empty_library(self, tmp_path):
        (tmp_path / "elements").mkdir()
        (tmp_path / "mappings").mkdir()
        idx = build_index(tmp_path)
        assert idx["element_count"] == 0
        assert idx["mapping_count"] == 0
