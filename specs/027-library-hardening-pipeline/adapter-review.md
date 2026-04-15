# Adapter Deep Review: Entity Classification Issues

**Date**: 2026-03-22 | **Reviewers**: 5 parallel agents

## Critical Cross-Cutting Issues

1. **Enum/vocabulary entries misclassified as elements** — affects ALL adapters. Enum members should be `ENUM_VALUE` (values), enum types should be `VALUESET`. Currently many are `ATTRIBUTE` (elements).

2. **No type_ref for reference fields** — affects DANDI, NWB, openMINDS, AIND. Fields referencing other model types are typed as "string" or "object" without `type_ref` pointing to the target class.

3. **Inheritance not tracked** — affects DANDI, NWB, openMINDS. `SchemaIdentity.subclass_of` exists but is never populated. The source schemas have rich type hierarchies.

4. **CLASS properties always empty** — affects BIDS (main adapter), DANDI (main adapter), openMINDS. The `properties` list in schema entities is always `[]` even though the data is available.

## Per-Source Findings

### BIDS (Critical: ~40% misclassification)

- **enum entries as ATTRIBUTE**: ~211 entries in categories like `datatypes`, `modalities`, `suffixes`, `extensions` are extracted as attributes but should be values/valuesets
- **Missing sidecar rules**: `rules/sidecars/` defines which metadata fields belong to which modality — this defines class-property membership but is not extracted
- **Missing value/unit/display_name fields**: `bidsschematools` objects have `value`, `display_name`, `unit` fields that are not captured
- **Underscore valueset $ref corruption**: 7 valuesets with `$ref` entries may have corrupted member lists

### DANDI (11 issues, 3 HIGH)

- **No ENUM_VALUE emission**: ~110 enum members missing as value concepts
- **No inheritance hierarchy**: ~35 classes missing `subclass_of` (available via `cls.__bases__`)
- **Empty CLASS properties**: Main adapter emits `[]` (docker script has them correct)
- **Fragile _pydantic_type**: String-matching on annotation repr instead of proper type introspection
- **Reference fields untyped**: ~40-50 fields referencing other models typed as "string"

### NWB (11 issues, 1 Critical + 3 HIGH)

- **Inheritance ignored**: `neurodata_type_inc` not tracked (the defining feature of NWB)
- **Links not extracted**: Inter-type relationships lost
- **Nested groups not extracted**: Composition relationships lost
- **Reference dtypes unhandled**: `target_type` fields not captured as type_ref
- **Compound dtypes not decomposed**: Multi-column types treated as single field

### openMINDS (11 issues, 4 HIGH)

- **Controlled vocabularies not as VALUESET**: ~85+ vocabulary types missing
- **Property names are full URIs**: Names like `https://openminds.om-i.org/props/abbreviation` instead of `abbreviation`
- **References typed as "string"**: `_linkedTypes`/`_embeddedTypes` ignored
- **Schema path may not resolve**: source_def points to potentially nonexistent `.jsonld` path

### AIND (10 issues, 2 HIGH)

- **anyOf/oneOf not decomposed**: Union types not split into separate elements per variant
- **$defs misclassified**: Underscore-prefixed `$defs` emitted as `ENUM_VALUE` but many are classes
- **Array items lose type_ref**: `items.$ref` not tracked

## Detailed Per-Source Issues

### BIDS (8 issues)
1. **CRITICAL**: ~211 enum entries in `objects.enums` extracted as ATTRIBUTE instead of ENUM_VALUE. Each has a `value` field (e.g., `"L"` for left_hemisphere) that is never read.
2. **CRITICAL**: 7 underscore valueset members may contain stringified $ref dicts instead of resolved values.
3. **MODERATE**: 9 vocabulary categories (`enums`, `datatypes`, `modalities`, `suffixes`, `extensions`, `formats`, `common_principles`, `files`, `metaentities`) incorrectly emitted as CLASS.
4. **MODERATE**: ~189 vocabulary terms in `datatypes`/`modalities`/`suffixes`/`extensions` extracted as ATTRIBUTE instead of ENUM_VALUE.
5. **MAJOR**: `value`, `display_name`, `unit` fields never read from ANY bidsschematools entry. Units like `"s"`, `"mm"`, `"Hz"` are critical for cross-source mapping and are lost.
6. **MAJOR**: Missing sidecar rules (`rules/sidecars/`) that define class-property membership (which metadata fields belong to which modality).
7. **MODERATE**: `entities` category entries are filename components, not data elements.
8. **MINOR**: Metadata enum response_options are flat strings, not references to ENUM_VALUE entities.

### DANDI (11 issues)
1. **HIGH**: ~110 enum members never emitted as ENUM_VALUE entities.
2. **HIGH**: No inheritance hierarchy — `cls.__bases__` available but never used for ~35 classes.
3. **MEDIUM**: Empty CLASS properties list (docker script has them correct, main adapter does not).
4. **HIGH**: ~40-50 reference-typed fields have no `type_ref` — typed as "string" instead of "object".
5. **MEDIUM**: Fragile `_pydantic_type` uses string matching on annotation repr.
6. **MEDIUM**: `_extract_enum_class` misses `X | None` unions (Python 3.10+).
7. **LOW**: Duplicate VALUESET emission from same enum across multiple classes.
8. **LOW**: No `required` flag tracking.
9. **LOW**: No `multivalued` flag tracking.
10. **MEDIUM**: PropertyValue handling incomplete.
11. **LOW**: Docker script / main adapter divergence.

### NWB (11 issues)
1. **MEDIUM**: Namespace file not parsed — no multi-file traversal.
2. **CRITICAL**: Inheritance (`neurodata_type_inc`) completely ignored — the defining feature of NWB.
3. **HIGH**: `links` section not extracted (inter-type relationships lost).
4. **HIGH**: Nested groups not extracted (composition relationships lost).
5. **MEDIUM**: Fixed values / default values ignored.
6. **MEDIUM**: `quantity` / `required` not captured.
7. **MEDIUM**: Compound dtypes not decomposed.
8. **HIGH**: Reference dtypes (`target_type`) not handled.
9. **MEDIUM**: `dims`/`shape` metadata discarded.
10. **MEDIUM**: Type defs emitted as spurious ATTRIBUTEs.
11. **MEDIUM**: No extract() test coverage.

### openMINDS (11 issues)
1. **HIGH**: Property names are full URIs instead of short names (e.g., `https://openminds.om-i.org/props/familyName` instead of `familyName`).
2. **HIGH**: `_linkedTypes`/`_embeddedTypes` ignored — all reference properties typed as "string".
3. **MEDIUM**: CLASS properties list always empty.
4. **HIGH**: ~85+ controlled vocabulary types (`controlledTerms` module) not emitted as VALUESET.
5. **MEDIUM**: `@context` fallback for properties is wrong.
6. **HIGH**: source_defs `schema_path` targets nonexistent `.jsonld` files.
7. **MEDIUM**: `@type` vs `_type` and class name extraction broken (names like `fileBundle.schema.omi`).
8. **MEDIUM**: No type hierarchy tracking (categories, modules).
9. **LOW-MEDIUM**: `required` field ignored.
10. **LOW**: Schema description/label not captured.
11. **LOW**: Rich property metadata discarded.

### AIND (10 issues)
1. **LOW-MEDIUM**: `$defs` entries without `properties` silently dropped.
2. **HIGH**: anyOf/oneOf unions NOT decomposed into separate elements per variant.
3. **HIGH**: Underscore-prefixed `$defs` misclassified as ENUM_VALUE — they are actually CLASS objects with properties.
4. **MEDIUM**: Descriptions lost for anyOf/oneOf wrapped references.
5. **MEDIUM-HIGH**: Array `items.$ref` loses `type_ref`.
6. **LOW-MEDIUM**: ENUM_VALUE labels lowercased inconsistently.
7. **LOW**: No circular reference protection.
8. **LOW**: `_find_parent_class` shallow traversal.
9. **MEDIUM**: Dead code references non-existent `extractors.aind` module.
10. **LOW**: Non-recursive file glob.

## Upstream Changes (reviewed 2026-03-22)

- **DANDI PR #387**: Converting dandischema to LinkML. Once merged, DANDI adapter should consume LinkML YAML directly via existing LinkML adapter. PR #385 replaces discriminated unions with simple unions — affects schemaKey detection.
- **openMINDS v5 released** (PR #86, merged 2026-03-11): New/modified schema files, vocabulary label fixes (PR #93). Must re-ingest against v5.
- **NWB HERD type merged** (PR #646): New group under NWBFile.general. Picked up automatically on re-ingestion.
- **NWB EventsTable** (PR #645, draft): New neurodata types targeting schema v2.10.0.
- **NWB #675**: Discussion about making many required fields optional — would change required flags on extracted elements.
- **AIND NHPSubject** (PR #1778, merged): New Subject union member. **files.json** (PR #1780, draft): Croissant-based file structure model.
- **BIDS PR #2359**: Schema expression language changes (context restructuring). **#2358**: Deprecating `_recording-` entity.
- **DANDI #372**: 3D probe/electrode positions proposed. **#369**: New DatasetType metadata field.

## Recommended Fix Order

1. **BIDS enum classification** (Critical, ~400 entities): Separate enum/vocabulary categories from attributes; read `value`/`display_name`/`unit` fields
2. **DANDI ENUM_VALUE + type_ref** (High, ~150 entities): Emit enum members; fix type introspection; populate inheritance
3. **openMINDS vocabulary + property names** (High, ~85 entities): Controlled terms as VALUESET; short property names; handle references
4. **NWB inheritance + links** (Critical): Track `neurodata_type_inc`; extract links/groups; handle reference dtypes
5. **AIND anyOf decomposition** (High): Split unions per variant; fix $defs classification
6. **Cross-cutting**: Read `unit`/`required`/`multivalued` where available
