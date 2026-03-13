# Contract: Roundtrip API

**Module**: `undata.roundtrip`

## Interface

```python
@dataclass
class RoundtripResult:
    fidelity_score: float          # 0.0–1.0
    missing_classes: list[str]     # class names lost in roundtrip
    missing_elements: list[str]    # element names lost in roundtrip
    warnings: list[str]            # non-fatal issues (cycles, coercions)

def roundtrip_json_schema(path: str) -> RoundtripResult: ...
def roundtrip_linkml(path: str) -> RoundtripResult: ...
```

## `roundtrip_json_schema(path: str) -> RoundtripResult`

**Preconditions**: `path` is a readable JSON Schema file.

**Algorithm**:
1. Load via `GenericJSONSchemaAdapter.load_file(path)`.
2. `elements_in = adapter.extract_elements()`.
3. `classes_in = adapter.extract_classes()`.
4. Build minimal `SchemaDefinition` from `elements_in` (one slot per element, one class
   per `SchemaClassPayload`).
5. Serialize to YAML string via `yaml_dumper.dumps(schema_def)`.
6. Write to `tempfile`, re-import via `LinkMLAdapter`.
7. `elements_out = la.extract_elements()`.
8. `classes_out = la.extract_classes()`.
9. `names_in = {e.name for e in elements_in}`.
10. `names_out = {e.name for e in elements_out}`.
11. `missing_elements = sorted(names_in - names_out)`.
12. `missing_classes = sorted({c.class_name for c in classes_in} - {c.class_name for c in classes_out})`.
13. `total = len(names_in) + len({c.class_name for c in classes_in})`.
14. `fidelity_score = 1.0 - (len(missing_elements) + len(missing_classes)) / max(total, 1)`.

**Postconditions**:
- `0.0 <= fidelity_score <= 1.0`.
- `missing_elements` and `missing_classes` are sorted lists of strings.
- `warnings` includes any cycle warnings from `GenericJSONSchemaAdapter`.
- Empty schema (no properties): `fidelity_score=1.0`, all lists empty.
- Raises `ValueError` on empty path; propagates `FileNotFoundError`.

## `roundtrip_linkml(path: str) -> RoundtripResult`

**Preconditions**: `path` is a readable LinkML YAML file.

**Algorithm**:
1. Load via `LinkMLAdapter.load_file(path)`.
2. `elements_in = la.extract_elements()`.
3. `classes_in = la.extract_classes()`.
4. Re-serialize via `yaml_dumper.dumps(la._linkml_schema)`.
5. Write to `tempfile`, re-import via second `LinkMLAdapter`.
6. Compare element names and class names as in `roundtrip_json_schema` steps 9–14.

**Postconditions**: Same invariants as `roundtrip_json_schema`.

## CLI Contract

```
undata roundtrip <path> [--format json|linkml]
```

| Argument | Required | Default | Description |
|---|---|---|---|
| `path` | yes | — | Path to schema file |
| `--format` | no | auto-detect | `json` or `linkml` |

**Auto-detection**: If `--format` omitted, infer from file extension (`.json` → json,
`.yaml`/`.yml` → linkml); raise `typer.BadParameter` if ambiguous.

**Output** (stdout):
```
Roundtrip fidelity: 1.00 (PASS)
  Missing elements:  0
  Missing classes:   0
```
or:
```
Roundtrip fidelity: 0.85 (FAIL)
  Missing elements:  3  [field_a, field_b, field_c]
  Missing classes:   1  [ComplexType]
  Warnings:
    - Circular $ref detected at depth 5 for #/$defs/RecursiveNode
```

**Exit codes**: 0 on PASS (`fidelity_score >= 1.0`), 1 on FAIL.
