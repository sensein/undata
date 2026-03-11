"""Integration tests for LinkMLSchemaGenerator using respx mock backend."""

import pytest
import respx
import yaml
from httpx import Response

from undata.linkml_gen import LinkMLSchemaGenerator

BACKEND_URL = "http://testbackend/api/v1"

MOCK_ELEMENTS = [
    {
        "id": "elem-001",
        "name": "subject_age",
        "data_type": "number",
        "description": "Age of the research subject",
        "required": False,
        "multivalued": False,
        "allowed_values": None,
        "source": {"name": "BIDS"},
    },
    {
        "id": "elem-002",
        "name": "session_id",
        "data_type": "string",
        "description": "Session identifier",
        "required": False,
        "multivalued": False,
        "allowed_values": None,
        "source": {"name": "BIDS"},
    },
    {
        "id": "elem-003",
        "name": "sex",
        "data_type": "string",
        "description": "Biological sex",
        "required": False,
        "multivalued": False,
        "allowed_values": ["male", "female", "other"],
        "source": {"name": "BIDS"},
    },
    {
        "id": "elem-004",
        "name": "identifier",
        "data_type": "string",
        "description": "Unique dataset identifier",
        "required": True,
        "multivalued": False,
        "allowed_values": None,
        "source": {"name": "DANDI"},
    },
]


@pytest.mark.asyncio
async def test_generator_produces_linkml_schema():
    with respx.mock(base_url=BACKEND_URL) as mock:
        mock.get("/elements").mock(
            return_value=Response(200, json={"items": MOCK_ELEMENTS, "total": 4, "page": 1})
        )
        gen = LinkMLSchemaGenerator(
            backend_url=BACKEND_URL,
            schema_id="https://undata.org/schema/test",
            schema_name="TestSchema",
            version="2026.03.0",
        )
        schema = await gen.generate()

    assert schema is not None
    assert schema.name == "TestSchema"
    assert schema.id == "https://undata.org/schema/test"


@pytest.mark.asyncio
async def test_generator_has_neuroscience_dataset_class():
    with respx.mock(base_url=BACKEND_URL) as mock:
        mock.get("/elements").mock(
            return_value=Response(200, json={"items": MOCK_ELEMENTS, "total": 4, "page": 1})
        )
        gen = LinkMLSchemaGenerator(backend_url=BACKEND_URL)
        schema = await gen.generate()

    assert "NeuroscienceDataset" in schema.classes


@pytest.mark.asyncio
async def test_generator_has_slots_for_elements():
    with respx.mock(base_url=BACKEND_URL) as mock:
        mock.get("/elements").mock(
            return_value=Response(200, json={"items": MOCK_ELEMENTS, "total": 4, "page": 1})
        )
        gen = LinkMLSchemaGenerator(backend_url=BACKEND_URL)
        schema = await gen.generate()

    assert "subject_age" in schema.slots
    assert "session_id" in schema.slots
    assert "identifier" in schema.slots


@pytest.mark.asyncio
async def test_generator_creates_enum_for_allowed_values():
    with respx.mock(base_url=BACKEND_URL) as mock:
        mock.get("/elements").mock(
            return_value=Response(200, json={"items": MOCK_ELEMENTS, "total": 4, "page": 1})
        )
        gen = LinkMLSchemaGenerator(backend_url=BACKEND_URL)
        schema = await gen.generate()

    assert len(schema.enums) > 0
    enum_names = list(schema.enums.keys())
    assert any("sex" in n.lower() for n in enum_names)


@pytest.mark.asyncio
async def test_generator_yaml_serialization():
    with respx.mock(base_url=BACKEND_URL) as mock:
        mock.get("/elements").mock(
            return_value=Response(200, json={"items": MOCK_ELEMENTS, "total": 4, "page": 1})
        )
        gen = LinkMLSchemaGenerator(backend_url=BACKEND_URL)
        schema = await gen.generate()

    yaml_str = gen.to_yaml(schema)
    parsed = yaml.safe_load(yaml_str)
    assert "name" in parsed
    assert "classes" in parsed
    assert "slots" in parsed
