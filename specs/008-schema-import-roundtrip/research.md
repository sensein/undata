# Research: Generic Schema Import with Roundtrip Fidelity

**Branch**: `008-schema-import-roundtrip` | **Date**: 2026-03-11

## Decision 1: Generic JSON Schema Adapter approach

**Decision**: Implement a standalone `GenericJSONSchemaAdapter` in
`ingestion/src/undata/adapters/json_schema.py` that reuses the same extraction
pattern already established in `dandi.py` (`_elements_from_props()` + `$defs` traversal).

**Rationale**: The DANDI adapter already implements a nearly complete generic JSON Schema
extractor — it handles `properties`, `$defs`, `type`, `enum`, `required`, `description`.
The only missing pieces are `$ref` resolution and support for the `definitions` key
(draft-07 spelling of `$defs`). Extracting this into a standalone generic adapter avoids
duplication and makes it immediately reusable.

**Alternatives considered**:
- Reuse the DANDI adapter with `source_name` override: rejected — couples DANDI semantics
  to generic use; DANDI has special Pydantic `load_code()` path not applicable here.
- Use `jsonschema` library for dereferencing: rejected — `jsonschema` is not in the
  dependency tree; adding it for `$ref` resolution alone is over-engineering; an
  in-document resolver for `#/$defs/<name>` is trivial to implement inline.
- Use `linkml.utils.schema_builder` to generate a LinkML schema from JSON Schema at import
  time: rejected — the `linkml` package (full, not just `linkml-runtime`) is not installed
  in the production venv (only `linkml-runtime`), and `linkml` is heavy. The adapter layer
  produces `NormalizedElement`s; LinkML conversion happens only in `linkml_gen.py`.

## Decision 2: LinkML Adapter — use `linkml_runtime.loaders.yaml_loader`

**Decision**: `LinkMLAdapter` uses `linkml_runtime.loaders.yaml_loader` (already in the
production venv) to load a `SchemaDefinition` object, then iterates `.slots` and `.classes`.

**Rationale**: `linkml_runtime` (v1.10.0) is already installed. `yaml_loader.load(path,
target_class=SchemaDefinition)` is already used in `validation.py`. No new dependencies.

**Alternatives considered**:
- Parse the YAML manually with PyYAML: rejected — would re-implement what `linkml_runtime`
  already does correctly (type coercions, defaults, nested objects).
- Use `linkml.SchemaView`: rejected — `linkml` full package not in production venv.

## Decision 3: Roundtrip implementation — in-memory, no backend

**Decision**: `roundtrip_json_schema(path)` and `roundtrip_linkml(path)` are pure offline
functions that:
1. Import via the appropriate adapter.
2. Build a minimal in-memory `SchemaDefinition` from the extracted `NormalizedElement`s
   (using `linkml_runtime`).
3. Serialize to YAML string via `yaml_dumper.dumps()`.
4. Re-import via `LinkMLAdapter` (from a `tempfile` or `io.StringIO`).
5. Compare slot names and class names to compute `fidelity_score`.

**Rationale**: No backend dependency → tests run offline; consistent with the offline-first
approach used in all unit tests. The in-memory round is deterministic.

**Alternatives considered**:
- Use `linkml.generators.jsonschemagen.JsonSchemaGenerator` to export LinkML → JSON Schema
  then re-import with `GenericJSONSchemaAdapter`: more faithful JSON→JSON roundtrip but
  requires the `linkml` full package (not in prod venv). Deferred for a future feature.
- Full semantic equivalence check (type, description, constraints): over-engineering for
  P3 use case; name-based fidelity score covers the primary regression detection goal.

## Decision 4: RoundtripResult as a dataclass

**Decision**: `RoundtripResult` lives in `ingestion/src/undata/roundtrip.py` alongside
the `roundtrip_json_schema()` and `roundtrip_linkml()` functions.

**Rationale**: Keeps roundtrip logic separate from both adapters and the LinkML generator.
Single-responsibility: adapters import, roundtrip module validates.

## Decision 5: CLI command placement

**Decision**: Add `roundtrip` as a new Typer subcommand in `cli.py` (same file as `ingest`,
`generate-schema`, `validate`).

**Rationale**: One CLI entry point (`undata`) per constitution Principle I (Simplicity First).
No new modules needed.

## Dependency Analysis

| Dependency | Already installed? | Used for |
|---|---|---|
| `linkml_runtime` ≥ 1.8 | ✅ yes (v1.10.0) | yaml_loader, yaml_dumper, SchemaDefinition |
| `linkml` (full) | ❌ dev only | JsonSchemaGenerator (not needed here) |
| `jsonschema` | ❌ not installed | Not needed (inline $ref resolver) |
| `pyyaml` | ✅ yes (transitive) | Already in venv |

No new production dependencies required.

## Range Mapping (LinkML → NormalizedElement)

| LinkML range | NormalizedElement.data_type |
|---|---|
| `string` / `str` / None | `"string"` |
| `integer` / `int` / `float` | `"number"` |
| `boolean` / `bool` | `"boolean"` |
| `Any` / `anyuri` | `"object"` |
| any other class name | `"object"` |
| (multivalued=True) | `"array"` |
