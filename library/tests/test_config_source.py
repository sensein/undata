"""T038n2: Verify config-only source ingestion for standard formats.

Creates a mock JSON Schema source definition + fixture file,
runs the pipeline, and verifies entities are extracted without code changes.
"""

import json

from undata_library.adapters.json_schema import JSONSchemaAdapter
from undata_library.utils import write_yaml


class TestConfigOnlyJsonSchema:
    def test_json_schema_adapter_extracts_from_file(self, tmp_path):
        """A new JSON Schema file can be ingested via the generic adapter."""
        # Create a simple JSON Schema
        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "title": "TestSchema",
            "type": "object",
            "properties": {
                "test_field": {
                    "type": "string",
                    "description": "A test field",
                },
                "test_number": {
                    "type": "number",
                    "description": "A numeric field",
                    "minimum": 0,
                    "maximum": 100,
                },
            },
        }
        schema_file = tmp_path / "test_schema.json"
        schema_file.write_text(json.dumps(schema))

        # Use the generic adapter directly
        adapter = JSONSchemaAdapter()
        entities = adapter.extract(tmp_path)

        # Should extract at least the 2 properties as attributes
        attributes = [e for e in entities if e.entity_type.value == "attribute"]
        assert len(attributes) >= 2

        # Verify field names
        names = {e.semantic.get("name", e.provenance.get("name", "")) for e in attributes}
        # The adapter extracts from properties
        assert len(names) >= 2

    def test_config_driven_source_def_structure(self, tmp_path):
        """Verify a source_def YAML for a JSON Schema source is structurally valid."""
        write_yaml(
            tmp_path / "test-source.yaml",
            {
                "name": "test-source",
                "adapter": "json_schema",
                "repo": "https://github.com/example/test-schemas",
                "acquisition": "git_clone",
                "schema_path": "schemas/",
            },
        )
        from undata_library.acquisition import load_source_def

        sd = load_source_def(str(tmp_path / "test-source.yaml"))
        assert sd.name == "test-source"
        assert sd.adapter == "json_schema"
