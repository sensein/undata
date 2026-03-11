"""CLI contract tests for `undata generate-schema`."""

import respx
import yaml
from httpx import Response
from typer.testing import CliRunner

from undata.cli import app

runner = CliRunner()

MOCK_ELEMENTS = [
    {
        "id": "e1",
        "name": "subject_age",
        "data_type": "number",
        "description": "Age",
        "required": False,
        "multivalued": False,
        "allowed_values": None,
        "source": {"name": "BIDS"},
    }
]


def test_generate_schema_outputs_valid_yaml(tmp_path):
    out_file = tmp_path / "schema.yaml"
    with respx.mock(base_url="http://localhost:8002/api/v1") as mock:
        mock.get("/elements").mock(
            return_value=Response(200, json={"items": MOCK_ELEMENTS, "total": 1, "page": 1})
        )
        result = runner.invoke(
            app,
            ["generate-schema", "--output", str(out_file)],
            catch_exceptions=False,
        )

    assert result.exit_code == 0, result.output
    content = out_file.read_text()
    parsed = yaml.safe_load(content)
    assert "name" in parsed
    assert "classes" in parsed


def test_generate_schema_stdout():
    with respx.mock(base_url="http://localhost:8002/api/v1") as mock:
        mock.get("/elements").mock(
            return_value=Response(200, json={"items": MOCK_ELEMENTS, "total": 1, "page": 1})
        )
        result = runner.invoke(app, ["generate-schema"], catch_exceptions=False)

    assert result.exit_code == 0
    parsed = yaml.safe_load(result.output)
    assert "name" in parsed
