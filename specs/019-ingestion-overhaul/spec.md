# Feature Specification: Ingestion Overhaul

**Feature Branch**: `019-ingestion-overhaul`
**Created**: 2026-03-20
**Status**: Draft
**Input**: Overhaul the ingestion pipeline for rigorous schema classification (class vs attribute vs enum vs valueset), LLM-assisted extraction, docker-based code inspection, extensible source support (JSON Schema, LinkML, CSV+data dictionary, code repos), parameterizable workflow, and output validation.

## Clarifications

### Session 2026-03-20

- Q: How precisely should source provenance track the origin of ingested data? → A: Every provenance entry must include `source_ref` with repo URL, git committish, file path within repo, and SHA-256 checksum of source file. Non-git sources include file path + checksum. Docker sources add package_version.

---

## User Scenarios & Testing

### User Story 1 — Rigorous Schema Classification (Priority: P1)

A data curator ingests a new schema source and the system correctly classifies every entity as a class (sh:NodeShape), an attribute/property (rdf:Property), an enum value (ValueConcept), or a valueset (collection of enum values). Misclassifications like "units" appearing as a schema class are caught and corrected.

**Why this priority**: The current ingestion produces incorrect classifications (e.g., unit lists as schemas, enum collections as elements). Without correct classification, the entire registry is unreliable.

**Independent Test**: Ingest the BIDS schema and verify that every output entity has the correct type. Run `undata-library validate` on output — 0 misclassification violations.

**Acceptance Scenarios**:

1. **Given** a JSON Schema with `$defs` containing both class definitions and enum definitions, **When** ingested, **Then** classes are emitted as SchemaRecord, properties as ElementRecord, and enums as ValueConcept with correct type tags.
2. **Given** a schema with a `units` field that is an enum/valueset (not a class), **When** ingested, **Then** it is classified as a ValueSet (collection of ValueConcepts), not as a SchemaRecord.
3. **Given** an attribute whose type is another class (e.g., `address: Address`), **When** ingested, **Then** the attribute is emitted as an ElementRecord with `data_type: object` and a reference to the Address SchemaRecord.
4. **Given** a schema with nested class hierarchies, **When** ingested, **Then** the parent-child relationships are preserved in SchemaRecord provenance.

---

### User Story 2 — Extensible Source Adapters (Priority: P1)

A data curator ingests schemas from a new source type (e.g., a CSV data dictionary, a JSON Schema file, a LinkML YAML, or a GitHub code repository) using a unified adapter interface. The system handles each source format without custom code per source.

**Why this priority**: The current system has 5 hardcoded adapters. Extending to new sources requires significant custom code each time. A generic adapter framework enables community contributions and rapid onboarding of new schemas.

**Independent Test**: Ingest a standalone JSON Schema file (not from any of the 5 known sources) and verify correct element/schema/value output.

**Acceptance Scenarios**:

1. **Given** a draft-07/2019/2020-12 JSON Schema file, **When** ingested via the generic JSON Schema adapter, **Then** all properties, definitions, and enums are correctly classified and emitted.
2. **Given** a LinkML YAML schema, **When** ingested via the LinkML adapter, **Then** classes map to SchemaRecord, slots map to ElementRecord, and enums map to ValueSet/ValueConcept.
3. **Given** a CSV file with a data dictionary (column name, type, description, allowed values), **When** ingested via the CSV adapter, **Then** each row produces an ElementRecord with correct data_type, description, and response_options from allowed values.
4. **Given** a GitHub repository URL containing a Python/TypeScript schema package, **When** ingested with docker-based code inspection enabled, **Then** the system launches an appropriate container, installs the package, introspects the schema classes, and emits elements/schemas.

---

### User Story 3 — LLM-Assisted Classification (Priority: P2)

When the rule-based classifier is uncertain about an entity's type (class vs attribute vs enum), the system optionally invokes an LLM (local via Ollama or remote via litellm) to resolve the ambiguity. The LLM provides a classification with confidence score, and the decision is recorded in provenance.

**Why this priority**: Rule-based classification covers ~80% of cases. The remaining 20% (ambiguous nested types, polymorphic fields, underdocumented schemas) benefit from LLM reasoning. This is an enhancement, not a prerequisite.

**Independent Test**: Ingest a schema with known ambiguous entities, run with LLM enabled, verify correct classification and provenance records showing LLM-assisted decisions.

**Acceptance Scenarios**:

1. **Given** an ambiguous entity and LLM enabled (`--llm-model ollama/llama3`), **When** the rule-based classifier returns confidence < 0.7, **Then** the LLM is invoked with the entity's context (name, type, description, parent, siblings) and returns a classification.
2. **Given** LLM is disabled (default), **When** an ambiguous entity is encountered, **Then** the system uses its best rule-based guess and flags the entity with `classification_confidence < 0.7` in provenance.
3. **Given** a remote LLM endpoint via litellm, **When** invoked, **Then** the system sends a structured prompt and parses the response into a classification decision.

---

### User Story 4 — Docker-Based Code Inspection (Priority: P2)

A data curator points the ingestion system at a code repository (local path or GitHub URL), and the system launches a Docker container with the appropriate runtime (Python, TypeScript/Node), installs the package, and introspects the schema definitions programmatically.

**Why this priority**: Many schemas are defined in code (Python dataclasses, Pydantic models, TypeScript interfaces) and cannot be extracted from static files alone. Docker isolation ensures safe execution of untrusted code.

**Independent Test**: Point ingestion at a known Python package (e.g., `aind-data-schema`) in a Docker container and verify schema extraction matches the file-based extraction.

**Acceptance Scenarios**:

1. **Given** a Python package with Pydantic models, **When** ingested with `--docker`, **Then** a Python container is launched, the package installed, models introspected via `__fields__`/`model_fields`, and elements emitted.
2. **Given** a TypeScript package with interface definitions, **When** ingested with `--docker`, **Then** a Node container is launched, the package compiled, AST parsed for interfaces/types, and elements emitted.
3. **Given** a repository that fails to install, **When** ingested, **Then** the system reports the failure with container logs and falls back to file-based extraction if available.

---

### User Story 5 — Parameterizable Workflow with Output Validation (Priority: P2)

The ingestion workflow is configurable via a YAML workflow definition that specifies: sources, classification rules, enrichment steps, validation checks, and output format. After ingestion, the system self-validates its output against the undata schema model.

**Why this priority**: A parameterizable workflow enables reproducible, auditable ingestion runs. Output validation catches regressions and misclassifications before they enter the registry.

**Independent Test**: Run ingestion with a workflow YAML that specifies validation rules, verify the validation report is produced and catches intentionally inserted errors.

**Acceptance Scenarios**:

1. **Given** a workflow YAML specifying source, classification overrides, and validation rules, **When** ingestion runs, **Then** each step executes in order and the workflow is recorded in provenance.
2. **Given** ingestion output, **When** validation runs, **Then** the system checks: (a) every element has valid data_type, (b) every schema has ≥1 property, (c) no orphan ValueConcepts, (d) sha256 in each file matches recomputed hash, (e) no duplicate URIs.
3. **Given** validation failures, **When** reported, **Then** each failure includes the file path, entity type, and specific violation with suggested fix.

---

### User Story 6 — Schema Model Alignment with Provenance (Priority: P3)

The SchemaRecord model is updated to match the ElementRecord provenance model: each schema has a semantic identity block (hashed) and N provenance entries (with PROV-O fields). Currently schemas have a simpler provenance structure than elements.

**Why this priority**: Consistency between element and schema provenance enables uniform tooling (verify, enrich, align) across both entity types.

**Independent Test**: Ingest a schema source and verify SchemaRecord files contain PROV-O provenance entries identical in structure to ElementRecord provenance.

**Acceptance Scenarios**:

1. **Given** a schema ingested from BIDS, **When** written to YAML, **Then** its provenance entries include `generated_at`, `attributed_to`, `activity`, `derived_from` — matching the ElementRecord provenance model.
2. **Given** the same schema class defined in two sources, **When** both are ingested, **Then** they share the same content-addressed URI (same property set = same hash) with separate provenance entries per source.

---

### Edge Cases

- What happens when a JSON Schema has circular `$ref` references? System must detect cycles and emit a warning, extracting what it can.
- What happens when a CSV data dictionary has no type column? System infers types from allowed_values (if present) or defaults to `string`.
- What happens when docker-based inspection times out? Configurable timeout (default 5 minutes), graceful fallback to file-based extraction.
- What happens when the LLM returns an invalid classification? System validates LLM output against the enum (class/attribute/enum/valueset); invalid responses are discarded and rule-based fallback is used.
- What happens when a valueset (enum collection) contains values that are also standalone elements? System emits both the ValueSet and individual ValueConcepts, linked by membership.

## Requirements

### Functional Requirements

**Schema Classification**

- **FR-001**: The ingestion system MUST classify every schema entity into exactly one of: `class` (sh:NodeShape → SchemaRecord), `attribute` (rdf:Property → ElementRecord), `enum_value` (→ ValueConcept), or `valueset` (→ ValueSet, a named collection of ValueConcepts).
- **FR-002**: ValueSet MUST be added as a new entity type — a named, content-addressed collection of ValueConcept URIs with its own provenance. Enums like "units", "modalities", "species" are ValueSets, not schemas. ValueSet members are URIs; output validation warns on unresolved member URIs but does not block ingestion (members may be ingested in a later run).
- **FR-003**: Attributes whose type is another class MUST be emitted as ElementRecord with `data_type: object` and a `type_ref` field pointing to the referenced SchemaRecord URI. `type_ref` is part of the identity hash (different referenced class = different element).
- **FR-004**: Classification MUST inspect structural signals: presence of `properties`/`slots` → class; leaf type + constraints → attribute; `enum`/`oneOf` with literal values → enum; named collection of enum values → valueset.
- **FR-005**: Each classification decision MUST include a `classification_confidence` score (0.0–1.0) recorded in provenance.

**Extensible Source Adapters**

- **FR-006**: The system MUST support a pluggable adapter interface: `BaseAdapter.extract(source_path) → list[ClassifiedEntity]` where `ClassifiedEntity` includes the entity, its classification, and confidence.
- **FR-007**: Built-in adapters MUST include: `JSONSchemaAdapter` (draft-07/2019/2020-12), `LinkMLAdapter`, `CSVDictionaryAdapter`, `CodeRepoAdapter` (Python + TypeScript via Docker).
- **FR-008**: The existing 5 source adapters (BIDS, NWB, DANDI, openMINDS, AIND) MUST be refactored to extend `BaseAdapter` with classification rigor. The old `extractors/` directory is deleted — no backward compatibility shims.
- **FR-009**: Third-party adapters MUST be registerable via entry points (`undata.adapters` group in `pyproject.toml`) or a `--adapter-module` CLI flag. The adapter registry MUST discover entry point adapters at startup.

**LLM-Assisted Classification**

- **FR-010**: The system MUST support optional LLM-assisted classification via `--llm-model MODEL` flag (e.g., `ollama/llama3`, `openai/gpt-4o`, any litellm-supported model).
- **FR-011**: LLM invocation MUST only occur when rule-based `classification_confidence < 0.7` (configurable threshold).
- **FR-012**: The LLM prompt MUST include: entity name, type signature, description, parent class context, and sibling entities for disambiguation.
- **FR-013**: LLM classification decisions MUST be recorded in provenance with `attributed_to: urn:llm:{model_name}` and `activity: classification`.
- **FR-014**: LLM MUST NOT be required — the system MUST function fully without any LLM configuration (rule-based only).

**Docker-Based Code Inspection**

- **FR-015**: `--docker` flag MUST enable container-based code inspection for repository sources.
- **FR-016**: The system MUST auto-detect the repository language (Python → python:3.12 image, TypeScript → node:20 image) or accept `--docker-image IMAGE`.
- **FR-017**: Container execution MUST be time-bounded (default 5 minutes, configurable via `--docker-timeout`).
- **FR-018**: Container MUST mount the repository read-only and write extraction results to a shared volume as JSON.
- **FR-019**: If container extraction fails, the system MUST fall back to file-based extraction and log the failure.

**Parameterizable Workflow**

- **FR-020**: Ingestion MUST accept a `--workflow YAML` file specifying: sources (list of {path, adapter, options}), classification overrides (entity → forced type), enrichment steps (enrich, embed), and validation rules.
- **FR-021**: Without a workflow file, the system MUST use sensible defaults (auto-detect adapter, no overrides, standard validation).
- **FR-022**: Workflow execution MUST be recorded in provenance: each step's start/end time, parameters, and outcome.

**Output Validation**

- **FR-023**: After ingestion, the system MUST self-validate output by checking: (a) every element has valid data_type, (b) every schema has ≥1 property URI, (c) sha256 matches recomputed hash, (d) no duplicate URIs, (e) all ValueConcept references in response_options resolve to existing files.
- **FR-024**: Validation results MUST be written to `ingestion-report.yaml` with per-file pass/fail status and violation details.
- **FR-025**: `--strict` mode MUST cause ingestion to fail (exit 1) if any validation violation is found.

**Precise Source Tracking**

- **FR-026**: Every provenance entry MUST include a `source_ref` block with precise origin metadata:
  - `repo`: GitHub repository URL or local path (e.g., `https://github.com/bids-standard/bids-specification`)
  - `committish`: Git commit SHA, tag, or branch at time of ingestion (e.g., `v1.9.0` or `abc123def`)
  - `file`: Relative path to the specific file within the repo (e.g., `src/schema/objects/entities.yaml`)
  - `checksum`: SHA-256 of the source file content at ingestion time
- **FR-027**: For non-git sources (CSV files, standalone JSON Schemas), `source_ref` MUST include `file` (absolute or relative path) and `checksum` (SHA-256 of file content). `repo` and `committish` are null.
- **FR-028**: For Docker-based code inspection, `source_ref` MUST additionally include `package_version` (installed package version string from pip/npm).
- **FR-029**: `source_ref` is NOT part of the identity hash — it is provenance metadata only. Same semantic content from different commits produces the same element URI.
- **FR-030**: Adapters MUST populate `source_ref` automatically. The `BaseAdapter.extract()` return type (`ClassifiedEntity`) MUST include `source_ref` as a required field.

**Schema Provenance Alignment**

- **FR-031**: `SchemaProvenance` MUST be extended to match `ProvenanceEntry`: add `generated_at`, `attributed_to`, `activity`, `derived_from`, `source_ref` fields.
- **FR-032**: SchemaRecord MUST store `sha256` in the YAML file, matching the ElementRecord pattern.

### Key Entities

- **ClassifiedEntity**: The output of an adapter — contains the raw entity data, its classification (class/attribute/enum/valueset), confidence score, source_ref (repo, committish, file, checksum), and source metadata.
- **ValueSet**: A new entity type — a named, content-addressed collection of ValueConcept URIs. Examples: "units" (collection of unit values), "modalities" (collection of modality values). Has semantic identity (hashed set of member URIs + name) and provenance.
- **BaseAdapter**: Abstract interface for source adapters. `extract(source) → list[ClassifiedEntity]`. Concrete implementations: JSONSchemaAdapter, LinkMLAdapter, CSVDictionaryAdapter, CodeRepoAdapter, BIDSAdapter, NWBAdapter, etc.
- **WorkflowSpec**: YAML-defined ingestion workflow with sources, classification overrides, enrichment steps, and validation rules.
- **IngestionReport**: Per-run validation report with pass/fail per file, violation details, and aggregate statistics.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Ingestion of all 5 current sources produces 0 misclassification violations (units/modalities as ValueSets, not schemas).
- **SC-002**: A new JSON Schema file (not from any known source) can be ingested with correct classification in under 2 minutes of curator effort (point at file, run command, review report).
- **SC-003**: A CSV data dictionary with 500 rows produces correct ElementRecords with types and descriptions in a single ingestion run.
- **SC-004**: LLM-assisted classification resolves ≥80% of ambiguous entities (confidence < 0.7) correctly, as measured against a curated test set.
- **SC-005**: Docker-based code inspection of a Python package extracts ≥95% of the elements that file-based extraction finds, with correct classifications.
- **SC-006**: Output validation catches 100% of intentionally injected errors (wrong data_type, missing sha256, duplicate URI, orphan ValueConcept).
- **SC-007**: SchemaRecord provenance entries are structurally identical to ElementRecord provenance entries (same PROV-O fields).
- **SC-008**: Full pipeline (ingest + validate) for the largest source (BIDS, ~1000 elements) completes in under 60 seconds.

### Assumptions

- Docker is available on the host for code inspection (not required — graceful degradation without Docker).
- LLM access is optional and not required for core functionality.
- litellm is used as the LLM abstraction layer, supporting Ollama (local) and any OpenAI-compatible API (remote).
- CSV data dictionaries follow a common pattern: one row per variable, columns for name, type, description, allowed_values.
- The existing 5 adapters will be rewritten as BaseAdapter subclasses. No backward compatibility — `extractors/` is deleted. Output may differ (improved classification), validated by new test suite.
