# Feature Specification: Full Library Re-extraction

**Feature Branch**: `022-full-reextract`
**Created**: 2026-03-21
**Status**: Draft
**Input**: Re-extract all data using the source acquisition (021) and new data extraction (019/020) pipelines to produce a complete, validated library output.

## User Scenarios & Testing

### User Story 1 — Clean Re-extraction of All Sources (Priority: P1)

A data curator runs the full pipeline for all 5 sources (BIDS, NWB, DANDI, openMINDS, AIND) using the automated source acquisition pipeline. The system downloads each source, creates isolated environments where needed, extracts all entities with rigorous 4-way classification, generates transforms between overlapping elements, and produces a validated library.

**Why this priority**: The library currently contains output from the old extractor pipeline. The new adapter framework (019), transform engine (020), and source acquisition (021) are implemented but the library has never been fully re-extracted with them.

**Independent Test**: Starting from a clean library directory, run the pipeline for all 5 sources and verify the output passes all validation checks.

**Acceptance Scenarios**:

1. **Given** a clean library directory (no existing elements/schemas/values), **When** the pipeline runs for all 5 sources, **Then** elements/, schemas/, values/, valuesets/, and transforms/ directories are populated.
2. **Given** all 5 sources are extracted, **When** `validate-ingestion` runs, **Then** 0 violations are reported.
3. **Given** all 5 sources are extracted, **When** the ontology index is built, **Then** it includes elements, schemas, and valuesets with entity_type annotations.
4. **Given** elements with shared ontology_term but different type/unit exist, **When** transforms are generated, **Then** bidirectional transform pairs exist with typed function specifications.

---

### User Story 2 — Output Verification and Statistics (Priority: P1)

After re-extraction, the curator reviews a summary report showing: element count per source, schema count, valueset count, value count, transform count, misclassification count, and entity type breakdown. This confirms the new pipeline produces correct, complete output.

**Why this priority**: Without verification, we can't confirm the new pipeline is an improvement over the old one. The report provides confidence that the migration is correct.

**Independent Test**: Run the pipeline and verify the ingestion report contains all expected statistics.

**Acceptance Scenarios**:

1. **Given** re-extraction completes, **When** the report is reviewed, **Then** it shows element count ≥ 1000 (BIDS alone has ~1000), schema count > 0, valueset count > 0, transform count > 0.
2. **Given** re-extraction completes, **When** entity types are checked, **Then** no entity that should be a valueset (e.g., "units", "modalities") appears as a schema.
3. **Given** old library output exists, **When** compared with new output, **Then** the new output has more valuesets and fewer misclassified schemas.

---

### Edge Cases

- What if a source download fails (network issue)? Pipeline logs the error and continues with remaining sources. Partial output is valid for completed sources.
- What if an isolated venv fails to create? Pipeline logs the error and skips that source. Curator can retry with `--docker` as fallback.
- What if transform generation produces 0 transforms? This means no elements share ontology_term across sources — the enrichment step may not have assigned terms yet. Report this as a warning.

## Requirements

### Functional Requirements

- **FR-001**: The pipeline MUST be run for all 5 sources: BIDS, NWB, DANDI, openMINDS, AIND, using the automated source acquisition (no manual --path flags).
- **FR-002**: Before re-extraction, the old library output MUST be cleared: delete existing elements/, schemas/, values/, valuesets/, transforms/, mappings/ directories.
- **FR-003**: Each source MUST be extracted using the 019 adapter framework with 4-way entity classification (class/attribute/enum_value/valueset).
- **FR-004**: After all sources are extracted, transforms MUST be generated between overlapping elements (020 transform engine).
- **FR-005**: After transforms, the ontology inverse map MUST be regenerated including all entity types (element, schema, valueset).
- **FR-006**: After all steps, `validate-ingestion` MUST run and produce `ingestion-report.yaml` with 0 violations.
- **FR-007**: A summary report MUST be produced showing per-source statistics and overall entity counts.

## Success Criteria

### Measurable Outcomes

- **SC-001**: All 5 sources extracted with 0 validation violations.
- **SC-002**: Element count ≥ 1000 (BIDS alone contributes ~1000).
- **SC-003**: Valueset count > 0 (units, modalities, etc. correctly classified).
- **SC-004**: Transform count > 0 (at least some overlapping elements detected).
- **SC-005**: No entity classified as "units" or "modalities" appears in schemas/ directory.
- **SC-006**: Full pipeline completes in under 30 minutes (first run with downloads).
- **SC-007**: ontology-index.yaml includes entity_type field on all entries.

### Assumptions

- Features 019, 020, and 021 are merged to main before this runs.
- Network access is available for first-run source downloads.
- uv and git are available on the host.
- The library output will replace the existing content-addressed files.
