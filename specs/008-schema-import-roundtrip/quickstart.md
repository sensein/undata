# Quickstart: Generic Schema Import with Roundtrip Fidelity

**Branch**: `008-schema-import-roundtrip`

## Prerequisites

```bash
cd ingestion
uv sync  # no new deps required
```

## QS-001: Import any JSON Schema file

```python
from undata.adapters.json_schema import GenericJSONSchemaAdapter

adapter = GenericJSONSchemaAdapter()
adapter.load_file("my_schema.json")  # any draft-07/2019/2020 JSON Schema
elements = adapter.extract_elements()
classes = adapter.extract_classes()
print(f"Extracted {len(elements)} elements from {len(classes)} classes")
# e.g. "Extracted 42 elements from 5 classes"
```

**Expected**: All `elements[i].source_name == "generic-json"` and `data_type` in
`{"string", "number", "boolean", "object", "array"}`.

## QS-002: Import a LinkML YAML schema

```python
from undata.adapters.linkml_adapter import LinkMLAdapter

la = LinkMLAdapter()
la.load_file("schema.yaml")  # any LinkML YAML
elements = la.extract_elements()
classes = la.extract_classes()
print(f"{len(elements)} slots, {len(classes)} classes")
```

## QS-003: Verify JSON Schema roundtrip fidelity

```python
from undata.roundtrip import roundtrip_json_schema

result = roundtrip_json_schema("tests/fixtures/aind/subject.json")
print(f"Fidelity: {result.fidelity_score:.2f}")
if result.missing_elements:
    print("Lost elements:", result.missing_elements)
```

**Expected for simple schemas**: `fidelity_score == 1.0`.

## QS-004: Verify LinkML roundtrip fidelity

```python
from undata.roundtrip import roundtrip_linkml

result = roundtrip_linkml("tests/fixtures/linkml_sample.yaml")
assert result.fidelity_score == 1.0
```

## QS-005: CLI roundtrip check

```bash
# JSON Schema (exits 0 on full fidelity)
uv run undata roundtrip tests/fixtures/aind/subject.json --format json

# LinkML (exits 0 on full fidelity)
uv run undata roundtrip tests/fixtures/linkml_sample.yaml --format linkml

# Auto-detect format from extension
uv run undata roundtrip tests/fixtures/generic_schema_sample.json
```

## QS-006: Use with bundled DANDI/AIND fixtures

```python
from pathlib import Path
from undata.adapters.json_schema import GenericJSONSchemaAdapter

# DANDI subject schema via generic adapter
adapter = GenericJSONSchemaAdapter()
adapter.load_file(str(Path("tests/fixtures/dandi") / "dandiset.json"))
elements = adapter.extract_elements()
print(f"DANDI dandiset: {len(elements)} elements from generic adapter")
```

## Success Criteria Reference

| QS | SC | Expected |
|---|---|---|
| QS-001 | SC-001 | ≥ 1 element per fixture with properties |
| QS-002 | SC-002 | ≥ 1 element from minimal LinkML fixture |
| QS-003 | SC-003 | `fidelity_score == 1.0` on simple fixture |
| QS-004 | SC-004 | `fidelity_score == 1.0` on minimal LinkML |
| QS-005 | SC-006 | CLI exits 0, ruff clean |
