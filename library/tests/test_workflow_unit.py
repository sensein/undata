"""Unit tests for workflow loading and execution."""

import pytest

from undata_library.utils import write_yaml
from undata_library.workflow import load_workflow


class TestLoadWorkflow:
    def test_load_valid_workflow(self, tmp_path):
        write_yaml(
            tmp_path / "workflow.yaml",
            {
                "sources": [
                    {"path": "/tmp/test", "adapter": "json_schema"},
                ],
                "validation": {"strict": False, "checks": []},
            },
        )
        spec = load_workflow(tmp_path / "workflow.yaml")
        assert len(spec.sources) == 1
        assert spec.sources[0].adapter == "json_schema"

    def test_load_missing_file_raises(self, tmp_path):
        with pytest.raises(ValueError, match="Invalid or missing"):
            load_workflow(tmp_path / "nonexistent.yaml")

    def test_load_malformed_yaml(self, tmp_path):
        f = tmp_path / "bad.yaml"
        f.write_text("not: [valid yaml {{")
        with pytest.raises(ValueError, match="Invalid or missing"):
            load_workflow(f)

    def test_load_multi_source_workflow(self, tmp_path):
        write_yaml(
            tmp_path / "multi.yaml",
            {
                "sources": [
                    {"path": "/tmp/bids", "adapter": "bids"},
                    {"path": "/tmp/dandi", "adapter": "dandi"},
                    {"path": "/tmp/nwb", "adapter": "nwb"},
                ],
                "validation": {"strict": True, "checks": ["data_type_valid"]},
            },
        )
        spec = load_workflow(tmp_path / "multi.yaml")
        assert len(spec.sources) == 3
        assert spec.validation.strict is True
