"""CLI contract tests for `undata validate`."""

import json

from typer.testing import CliRunner

from undata.cli import app

runner = CliRunner()

MINIMAL_SCHEMA = """
id: https://test.org/schema
name: TestSchema
prefixes:
  linkml: https://w3id.org/linkml/
default_range: string
classes:
  NeuroscienceDataset:
    slots:
      - subject_id
slots:
  subject_id:
    range: string
    required: true
"""


def test_validate_conformant_exits_zero(tmp_path):
    schema_file = tmp_path / "schema.yaml"
    schema_file.write_text(MINIMAL_SCHEMA)
    data_file = tmp_path / "data.json"
    data_file.write_text('{"subject_id": "sub-01"}')

    result = runner.invoke(
        app,
        ["validate", str(data_file), "--schema", str(schema_file)],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    assert "PASS" in result.output


def test_validate_nonconformant_exits_one(tmp_path):
    schema_file = tmp_path / "schema.yaml"
    schema_file.write_text(MINIMAL_SCHEMA)
    data_file = tmp_path / "data.json"
    data_file.write_text("{}")  # missing required subject_id

    result = runner.invoke(
        app,
        ["validate", str(data_file), "--schema", str(schema_file)],
    )
    assert result.exit_code == 1
    assert "FAIL" in result.output


def test_validate_json_output(tmp_path):
    schema_file = tmp_path / "schema.yaml"
    schema_file.write_text(MINIMAL_SCHEMA)
    data_file = tmp_path / "data.json"
    data_file.write_text('{"subject_id": "sub-01"}')

    result = runner.invoke(
        app,
        ["validate", str(data_file), "--schema", str(schema_file), "--output-format", "json"],
        catch_exceptions=False,
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "status" in data
    assert "violations" in data
