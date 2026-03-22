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

## Recommended Fix Order

1. **Classifier logic** (affects all): Improve `classify_entity` to distinguish vocabulary/enum categories from attributes
2. **BIDS**: Separate enum categories from attribute categories; add sidecar rule parsing
3. **DANDI**: Add ENUM_VALUE emission; fix _pydantic_type; populate CLASS properties and subclass_of
4. **NWB**: Add inheritance tracking; extract links/groups/refs
5. **openMINDS**: Extract controlled vocabularies; fix property name extraction; handle references
6. **AIND**: Decompose anyOf; fix $defs classification; track array item types
